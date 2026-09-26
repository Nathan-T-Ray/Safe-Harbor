"""Safe Harbor v1 API. Application records and event history live in MongoDB."""
from __future__ import annotations

import importlib
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, ValidationError
from pymongo.errors import PyMongoError

from shared.contracts import Budget, CreateExperiment, CreateRun, EvidenceRevision, Run
from safe_harbor.mongo import MongoConfigurationError, describe_target
from safe_harbor.runtime.compiler import compile_harness
from safe_harbor.runtime.ledger import Ledger, LedgerError, digest, identifier, now
from safe_harbor.runtime.model_settings import freeze_generation_settings

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
logger = logging.getLogger("uvicorn.error")


class UnconfiguredLedger:
    """Stand-in when MONGODB_URI is missing: the API still starts, and every route that needs
    MongoDB answers 503 with the configuration message instead of failing at import."""

    def __init__(self, error: MongoConfigurationError):
        self.error = error

    def __getattr__(self, name):
        raise self.error


try:
    ledger = Ledger()
    mongo_configuration_error = None
except MongoConfigurationError as exc:
    ledger = UnconfiguredLedger(exc)
    mongo_configuration_error = exc
coordinator = None


def science():
    return importlib.import_module("safe_harbor.science")


def harnesses():
    return importlib.import_module("safe_harbor.harness")


def model_available() -> bool:
    return bool(os.getenv("OPENROUTER_API_KEY") and os.getenv("MODEL_ID")) and os.getenv("SAFE_HARBOR_READ_ONLY") != "1"


REVISION_FIXTURES = [
    {"fixture_id": "withhold-control-evidence", "label": "Withdraw control evidence", "description": "Prepared operational revision: mark untargeted-control evidence unavailable for the first selected candidate. Original source values remain unchanged."},
    {"fixture_id": "restore-control-evidence", "label": "Restore control evidence", "description": "Restore availability of the original hashed control evidence. This does not introduce a new biological measurement."},
]


# Read-only deployments (e.g. Vercel serverless) browse recorded runs from MongoDB Atlas. They never
# start the coordinator or accept writes, because serverless processes cannot hold coordinator leases.
READ_ONLY = os.getenv("SAFE_HARBOR_READ_ONLY") == "1"
READ_ONLY_MESSAGE = "Read-only deployment: recorded runs can be browsed here; start investigations from the full Safe Harbor server."


@asynccontextmanager
async def lifespan(app):
    global coordinator
    if READ_ONLY:
        logger.info("Safe Harbor API in read-only mode: coordinator disabled, writes rejected")
        yield
        return
    if mongo_configuration_error is not None:
        logger.error("Safe Harbor API started without MongoDB: %s", mongo_configuration_error)
        yield
        return
    target = describe_target(ledger.uri)
    logger.info("MongoDB target: %s host=%s database=%s", target["kind"], target["host"], ledger.db.name)
    ledger.initialize()
    try:
        module = importlib.import_module("safe_harbor.runtime.coordinator")
    except ModuleNotFoundError as exc:
        if exc.name != "safe_harbor.runtime.coordinator":
            raise
    else:
        coordinator = module.Coordinator(ledger)
        coordinator.start()
    yield
    if coordinator:
        coordinator.stop()
    ledger.client.close()


app = FastAPI(title="Safe Harbor", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def read_only_guard(request, call_next):
    if READ_ONLY and request.method not in ("GET", "HEAD", "OPTIONS"):
        return JSONResponse(status_code=503, content={"detail": READ_ONLY_MESSAGE})
    return await call_next(request)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174", "http://localhost:5176", "http://127.0.0.1:5176"], allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["*"])


@app.exception_handler(LedgerError)
async def ledger_error(request, exc):
    return JSONResponse(status_code=exc.code, content={"detail": str(exc)})


@app.exception_handler(MongoConfigurationError)
async def mongo_configuration_error_handler(request, exc):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(ValidationError)
async def schema_error(request, exc):
    return JSONResponse(status_code=422, content={"detail": "Record failed schema validation", "errors": exc.errors(include_context=False)})


def default_run_id() -> str | None:
    """Run a read-only deployment opens when no ?run= is given: SAFE_HARBOR_DEFAULT_RUN, else the
    most recent completed run (real-model preferred). Only ever a stored run; nothing is created."""
    configured = os.getenv("SAFE_HARBOR_DEFAULT_RUN")
    if configured:
        return configured
    for query in ({"status": "complete", "mode": "real_model"}, {"status": "complete"}):
        record = ledger.db.runs.find_one(query, {"_id": 0, "run_id": 1}, sort=[("created_at", -1)])
        if record:
            return record["run_id"]
    return None


@app.get("/health")
def health():
    if mongo_configuration_error is not None:
        return JSONResponse(status_code=503, content={"status": "unavailable", "detail": str(mongo_configuration_error), "mongodb": None, "authoritative_store": "MongoDB", "schema_version": 1})
    target = {**describe_target(ledger.uri), "database": ledger.db.name}
    try:
        ledger.client.admin.command("ping")
    except PyMongoError as exc:
        return JSONResponse(status_code=503, content={"status": "unavailable", "detail": f"MongoDB is unreachable ({type(exc).__name__}); check the Atlas network access list and credentials.", "mongodb": target, "authoritative_store": "MongoDB", "schema_version": 1})
    return {"status": "ok", "database": ledger.db.name, "mongodb": target, "authoritative_store": "MongoDB", "model_available": model_available(), "coordinator_available": coordinator is not None, "read_only": READ_ONLY, "default_run_id": default_run_id() if READ_ONLY else None, "schema_version": 1}


@app.get("/catalog")
def catalog():
    data = science().get_catalog()
    return {**data, "schema_version": 1, "modes": ["deterministic", "real_model"], "model_available": model_available(), "revision_fixtures": REVISION_FIXTURES}


def create_run(body: CreateRun, *, start: bool = True) -> dict:
    if body.mode == "mock":
        raise HTTPException(422, "Mock fixtures are supplied as files; live runs require deterministic or real_model mode.")
    if body.mode == "real_model" and not model_available():
        raise HTTPException(409, "Real-model execution is unconfigured. Set OPENROUTER_API_KEY and MODEL_ID in the ignored .env file.")
    pricing = None
    if body.mode == "real_model":
        from safe_harbor.runtime.pricing import freeze_model_pricing
        pricing = freeze_model_pricing(os.environ["MODEL_ID"])
    source = science().get_catalog()
    by_id = {candidate["candidate_id"]: candidate for candidate in source["candidates"]}
    if len(body.candidate_ids) != len(set(body.candidate_ids)) or set(body.candidate_ids) - set(by_id):
        raise HTTPException(422, "Candidate IDs must be unique IDs from the verified catalog.")
    harness = harnesses().get_harness(body.harness_hash)
    run_id = identifier("run")
    tasks = compile_harness(harness, run_id, body.candidate_ids)
    budget_input = body.budget or {}
    if set(budget_input) - {"token_limit", "tool_limit", "cost_limit_usd"}:
        raise HTTPException(422, "Only assigned budget limits may be supplied.")
    budget = Budget.model_validate(budget_input).model_dump()
    if min(budget["token_limit"], budget["tool_limit"], budget["cost_limit_usd"]) < 0:
        raise HTTPException(422, "Budget limits cannot be negative.")
    versions = {"criteria:v1": 1, "source:data_version": source["data_version"]}
    for candidate_id in body.candidate_ids:
        for scope in ("expression", "annotation", "sequence", "catalog"):
            versions[f"scope:{candidate_id}:{scope}"] = 1
    run = Run(
        run_id=run_id, objective="Do these measured expression changes justify excluding this candidate region?",
        mode=body.mode, status="queued", candidate_ids=body.candidate_ids, data_version=source["data_version"],
        harness_hash=harness["harness_hash"], budget=budget, created_at=now(), evidence_versions=versions,
        evidence_availability={candidate_id: {"control_evidence": True} for candidate_id in body.candidate_ids},
        replan_rounds=0, execution_limits={"workers": 2, "task_nodes": 24, "replan_rounds": 3, "transient_retries": 1},
        model_id=os.getenv("MODEL_ID") if body.mode == "real_model" else None,
        model_provider="openrouter" if body.mode == "real_model" else None,
        baseline_arm=harness.get("baseline_arm", "H1" if harness.get("parent_hash") else "H0"),
        model_pricing=pricing,
        model_settings=freeze_generation_settings(),
        scientific_contract="Published shortlist; GRCh38 reference, H1 context; no global safety label.",
    ).model_dump()
    frozen_assets = []
    for candidate_id in body.candidate_ids:
        data = {"candidate_id": candidate_id, "data_version": source["data_version"], "reference_assets": source.get("reference_assets", {}).get(candidate_id, {})}
        frozen_assets.append({
            "artifact_id": f"{run_id}:reference:{candidate_id}", "run_id": run_id, "kind": "reference_assets",
            "revision": 1, "content_hash": digest(data), "data": data, "evidence_ids": by_id[candidate_id]["evidence_ids"],
            "input_read_set": [{"key": key, "version": versions[key], "kind": "artifact" if key == "source:data_version" else "query_scope"} for key in ("source:data_version", f"scope:{candidate_id}:sequence", f"scope:{candidate_id}:annotation")],
            "provenance": {"data_version": source["data_version"], "mode": body.mode, "source": "Frozen source catalog; original sequence and annotation hashes retained inside reference_assets."},
            "created_at": run["created_at"],
        })
    manifest_data = {"data_version": source["data_version"], "criteria": source.get("criteria", {}), "provenance": source.get("provenance", {}), "limitations": source.get("limitations", [])}
    frozen_assets.append({"artifact_id": f"{run_id}:source-manifest", "run_id": run_id, "kind": "source_manifest", "revision": 1, "content_hash": digest(manifest_data), "data": manifest_data, "evidence_ids": sorted({item for candidate_id in body.candidate_ids for item in by_id[candidate_id]["evidence_ids"]}), "input_read_set": [{"key": "source:data_version", "version": source["data_version"], "kind": "artifact"}, {"key": "criteria:v1", "version": 1, "kind": "criteria"}], "provenance": {"data_version": source["data_version"], "mode": body.mode}, "created_at": run["created_at"]})
    ledger.create(run, [by_id[candidate_id] for candidate_id in body.candidate_ids], tasks, harness, artifacts=frozen_assets)
    if coordinator and start:
        coordinator.enqueue(run_id)
    return {"run_id": run_id}


@app.post("/runs", status_code=201)
def post_run(body: CreateRun):
    return create_run(body)


@app.get("/runs/{run_id}/snapshot")
def snapshot(run_id: str, through_sequence: int | None = Query(None, ge=0)):
    return ledger.snapshot(run_id, through_sequence)


@app.get("/runs/{run_id}/events")
def events(run_id: str, after_sequence: int = Query(0, ge=0)):
    return ledger.events(run_id, after_sequence)


@app.get("/runs/{run_id}/artifacts/{artifact_id}")
def artifact(run_id: str, artifact_id: str):
    ledger.get_run(run_id)
    record = ledger.db.artifacts.find_one({"run_id": run_id, "artifact_id": artifact_id}, {"_id": 0})
    if not record:
        raise HTTPException(404, "Artifact is outside this run or does not exist.")
    return record


@app.get("/runs/{run_id}/tasks/{task_id}/context")
def task_context(run_id: str, task_id: str):
    from safe_harbor.runtime.worker import build_context_packet
    run = ledger.get_run(run_id)
    task = ledger.db.tasks.find_one({"run_id": run_id, "task_id": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(404, "Task is outside this run or does not exist.")
    return build_context_packet(ledger, run, task)


@app.get("/runs/{run_id}/tasks/{task_id}/evidence/{artifact_id}")
def task_evidence(run_id: str, task_id: str, artifact_id: str, pointer: str = "", offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=20)):
    from safe_harbor.runtime.context import retrieve
    run = ledger.get_run(run_id)
    task = ledger.db.tasks.find_one({"run_id": run_id, "task_id": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(404, "Task is outside this run or does not exist.")
    return retrieve(ledger, run, task, {"artifact_id": artifact_id, "pointer": pointer, "offset": offset, "limit": limit})


class ValidateAssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    proposal: dict


@app.post("/runs/{run_id}/assessment-validation")
def assessment_validation(run_id: str, body: ValidateAssessmentRequest):
    """Read-only validator inspection. This endpoint never creates a model or scientific result."""
    from safe_harbor.runtime.assessments import validate_proposal
    from safe_harbor.runtime.context import available_artifacts
    run = ledger.get_run(run_id)
    task = ledger.db.tasks.find_one({"run_id": run_id, "task_id": body.task_id, "status": "complete"}, {"_id": 0})
    if not task:
        raise HTTPException(404, "Completed task not found in this run.")
    outputs = list(ledger.db.artifacts.find({"run_id": run_id, "artifact_id": {"$in": task.get("result_artifact_ids", [])}}, {"_id": 0}))
    existing = next((artifact["data"]["assessment"] for artifact in outputs if artifact["kind"] == "assessment_proposal"), None)
    if not existing:
        raise HTTPException(422, "Choose a task with a saved assessment proposal.")
    artifacts = available_artifacts(ledger, run, task) + [artifact for artifact in outputs if artifact["kind"] == "scientific_tool_result"]
    validated, errors = validate_proposal(body.proposal, artifacts, existing["criterion_results"], existing["screen_status"], run["evidence_availability"][task["candidate_id"]]["control_evidence"])
    return {"mode": "deterministic_validation", "model_called": False, "state_changed": False, "valid": not errors, "errors": errors, "validated_proposal": validated if not errors else None}


@app.post("/runs/{run_id}/resume")
def resume(run_id: str):
    ledger.get_run(run_id)
    if not coordinator:
        raise HTTPException(503, "Coordinator implementation is not available yet.")
    coordinator.enqueue(run_id)
    return {"run_id": run_id, "status": "resume_requested"}


@app.post("/runs/{run_id}/evidence-revisions")
def evidence_revision(run_id: str, body: EvidenceRevision):
    if body.fixture_id not in {fixture["fixture_id"] for fixture in REVISION_FIXTURES}:
        raise HTTPException(422, "Unknown prepared evidence revision.")
    try:
        revisions = importlib.import_module("safe_harbor.runtime.revisions")
    except ModuleNotFoundError:
        raise HTTPException(503, "Evidence revision execution is not available yet.")
    result = revisions.apply_revision(ledger, run_id, body.fixture_id)
    if coordinator:
        coordinator.enqueue(run_id)
    return result


@app.post("/experiments", status_code=201)
def create_experiment(body: CreateExperiment):
    try:
        evaluation = importlib.import_module("safe_harbor.evaluation")
    except ModuleNotFoundError:
        raise HTTPException(503, "Experiment execution is not available yet.")
    return evaluation.create_experiment(ledger=ledger, request=body.model_dump(), create_run=create_run)


@app.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: str):
    record = ledger.db.evaluations.find_one({"evaluation_id": experiment_id}, {"_id": 0})
    if not record:
        raise HTTPException(404, "Experiment not found.")
    return record


@app.get("/runs/{run_id}/export")
def export(run_id: str):
    return ledger.export(run_id)

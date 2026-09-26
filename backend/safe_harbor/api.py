"""Safe Harbor v1 API. Application records and event history live in MongoDB."""
from __future__ import annotations

import importlib
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from shared.contracts import Budget, CreateExperiment, CreateRun, EvidenceRevision, Run
from safe_harbor.runtime.compiler import compile_harness
from safe_harbor.runtime.ledger import Ledger, LedgerError, identifier, now

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
ledger = Ledger()
coordinator = None


def science():
    return importlib.import_module("safe_harbor.science")


def harnesses():
    return importlib.import_module("safe_harbor.harness")


def model_available() -> bool:
    return bool(os.getenv("OPENROUTER_API_KEY") and os.getenv("MODEL_ID"))


REVISION_FIXTURES = [
    {"fixture_id": "withhold-control-evidence", "label": "Withdraw control evidence", "description": "Prepared operational revision: mark untargeted-control evidence unavailable for the first selected candidate. Original source values remain unchanged."},
    {"fixture_id": "restore-control-evidence", "label": "Restore control evidence", "description": "Restore availability of the original hashed control evidence. This does not introduce a new biological measurement."},
]


@asynccontextmanager
async def lifespan(app):
    global coordinator
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
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174", "http://localhost:5176", "http://127.0.0.1:5176"], allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["*"])


@app.exception_handler(LedgerError)
async def ledger_error(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=exc.code, content={"detail": str(exc)})


@app.exception_handler(ValidationError)
async def schema_error(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=422, content={"detail": "Record failed schema validation", "errors": exc.errors(include_context=False)})


@app.get("/health")
def health():
    ledger.client.admin.command("ping")
    return {"status": "ok", "database": ledger.db.name, "authoritative_store": "MongoDB", "model_available": model_available(), "coordinator_available": coordinator is not None, "schema_version": 1}


@app.get("/catalog")
def catalog():
    data = science().get_catalog()
    return {**data, "schema_version": 1, "modes": ["deterministic", "real_model"], "model_available": model_available(), "revision_fixtures": REVISION_FIXTURES}


def create_run(body: CreateRun, *, start: bool = True) -> dict:
    if body.mode == "mock":
        raise HTTPException(422, "Mock fixtures are supplied as files; live runs require deterministic or real_model mode.")
    if body.mode == "real_model" and not model_available():
        raise HTTPException(409, "Real-model execution is unconfigured. Set OPENROUTER_API_KEY and MODEL_ID in the ignored .env file.")
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
        scientific_contract="Published shortlist; GRCh38 reference, H1 context; no global safety label.",
    ).model_dump()
    ledger.create(run, [by_id[candidate_id] for candidate_id in body.candidate_ids], tasks, harness)
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

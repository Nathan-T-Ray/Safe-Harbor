"""Isolated case runs and frozen dev/validation/final experiment orchestration.

Only this evaluator imports reference answers. Each arm receives a fresh run,
fresh task/artifact namespace, the same frozen input manifest and resource cap.
No model calls occur in MongoDB transaction callbacks.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import importlib
import json
import os
from pathlib import Path
import threading
import time

from shared.contracts import CreateRun
from safe_harbor.runtime.ledger import LedgerError, digest, identifier, now
from safe_harbor.science import get_catalog
from .baselines import DEFAULT_BUDGET, OUTPUT_CONTRACT, frozen_baselines
from .cases import load_cases
from .reference_answers import load_reference
from .scoring import extract_run_output, score_case

POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="safe-harbor-evaluation")
LOCK = threading.Lock()
ACTIVE = set()
TERMINAL = {"complete", "blocked", "failed", "budget_exhausted"}
ROOT = Path(__file__).resolve().parents[3]


class PendingCaseExecution(RuntimeError):
    """The driver must not dispatch another arm while an old call may spend."""
    pass


def _evaluation_fingerprints() -> dict:
    paths = {"reference_answers_sha256": ROOT/"data/safe_harbor/evaluator/reference_answers.json",
             "scoring_implementation_sha256": Path(__file__).with_name("scoring.py"),
             "case_manifest_sha256": ROOT/"data/safe_harbor/evaluator/splits.json"}
    fingerprints = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in paths.items()}
    production = list((ROOT/"backend/safe_harbor/runtime").glob("*.py"))
    production += [ROOT/"backend/safe_harbor/science"/name for name in ("__init__.py", "catalog.py", "calculations.py", "expression_tools.py", "tools.py")]
    production += [ROOT/"backend/safe_harbor/harness"/name for name in ("__init__.py", "specification.py")]
    production += [ROOT/"shared/contracts.py", ROOT/"backend/safe_harbor/api.py"]
    fingerprints["production_implementation_sha256"] = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(production)}
    return fingerprints


def _promotion_rule() -> dict:
    module = importlib.import_module("safe_harbor.evaluation.promotion")
    return module.freeze_promotion_rule()


def _public_case(case: dict) -> dict:
    # Explicit allowlist: expected numbers, decisions and rubrics can never be
    # accidentally copied into a worker packet when case formats expand.
    keys = {"case_id", "candidate_id", "scenario_id", "assembly", "cell_context", "data_version", "objective",
            "question", "instructions", "controls_available", "evidence_revision_fixture"}
    return {k: deepcopy(v) for k,v in case.items() if k in keys}


def _persist(ledger, experiment: dict) -> None:
    experiment["updated_at"] = now()
    ledger.db.evaluations.replace_one({"evaluation_id": experiment["evaluation_id"]}, deepcopy(experiment), upsert=True)


def _zero_usage() -> dict:
    return {"tokens": 0, "tool_calls": 0, "model_calls": 0, "cost_usd": 0.0, "duration_seconds": 0.0, "usage_complete": True, "status": "not_invoked"}


def _placeholder(case: dict, arm: str, experiment: dict, status: str = "pending", error: str | None = None) -> dict:
    return {"experiment_id": experiment["evaluation_id"], "comparison_manifest_hash": experiment["comparison_manifest_hash"],
            "case_id": case["case_id"], "candidate_id": case["candidate_id"], "scenario_id": case["scenario_id"],
            "split": case["split"], "arm": arm, "run_id": None, "harness_hash": experiment["arms"].get(arm),
            "status": status, "score": None,
            "usage": {"tokens": None, "tool_calls": 0, "model_calls": 0, "cost_usd": None, "duration_seconds": 0,
                      "usage_complete": False}, "trace_artifact_ids": [], "error": error}


def create_experiment(*, ledger, request: dict, create_run) -> dict:
    mode = request.get("mode", "real_model")
    if mode not in ("real_model", "deterministic"):
        raise LedgerError("Experiments require explicitly real_model or deterministic operational mode", 422)
    cases = load_cases()
    requested = request.get("candidate_ids")
    if requested:
        known = {c["candidate_id"] for c in cases}
        if set(requested)-known or len(requested) != len(set(requested)):
            raise LedgerError("Experiment candidates must be unique frozen case candidates", 422)
        cases = [c for c in cases if c["candidate_id"] in requested]
    source = get_catalog()
    pricing, pricing_error = None, None
    if mode == "real_model" and os.getenv("OPENROUTER_API_KEY") and os.getenv("MODEL_ID"):
        try:
            from safe_harbor.runtime.pricing import freeze_model_pricing
            pricing = freeze_model_pricing(os.environ["MODEL_ID"])
        except Exception as exc:
            pricing_error = str(exc)
    baselines = frozen_baselines(ledger.db)
    try:
        rule = _promotion_rule()
    except ModuleNotFoundError:
        rule = {"version": 1, "cost_reduction_fraction": 0.15, "require_no_quality_regression": True,
                "require_complete_usage_for_cost": True, "status": "promotion_module_unavailable"}
    split_bytes = (ROOT/"data/safe_harbor/evaluator/splits.json").read_bytes()
    split_package = json.loads(split_bytes)
    from safe_harbor.runtime.model_settings import freeze_generation_settings
    model_snapshot = {"provider": "openrouter", "model_id": os.getenv("MODEL_ID"),
                      **freeze_generation_settings(), "model_pricing": pricing, "cache_policy": "no_application_answer_cache; provider caching is not controlled and usage remains provisional"}
    manifest = {"schema_version": 1, "model": model_snapshot, "budget": dict(DEFAULT_BUDGET),
                "data_version": source["data_version"], "source_hashes": {s["source_id"]: s["sha256"] for s in source["provenance"]["sources"]},
                "criteria_sha256": source["provenance"]["criteria_sha256"],
                "split_hash": split_package["split_hash"], "case_ids": [c["case_id"] for c in cases],
                "case_manifest_sha256": hashlib.sha256(split_bytes).hexdigest(),
                "answer_contract_sha256": hashlib.sha256(OUTPUT_CONTRACT.encode()).hexdigest(),
                "evaluation_fingerprints": _evaluation_fingerprints(),
                "promotion_rule": rule, "baselines": {k: v["harness_hash"] for k,v in baselines.items()},
                "isolation": "Fresh run ID per case and arm; only that run's ancestors are retrievable; no derived answers shared across arms.",
                "paired_repetitions": 1, "case_timeout_seconds": float(os.getenv("SAFE_HARBOR_EVALUATION_CASE_TIMEOUT", "900")), "order": "H0/R0 alternate by case; candidate H1 added only after development proposal; final after selection",
                "optimizer_budget": {"token_limit": 40000, "tool_limit": 0, "cost_limit_usd": 1.0}}
    experiment_id = identifier("experiment")
    experiment = {"evaluation_id": experiment_id, "experiment_id": experiment_id, "schema_version": 1, "mode": mode,
                  "kind": "harness_comparison", "status": "queued", "created_at": now(), "updated_at": now(),
                  "comparison_manifest": manifest, "comparison_manifest_hash": digest(manifest),
                  "arms": {**manifest["baselines"], "H1": None}, "cases": cases, "results": [],
                  "model_snapshot": model_snapshot, "optimizer": None, "promotion": None,
                  "harness_versions": list(baselines.values()),
                  "evaluation_overhead": {"tokens": 0, "tool_calls": 0, "model_calls": 0, "cost_usd": 0.0, "duration_seconds": 0.0, "usage_complete": True, "scope": "Deterministic scoring duration only; no evaluator model call. Ingestion and development engineering excluded."}, "selected_harness_hash": baselines["H0"]["harness_hash"],
                  "limitations": split_package.get("limitations", []) + [
                      "One paired run per case; stochastic cost differences are provisional.",
                      "A rejected proposal demonstrates selection, not successful self-improvement.",
                      "Deterministic operational results cannot establish model quality or improvement.",
                      "Experiment orchestration stops on server-process death; persisted individual runs retain runtime recovery. No experiment-level recovery claim."]}
    for case in cases:
        for arm in ("H0", "R0") + (("H1",) if case["split"] != "development" else ()):
            experiment["results"].append(_placeholder(case, arm, experiment, "awaiting_proposal" if arm == "H1" else "pending"))
    blocked = ["Model pricing could not be frozen: " + pricing_error] if pricing_error else []
    if mode == "real_model" and not (os.getenv("OPENROUTER_API_KEY") and model_snapshot["model_id"]):
        blocked.append("Real-model access is unconfigured; set server-side OPENROUTER_API_KEY and MODEL_ID. No model run or improvement was fabricated.")
    if {c["split"] for c in cases} != {"development", "validation", "final"}:
        blocked.append("Selected candidates do not cover all frozen grouped splits; comparison requires development, validation and final groups.")
    if any(c["data_version"] != source["data_version"] for c in cases):
        blocked.append("Current source version differs from frozen cases; freeze a new experiment specification before running.")
    if rule.get("status") == "promotion_module_unavailable":
        blocked.append("Promotion rule implementation is not available to freeze before results.")
    if blocked:
        experiment.update(status="blocked", blockers=blocked)
        for result in experiment["results"]:
            result.update(status="not_run_blocked", error="; ".join(blocked), usage=_zero_usage())
        _persist(ledger, experiment)
        return experiment
    _persist(ledger, experiment)
    with LOCK:
        ACTIVE.add(experiment_id)
    POOL.submit(_drive_safely, ledger, experiment_id, create_run)
    return experiment


def _bind_case(ledger, run_id: str, case: dict, experiment: dict, arm: str):
    payload = {"run_id": run_id, "case": _public_case(case), "experiment_id": experiment["evaluation_id"],
               "comparison_manifest_hash": experiment["comparison_manifest_hash"], "arm": arm}
    def commit(session):
        run = ledger.get_run(run_id, session)
        if run.get("mode") == "real_model" and (run.get("model_pricing") or {}).get("pricing_hash") != (experiment["model_snapshot"].get("model_pricing") or {}).get("pricing_hash"):
            raise LedgerError("Provider pricing/routing changed after experiment freeze", 409)
        if run.get("mode") == "real_model" and run.get("model_settings") != {key: experiment["model_snapshot"][key] for key in ("temperature", "max_output_tokens", "context_limit_bytes", "reasoning") if key in experiment["model_snapshot"]}:
            raise LedgerError("Model generation/context settings changed after experiment freeze", 409)
        if run["status"] != "queued" or any(t["attempt"] for t in ledger.db.tasks.find({"run_id": run_id}, session=session)):
            raise LedgerError("Evaluation case must be bound before dispatch", 409)
        run.update(objective=case["question"], case_context=_public_case(case), experiment_id=experiment["evaluation_id"],
                   comparison_manifest_hash=experiment["comparison_manifest_hash"], evaluation_arm=arm,
                   comparison_model_settings=experiment["comparison_manifest"]["model"])
        event = ledger._write_event(session, run, "bind-case:"+run_id, "evaluation.case_bound", {})
        return {"sequence": event["sequence"]}
    ledger.transact("bind-case:"+run_id, payload, commit)


def _run_case(ledger, experiment: dict, case: dict, arm: str, harness_hash: str, create_run) -> dict:
    result = _placeholder(case, arm, experiment, "running")
    result["harness_hash"] = harness_hash
    started = time.monotonic()
    run_id = None
    try:
        if experiment["mode"] == "real_model" and os.getenv("MODEL_ID") != experiment["comparison_manifest"]["model"]["model_id"]:
            raise LedgerError("Model identity changed after experiment freeze", 409)
        if _evaluation_fingerprints() != experiment["comparison_manifest"]["evaluation_fingerprints"]:
            raise LedgerError("Reference answers, scoring/case definitions or production implementations changed after experiment freeze", 409)
        current = get_catalog()
        if current["data_version"] != experiment["comparison_manifest"]["data_version"] or current["provenance"]["criteria_sha256"] != experiment["comparison_manifest"]["criteria_sha256"] or {s["source_id"]: s["sha256"] for s in current["provenance"]["sources"]} != experiment["comparison_manifest"]["source_hashes"]:
            raise LedgerError("Input data or criteria changed after experiment freeze", 409)
        response = create_run(CreateRun(candidate_ids=[case["candidate_id"]], mode=experiment["mode"],
                                       harness_hash=harness_hash, budget=experiment["comparison_manifest"]["budget"]), start=False)
        run_id = response["run_id"]
        result["run_id"] = run_id
        _bind_case(ledger, run_id, case, experiment, arm)
        if case.get("evidence_revision_fixture"):
            from safe_harbor.runtime.revisions import apply_revision
            apply_revision(ledger, run_id, case["evidence_revision_fixture"])
        coordinator = importlib.import_module("safe_harbor.api").coordinator
        if coordinator is None:
            raise LedgerError("Persistent coordinator is unavailable", 503)
        latest = ledger.db.evaluations.find_one({"evaluation_id": experiment["evaluation_id"]}, {"_id": 0})
        latest["results"] = [r for r in latest["results"] if (r["case_id"], r["arm"]) != (case["case_id"], arm)] + [deepcopy(result)]
        _persist(ledger, latest)
        coordinator.enqueue(run_id)
        deadline = time.monotonic()+experiment["comparison_manifest"]["case_timeout_seconds"]
        while time.monotonic() < deadline:
            run = ledger.get_run(run_id)
            if run["status"] in TERMINAL:
                break
            time.sleep(.5)
        else:
            raise TimeoutError("Case did not reach a terminal ledger state before its experiment timeout")
        snapshot = ledger.snapshot(run_id)
        trace = extract_run_output(snapshot)
        scoring_started = time.monotonic()
        result["score"] = score_case(case, load_reference(case["case_id"]), trace)
        result["scoring_duration_seconds"] = round(time.monotonic()-scoring_started, 6)
        result["status"] = "complete" if run["status"] == "complete" else "failed"
        result["error"] = None if result["status"] == "complete" else run.get("stop_reason", run["status"])
        result["selected_trace_artifact_id"] = trace["selected_trace_artifact_id"]
        result["trace_artifact_ids"] = [a["artifact_id"] for a in snapshot["artifacts"] if a["kind"] == "worker_trace"]
        budget = run["budget"]
        unknown = any(budget.get(key, 0) for key in ("uncertain_tokens", "uncertain_cost_usd", "uncertain_model_calls", "reserved_tokens", "reserved_cost_usd"))
        result["usage"] = {"tokens": budget.get("tokens_used"), "tool_calls": budget.get("tool_calls", 0),
                           "model_calls": budget.get("model_calls", 0), "cost_usd": budget.get("cost_usd"),
                           "duration_seconds": round(time.monotonic()-started, 4), "pricing_hash": (run.get("model_pricing") or {}).get("pricing_hash"),
                           "usage_complete": not unknown and budget.get("cost_usd") is not None,
                           "uncertain_tokens": budget.get("uncertain_tokens", 0), "uncertain_cost_usd": budget.get("uncertain_cost_usd", 0)}
        if experiment["mode"] == "deterministic":
            result["status"] = "operational_complete" if run["status"] == "complete" else "operational_failed"
    except Exception as exc:
        result.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        # Failures still appear in required-output denominators; uncertainty is
        # retained instead of treating interrupted/model-unreported calls as free.
        snapshot = ledger.snapshot(run_id) if run_id else {"run": {"status": "failed"}, "artifacts": [], "tasks": []}
        scoring_started = time.monotonic()
        result["score"] = score_case(case, load_reference(case["case_id"]), extract_run_output(snapshot))
        result["scoring_duration_seconds"] = round(time.monotonic()-scoring_started, 6)
        result["usage"]["duration_seconds"] = round(time.monotonic()-started, 4)
        result["usage"]["usage_complete"] = False
        if run_id:
            b = snapshot["run"]["budget"]
            result["usage"].update(tokens=b.get("tokens_used"), tool_calls=b.get("tool_calls",0), model_calls=b.get("model_calls",0), cost_usd=b.get("cost_usd"),
                                    uncertain_tokens=b.get("uncertain_tokens",0)+b.get("reserved_tokens",0),
                                    uncertain_cost_usd=b.get("uncertain_cost_usd",0)+b.get("reserved_cost_usd",0))
            if snapshot["run"]["status"] not in TERMINAL:
                result["execution_still_active"] = True
                result["status"] = "pending_terminal_reconciliation"
                result["error"] += "; coordinator execution may still finish or incur already-reserved expenditure; no later comparison arm will dispatch"
    return result


def run_arm(ledger, experiment_id: str, arm: str, harness_hash: str, cases: list[dict], create_run) -> list[dict]:
    experiment = ledger.db.evaluations.find_one({"evaluation_id": experiment_id}, {"_id": 0})
    if not experiment:
        raise LedgerError("Unknown experiment", 404)
    outputs = []
    for case in cases:
        result = _run_case(ledger, experiment, case, arm, harness_hash, create_run)
        outputs.append(result)
        experiment = ledger.db.evaluations.find_one({"evaluation_id": experiment_id}, {"_id": 0})
        experiment["results"] = [r for r in experiment["results"] if (r["case_id"],r["arm"]) != (case["case_id"],arm)] + [result]
        _persist(ledger, experiment)
        if result.get("execution_still_active"):
            raise PendingCaseExecution(result["run_id"])
    return outputs


def _drive_safely(ledger, experiment_id: str, create_run):
    try:
        _drive(ledger, experiment_id, create_run)
    except PendingCaseExecution as exc:
        experiment = ledger.db.evaluations.find_one({"evaluation_id": experiment_id}, {"_id": 0})
        experiment.update(status="blocked", blockers=["A case remains active after the experiment deadline; pending usage must be reconciled before any complete comparison or later arm. No automatic experiment restart."], pending_run_ids=[str(exc)], usage_reconciliation_required=True)
        for row in experiment["results"]:
            if row["status"] in ("pending", "awaiting_proposal"):
                row.update(status="not_run_prior_case_pending", error="Experiment stopped before this assignment because a prior run is still active.", usage=_zero_usage())
        _persist(ledger, experiment)
    except Exception as exc:
        ledger.db.evaluations.update_one({"evaluation_id": experiment_id}, {"$set": {"status": "failed", "error": f"{type(exc).__name__}: {exc}", "updated_at": now()}})
    finally:
        with LOCK:
            ACTIVE.discard(experiment_id)


def _drive(ledger, experiment_id: str, create_run):
    def load():
        return ledger.db.evaluations.find_one({"evaluation_id": experiment_id}, {"_id": 0})
    exp = load()
    exp["status"] = "running_development"
    _persist(ledger, exp)
    for index, case in enumerate(c for c in exp["cases"] if c["split"] == "development"):
        for arm in (("H0","R0") if index%2 == 0 else ("R0","H0")):
            run_arm(ledger, experiment_id, arm, exp["arms"][arm], [case], create_run)
    exp = load()
    if exp["mode"] == "real_model":
        from safe_harbor.harness.optimizer import propose_harness
        proposal = propose_harness(ledger, experiment_id, exp["arms"]["H0"],
                                   [r for r in exp["results"] if r["split"] == "development"],
                                   exp["comparison_manifest"]["model"], exp["comparison_manifest"]["optimizer_budget"])
    else:
        proposal = {"status": "blocked", "candidate_hash": None, "reason": "Deterministic operational adapters cannot generate a genuine model architecture proposal.", "usage": {"tokens": 0, "tool_calls": 0, "model_calls": 0, "cost_usd": 0.0, "duration_seconds": 0.0, "usage_complete": True}}
    exp = load()
    exp["optimizer"] = proposal
    if proposal.get("status") == "candidate_ready":
        exp["arms"]["H1"] = proposal["candidate_hash"]
    else:
        for row in exp["results"]:
            if row["arm"] == "H1":
                row.update(status="not_run_no_candidate", error=proposal.get("error", proposal.get("reason", proposal["status"])), usage=_zero_usage())
    exp["status"] = "running_validation"
    _persist(ledger, exp)
    for index, case in enumerate(c for c in exp["cases"] if c["split"] == "validation"):
        order = ["H0", "R0"] if index%2 == 0 else ["R0", "H0"]
        if exp["arms"].get("H1"):
            order.append("H1")
        for arm in order:
            run_arm(ledger, experiment_id, arm, exp["arms"][arm], [case], create_run)
    exp = load()
    from .promotion import decide_promotion, save_promotion
    if exp["arms"].get("H1"):
        decision = decide_promotion([r for r in exp["results"] if r["split"] == "validation" and r["arm"] == "H0"],
                                    [r for r in exp["results"] if r["split"] == "validation" and r["arm"] == "H1"],
                                    exp["comparison_manifest"]["promotion_rule"], mode=exp["mode"])
    else:
        decision = {"status": "blocked" if exp["mode"] == "real_model" else "operational_only", "selected_harness_hash": exp["arms"]["H0"],
                    "reason": "No executable automatic candidate was available; no self-improvement claim."}
    save_promotion(ledger, experiment_id, decision)
    exp["promotion"] = decision
    exp["selected_harness_hash"] = decision.get("selected_harness_hash") or exp["arms"]["H0"]
    exp["status"] = "running_final"
    _persist(ledger, exp)
    # Selection is complete before any final case executes. The selected harness
    # is executed first here, proving reuse without selecting on final scores.
    selected_arm = "H1" if exp["selected_harness_hash"] == exp["arms"].get("H1") else "H0"
    for case in (c for c in exp["cases"] if c["split"] == "final"):
        order = [selected_arm] + [a for a in ("H0","R0","H1") if a != selected_arm and exp["arms"].get(a)]
        for arm in order:
            run_arm(ledger, experiment_id, arm, exp["arms"][arm], [case], create_run)
    exp = load()
    from .report import build_comparison_report, attach_report_to_run
    exp["status"] = "complete" if exp["mode"] == "real_model" else "operational_complete"
    exp["completed_at"] = now()
    exp["harness_versions"] = list(ledger.db.harness_versions.find({"harness_hash": {"$in": [h for h in exp["arms"].values() if h]}}, {"_id": 0}))
    if exp.get("optimizer", {}).get("proposal_artifact_id"):
        exp["optimizer_response_artifact"] = ledger.db.artifacts.find_one({"artifact_id": exp["optimizer"]["proposal_artifact_id"], "run_id": "experiment:" + experiment_id}, {"_id": 0})
    exp["evaluation_overhead"]["duration_seconds"] = sum(r.get("scoring_duration_seconds", 0) for r in exp["results"])
    exp["report"] = build_comparison_report(exp, results=exp["results"], optimizer=exp["optimizer"], promotion=exp["promotion"])
    _persist(ledger, exp)
    selected_runs = [r for r in exp["results"] if r["split"] == "final" and r["arm"] == selected_arm and r.get("run_id")]
    if selected_runs:
        exp["report_attachment"] = attach_report_to_run(ledger, selected_runs[0]["run_id"], exp, exp["report"])
        _persist(ledger, exp)

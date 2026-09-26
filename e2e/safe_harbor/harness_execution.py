#!/usr/bin/env python3
"""Real-process/MongoDB proof that a manually authored structural patch executes.

This is a deterministic operational E2E over actual ingested scientific data.
It is not an automatic proposal, model comparison, or improvement measurement.
No unit/component fixtures replace the API, tools, coordinator, or database.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

from _atlas import add_keep_db_flag, child_env, drop_journey_database, e2e_database, mongo_uri, target

from safe_harbor.harness import apply_patch, get_harness, save_harness
from safe_harbor.runtime.ledger import Ledger, now

ROOT = Path(__file__).resolve().parents[2]
ASSIGNED_BUDGET = {"token_limit": 60000, "tool_limit": 40, "cost_limit_usd": 5.0}


def request(base: str, path: str, body=None):
    payload = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def wait_for(base: str, run_id: str, timeout: float = 300):  # Atlas round-trips per poll
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snapshot = request(base, f"/runs/{run_id}/snapshot")
        status = snapshot["run"]["status"]
        if status == "complete":
            return snapshot
        if status in {"blocked", "failed", "budget_exhausted"}:
            raise AssertionError(f"Run ended {status}: {[(task['role_id'], task['status'], task.get('error')) for task in snapshot['tasks']]}")
        time.sleep(0.3)
    raise AssertionError(f"Run {run_id} did not complete in {timeout} seconds")


def assert_complete(snapshot: dict, harness: dict, expected_roles: int):
    assert snapshot["run"]["mode"] == "deterministic"
    assert snapshot["run"].get("model_id") is None
    assert snapshot["run"].get("model_provider") is None
    assert snapshot["run"]["harness_hash"] == harness["harness_hash"]
    assert len(snapshot["tasks"]) == expected_roles
    assert all(task["status"] == "complete" for task in snapshot["tasks"])
    assert all(task["harness_hash"] == harness["harness_hash"] for task in snapshot["tasks"])
    assert snapshot["run"]["budget"]["model_calls"] == 0
    assert snapshot["run"]["budget"]["tokens_used"] == 0
    for key, limit in ASSIGNED_BUDGET.items():
        assert snapshot["run"]["budget"][key] == limit
    assert all(assessment["evidence_status"] == "unknown" for assessment in snapshot["assessments"])
    assert all(assessment["screen_status"] == "incomplete" for assessment in snapshot["assessments"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0, help="Default picks an available loopback port.")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "safe-harbor" / "harness-operational")
    add_keep_db_flag(parser)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.port:
        port = args.port
    else:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    database = e2e_database("harness")
    ledger = Ledger(uri=mongo_uri(), database=database)
    ledger.initialize()
    baseline = get_harness()
    patch = {"operations": [{
        "op": "insert_reviewer", "after_role_id": "assess",
        "role": {
            "role_id": "controls_audit", "kind": "review_candidate",
            "question": "Are the H1 control overlap numerator, denominator, and context preserved in this assessment?",
            "allowed_tools": ["control_overlap"], "context_policy": "numerical_first",
            "instructions": "This manually authored deterministic operational reviewer checks actual control results. Keep the expression concern unresolved pending real model interpretation. Never infer safety or causality.",
        },
    }]}
    candidate = apply_patch(baseline, patch, proposal_mode="deterministic_operational", proposal_metadata={
        "authoring": "manual_operational_e2e", "automatic_proposal": False,
        "purpose": "Prove saved structural changes affect executed roles and dependencies, not biological or model improvement.",
    })
    assert baseline["immutable_constraints"] == candidate["immutable_constraints"]
    save_harness(baseline, database=ledger.db)
    save_harness(candidate, database=ledger.db)
    assert get_harness(candidate["harness_hash"], database=ledger.db) == candidate
    env = child_env(database)  # inherits MONGODB_URI unchanged
    # This journey never performs a real model call, even if credentials exist.
    for key in list(env):
        if key.startswith("SAFE_HARBOR_CRASH_") or key.startswith("SAFE_HARBOR_OPERATIONAL_"):
            env.pop(key)
    log_path = args.output / "api-process.log"
    report = {"schema_version": 1, "started_at": now(), "mode": "deterministic_operational", "proposal_origin": "manual_operational_e2e", "automatic_proposal": False, "model_improvement_measured": False, "database": database, "mongo_target": target(database), "port": port, "assigned_budget_per_run": ASSIGNED_BUDGET, "patch": patch}
    process = None
    with log_path.open("w") as log:
        try:
            process = subprocess.Popen([sys.executable, "-m", "uvicorn", "safe_harbor.api:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            report["api_process_id"] = process.pid
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise AssertionError(f"API exited unexpectedly; inspect {log_path}")
                try:
                    health = request(base, "/health")
                    if health["database"] == database and health["coordinator_available"]:
                        break
                except (OSError, urllib.error.URLError):
                    pass
                time.sleep(0.1)
            else:
                raise AssertionError("Isolated API failed to start")
            catalog = request(base, "/catalog")
            assert any(candidate["candidate_id"] == "pansio-1" for candidate in catalog["candidates"])
            outcomes = []
            for name, harness, count in (("fixed_baseline", baseline, 6), ("manual_structural_patch", candidate, 7)):
                created = request(base, "/runs", {"mode": "deterministic", "candidate_ids": ["pansio-1"], "harness_hash": harness["harness_hash"], "budget": ASSIGNED_BUDGET})
                snapshot = wait_for(base, created["run_id"])
                assert_complete(snapshot, harness, count)
                assert snapshot["run"]["data_version"] == catalog["data_version"]
                export = request(base, f"/runs/{created['run_id']}/export")
                sequences = [event["sequence"] for event in export["events"]]
                assert sequences == list(range(1, snapshot["through_sequence"] + 1))
                assert export["snapshot"] == snapshot
                exported = args.output / f"{name}.json"
                exported.write_text(json.dumps(export, indent=2, ensure_ascii=False))
                outcomes.append({"label": name, "run_id": created["run_id"], "harness_hash": harness["harness_hash"], "task_count": len(snapshot["tasks"]), "completed_roles": [task["role_id"] for task in snapshot["tasks"]], "event_count": len(sequences), "measured_usage": snapshot["run"]["budget"], "export": exported.name})
                if name == "manual_structural_patch":
                    task = next(task for task in snapshot["tasks"] if task["role_id"] == "controls_audit")
                    assess = next(task for task in snapshot["tasks"] if task["role_id"] == "assess")
                    review = next(task for task in snapshot["tasks"] if task["role_id"] == "review")
                    assert task["depends_on"] == [assess["task_id"]]
                    assert task["task_id"] in review["depends_on"]
                    artifacts = [artifact for artifact in snapshot["artifacts"] if artifact["provenance"]["task_id"] == task["task_id"]]
                    scientific = next(artifact for artifact in artifacts if artifact["kind"] == "scientific_tool_result")
                    trace = next(artifact for artifact in artifacts if artifact["kind"] == "worker_trace")
                    assert scientific["data"]["tool_name"] == "control_overlap"
                    assert scientific["data"]["evidence_ids"]
                    assert trace["data"]["context_packet"]["context_policy"] == "numerical_first"
                    selection = trace["data"]["context_packet"]["context_selection_trace"]
                    assert selection["policy"] == "numerical_first"
                    assert selection["selected_characters"] <= selection["max_characters"]
                    assert trace["data"]["usage"]["tool_calls"] == 1
                    assert trace["data"]["usage"]["model_calls"] == 0
                    outcomes[-1]["executed_review_proof"] = {"task_id": task["task_id"], "depends_on": task["depends_on"], "downstream_review_task": review["task_id"], "scientific_artifact_id": scientific["artifact_id"], "worker_trace_id": trace["artifact_id"], "context_selection": selection}
            assert get_harness(baseline["harness_hash"], database=ledger.db) == baseline
            assert request(base, f"/runs/{outcomes[0]['run_id']}/snapshot")["run"]["harness_hash"] == baseline["harness_hash"]
            report.update(passed=True, outcomes=outcomes, source_data_version=catalog["data_version"], model_calls=0, ended_at=now())
        except Exception as exc:
            report.update(passed=False, error=f"{type(exc).__name__}: {exc}", ended_at=now())
            raise
        finally:
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            report["api_exit_code"] = process.returncode if process else None
            report["database_cleanup"] = drop_journey_database(database, args.keep_db, ledger.client)
            (args.output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
            ledger.client.close()
    print(json.dumps({"passed": report["passed"], "report": str(args.output / 'report.json'), "database": database, "automatic_proposal": False, "model_calls": 0}))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Actual API/process/MongoDB E2E for authoritative assessment acceptance.

An isolated test server adds a fixed operational-fixture route. It executes the
real screen tool, then submits labelled corrupted copies or the unchanged result
through Ledger.accept. No model inference or fictional biology is claimed.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


def serve(port):
    import uvicorn
    from safe_harbor import api
    from safe_harbor.runtime.compiler import compile_harness
    from safe_harbor.runtime.ledger import LedgerError, digest, identifier, now
    from safe_harbor.runtime.worker import execute_worker, read_set_for
    from safe_harbor.science import get_catalog
    from shared.contracts import Run, Budget

    @api.app.post("/operational/assessment-fixture")
    def fixture(body: dict):
        mutation = body["fixture_id"]
        assert mutation in {"unchanged", "forged_pass", "missing_required_rows", "forged_evidence", "invented_available_criterion", "wrong_context", "fractional_cost_settlement"}
        ledger = api.ledger
        source = get_catalog()
        candidate = source["candidates"][0]
        cid, run_id = candidate["candidate_id"], identifier("mock-acceptance-e2e")
        harness = {"mode": "mock", "proposal_mode": "mock", "name": "Authoritative acceptance fixture", "roles": [{"role_id": "assess", "kind": "assess_candidate", "question": "Operational acceptance fixture using real screen results; no model interpretation.", "depends_on": [], "allowed_tools": ["screen_candidate"], "max_tool_calls": 1, "max_model_calls": 1}]}
        if mutation == "fractional_cost_settlement":
            harness["roles"].append({**harness["roles"][0], "role_id": "second_assessment"})
        harness["harness_hash"] = digest(harness)
        versions = {"criteria:v1": 1, "source:data_version": source["data_version"], **{f"scope:{cid}:{key}": 1 for key in ("catalog", "annotation", "expression", "sequence")}}
        run = Run(run_id=run_id, mode="deterministic", status="blocked", objective="Operational fixture, no model inference.", candidate_ids=[cid], data_version=source["data_version"], harness_hash=harness["harness_hash"], created_at=now(), budget=Budget(), evidence_versions=versions, evidence_availability={cid: {"control_evidence": True}}, operational_fixture=True).model_dump()
        if mutation == "fractional_cost_settlement":
            run["objective"] = "Synthetic operational cost accounting fixture; all monetary values are artificial, no inference charge."
            run["budget"]["uncertain_cost_usd"] = 0.007
        data = {"data_version": source["data_version"], "criteria": source["criteria"]}
        manifest = {"artifact_id": f"{run_id}:source-manifest", "run_id": run_id, "kind": "source_manifest", "revision": 1, "content_hash": digest(data), "data": data, "evidence_ids": [], "input_read_set": [], "provenance": {"mode": "mock", "purpose": "Operational fixture; real frozen criteria"}, "created_at": now()}
        tasks = compile_harness(harness, run_id, [cid])
        ledger.create(run, [candidate], tasks, harness, [manifest])
        epoch = ledger.claim(run_id, "isolated-acceptance-fixture")
        run = ledger.get_run(run_id)
        if mutation == "fractional_cost_settlement":
            reservations = [ledger.reserve(run_id, task["task_id"], epoch, read_set_for(ledger, ledger.get_run(run_id), task), 0, 1, cost) for task, cost in zip(tasks, (0.1, 0.2))]
            initially_reserved = ledger.get_run(run_id)["budget"]["reserved_cost_usd"]
            for task, synthetic_cost in zip(reservations, (0.01, 0.02)):
                payload = execute_worker(ledger, ledger.get_run(run_id), task)
                payload["usage"]["cost_usd"] = synthetic_cost
                for artifact in payload["artifacts"]:
                    if artifact["kind"] == "worker_trace":
                        artifact["data"]["cost_fixture"] = "Synthetic operational accounting, not a real provider charge."
                    artifact["content_hash"] = digest(artifact["data"])
                ledger.accept(f"fixture-accept:{task['task_id']}", payload)
            budget = ledger.snapshot(run_id)["run"]["budget"]
            return {"fixture_id": mutation, "run_id": run_id, "accepted": True, "reason": None, "unchanged_on_rejection": True, "initially_reserved_cost_usd": initially_reserved, "budget": budget, "cost_mode": "synthetic_operational_no_provider_charge"}
        task = ledger.reserve(run_id, tasks[0]["task_id"], epoch, read_set_for(ledger, run, tasks[0]), 0, 1, 0)
        payload = execute_worker(ledger, ledger.get_run(run_id), task)
        record = copy.deepcopy(payload["assessments"][0])
        payload["assessments"][0] = record
        if mutation == "forged_pass":
            record["screen_status"] = "pass"
        elif mutation == "missing_required_rows":
            record["criterion_results"] = [row for row in record["criterion_results"] if row["status"] == "pass"]
            record["screen_status"] = "pass"
        elif mutation == "forged_evidence":
            record["criterion_results"][0]["evidence_ids"] = ["source:does-not-exist"]
        elif mutation == "invented_available_criterion":
            for row in record["criterion_results"]:
                if row["status"] == "incomplete":
                    row["status"] = "pass"
                    row["evidence_ids"] = ["source:does-not-exist"]
            record["screen_status"] = "pass"
        elif mutation == "wrong_context":
            record["cell_context"] = "H9 human embryonic stem cells"
        # Keep independently calculated tool artifacts untouched. Only the proposed
        # assessment copy is corrupted; proof cannot be made to agree by editing it.
        before = ledger.snapshot(run_id)
        operation_id = f"fixture-accept:{run_id}"
        try:
            result = ledger.accept(operation_id, payload)
            accepted, reason = True, None
        except LedgerError as exc:
            accepted, reason = False, str(exc)
        after = ledger.snapshot(run_id)
        unchanged_on_rejection = accepted or (after == before and not after["assessments"])
        return {"fixture_id": mutation, "run_id": run_id, "accepted": accepted, "reason": reason, "unchanged_on_rejection": unchanged_on_rejection, "screen_status": after["assessments"][0]["screen_status"] if after["assessments"] else None}

    uvicorn.run(api.app, host="127.0.0.1", port=port)


def main(port, output, cost_only=False):
    output.mkdir(parents=True, exist_ok=True)
    database = f"safe_harbor_aggregate_{int(time.time())}"
    env = dict(os.environ, PYTHONPATH=f"{ROOT / 'backend'}:{ROOT}", MONGODB_DATABASE=database, OPENROUTER_API_KEY="", MODEL_ID="")
    log = (output / "api.log").open("w")
    process = subprocess.Popen([sys.executable, __file__, "--serve", "--port", str(port)], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)

    def request(path, body=None):
        req = urllib.request.Request(f"http://127.0.0.1:{port}" + path, data=json.dumps(body).encode() if body else None, headers={"Content-Type": "application/json"})
        return json.load(urllib.request.urlopen(req, timeout=10))

    try:
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            try:
                if request("/health")["database"] == database:
                    break
            except OSError:
                pass
            time.sleep(0.1)
        cases = []
        fixture_ids = ["fractional_cost_settlement"] if cost_only else ["unchanged", "forged_pass", "missing_required_rows", "forged_evidence", "invented_available_criterion", "wrong_context"]
        for fixture_id in fixture_ids:
            case = request("/operational/assessment-fixture", {"fixture_id": fixture_id})
            assert case["accepted"] == (fixture_id in ("unchanged", "fractional_cost_settlement")), case
            assert case["unchanged_on_rejection"], case
            if fixture_id == "unchanged":
                assert case["screen_status"] == "incomplete"
            if fixture_id == "fractional_cost_settlement":
                assert case["initially_reserved_cost_usd"] == 0.1 + 0.2
                assert case["budget"]["reserved_cost_usd"] == 0
                assert case["budget"]["cost_usd"] == 0.01 + 0.02
                assert case["budget"]["uncertain_cost_usd"] == 0.007
            exported = request(f"/runs/{case['run_id']}/export")
            (output / f"{fixture_id}.json").write_text(json.dumps(exported, indent=2) + "\n")
            cases.append(case)
        report = {"mode": "deterministic_operational", "harness_mode": "mock", "model_calls": 0, "purpose": "Actual API/process/MongoDB acceptance boundary; real screen tool inputs, deliberately corrupted proposed copies explicitly labelled.", "passed": True, "database": database, "api_pid": process.pid, "cases": cases}
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    finally:
        process.terminate()
        process.wait(timeout=10)
        log.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--cost-only", action="store_true")
    parser.add_argument("--port", type=int, default=8033)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/safe_harbor/ledger-aggregate-e2e/acceptance")
    args = parser.parse_args()
    serve(args.port) if args.serve else main(args.port, args.output, args.cost_only)

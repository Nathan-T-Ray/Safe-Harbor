#!/usr/bin/env python3
"""Operational E2E: real API processes, MongoDB transactions and checkpoints.

Run from the repository root:
  PYTHONPATH=backend:. .venv/bin/python e2e/safe_harbor/runtime_operations.py

This creates an isolated MongoDB database and explicitly mock harness fixtures.
No biological result, model execution or measured improvement is manufactured.
The database and JSON exports remain available for inspection after execution.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

from shared.contracts import Budget, Run
from safe_harbor.runtime.compiler import compile_harness
from safe_harbor.runtime.ledger import Ledger, LedgerError, digest, identifier, now
from safe_harbor.science import get_catalog

ROOT = Path(__file__).resolve().parents[2]


class Journey:
    def __init__(self, port: int, output: Path):
        self.port = port
        self.base = f"http://127.0.0.1:{port}"
        self.output = output
        self.output.mkdir(parents=True, exist_ok=True)
        self.database = f"safe_harbor_operational_{int(time.time())}"
        self.ledger = Ledger(database=self.database)
        self.ledger.initialize()
        self.process = None
        self.log = None
        self.processes = []
        self.report = {"started_at": now(), "database": self.database, "mode": "deterministic_operational", "harness_mode": "mock", "biological_results": 0, "model_calls": 0, "cases": [], "processes": self.processes}

    def request(self, path: str, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base + path, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)

    def start(self, **hooks):
        env = dict(os.environ, PYTHONPATH=f"{ROOT / 'backend'}:{ROOT}", MONGODB_DATABASE=self.database)
        for key in list(env):
            if key.startswith("SAFE_HARBOR_CRASH_") or key.startswith("SAFE_HARBOR_OPERATIONAL_"):
                env.pop(key)
        env.update(hooks)
        path = self.output / f"process-{len(self.processes) + 1}.log"
        self.log = path.open("w")
        self.process = subprocess.Popen([sys.executable, "-m", "uvicorn", "safe_harbor.api:app", "--host", "127.0.0.1", "--port", str(self.port)], cwd=ROOT, env=env, stdout=self.log, stderr=subprocess.STDOUT)
        self.processes.append({"pid": self.process.pid, "hooks": hooks, "log": str(path), "started_at": now()})
        until = time.monotonic() + 25
        while time.monotonic() < until:
            if self.process.poll() is not None:
                if self.process.returncode in (86, 87):
                    return
                raise AssertionError(f"API process exited {self.process.returncode}; inspect {path}")
            try:
                if self.request("/health")["database"] == self.database:
                    return
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(0.1)
        raise AssertionError("API did not start")

    def stop(self):
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=10)
            self.processes[-1]["exit_code"] = self.process.returncode
            self.processes[-1]["ended_at"] = now()
        if self.log:
            self.log.close()
        self.process = None

    def fixture(self, label: str, roles: list[dict], token_limit: int = 60000):
        source = get_catalog()
        candidate = source["candidates"][0]
        cid = candidate["candidate_id"]
        harness = {"name": label, "parent_hash": None, "roles": roles, "patch": None, "proposal_mode": "mock", "mode": "mock", "immutable_constraints": {"purpose": "Operational E2E only; no scientific conclusion"}}
        harness["harness_hash"] = digest(harness)
        run_id = identifier("operational-e2e")
        versions = {"criteria:v1": 1, "source:data_version": source["data_version"], **{f"scope:{cid}:{scope}": 1 for scope in ("expression", "annotation", "sequence", "catalog")}}
        run = Run(run_id=run_id, objective="Operational E2E; no biological inference or model execution.", mode="deterministic", status="queued", candidate_ids=[cid], data_version=source["data_version"], harness_hash=harness["harness_hash"], created_at=now(), budget=Budget(token_limit=token_limit), evidence_versions=versions, evidence_availability={cid: {"control_evidence": True}}, replan_rounds=0, operational_fixture=True).model_dump()
        tasks = compile_harness(harness, run_id, [cid])
        self.ledger.create(run, [candidate], tasks, harness)
        return run_id

    def wait_run(self, run_id: str, terminal="complete"):
        until = time.monotonic() + 40
        while time.monotonic() < until:
            snapshot = self.request(f"/runs/{run_id}/snapshot")
            if snapshot["run"]["status"] == terminal:
                return snapshot
            if snapshot["run"]["status"] in ("blocked", "budget_exhausted", "failed"):
                raise AssertionError(snapshot["run"])
            time.sleep(0.1)
        raise AssertionError(f"Run did not reach {terminal}: {run_id}")

    def export(self, run_id: str):
        export = self.request(f"/runs/{run_id}/export")
        path = self.output / f"{run_id}.json"
        path.write_text(json.dumps(export, indent=2))
        return str(path)

    def ordinary(self):
        self.start()
        run_id = self.fixture("Mock metadata fixture", [role("metadata", "screen_regions")])
        self.request(f"/runs/{run_id}/resume", {})
        snapshot = self.wait_run(run_id)
        page = self.request(f"/runs/{run_id}/events?after_sequence=0")
        assert [event["sequence"] for event in page["events"]] == list(range(1, snapshot["through_sequence"] + 1))
        task, artifact = snapshot["tasks"][0], snapshot["artifacts"][0]
        operation_id = f"accept:{task['task_id']}:{task['coordinator_epoch']}:{task['attempt']}"
        payload = {"run_id": run_id, "task_id": task["task_id"], "epoch": task["coordinator_epoch"], "attempt": task["attempt"], "input_read_set": task["input_read_set"], "artifacts": [artifact], "assessments": [], "usage": artifact["data"]["usage"]}
        accepted = self.ledger.db.operations.find_one({"operation_id": operation_id})
        assert digest(payload) == accepted["payload_hash"]
        assert self.ledger.accept(operation_id, payload) == accepted["accepted_result"]
        conflict = json.loads(json.dumps(payload)); conflict["usage"]["tokens"] = 1
        try:
            self.ledger.accept(operation_id, conflict)
        except LedgerError as exc:
            assert "different content" in str(exc)
        else:
            raise AssertionError("Conflicting operation accepted")
        assert self.ledger.get_run(run_id)["through_sequence"] == snapshot["through_sequence"]
        historical = self.request(f"/runs/{run_id}/snapshot?through_sequence=1")
        assert historical["tasks"][0]["status"] == "queued" and not historical["artifacts"]
        assert self.request(f"/runs/{run_id}/export")["snapshot"] == snapshot
        self.report["cases"].append({"case": "ordered_events_idempotency_and_history", "run_id": run_id, "passed": True, "events": snapshot["through_sequence"], "export": self.export(run_id)})
        self.stop()

    def accepted_crash(self):
        run_id = self.fixture("Mock acceptance crash fixture", [role("before_crash", "screen_regions"), role("after_restart", "inspect_evidence", ["before_crash"])])
        self.start(SAFE_HARBOR_CRASH_AFTER_ACCEPT="screen_regions")
        assert self.process.wait(timeout=25) == 86
        assert self.ledger.db.tasks.find_one({"run_id": run_id, "role_id": "before_crash"})["status"] == "complete"
        assert self.ledger.db.tasks.find_one({"run_id": run_id, "role_id": "after_restart"})["status"] == "queued"
        assert self.ledger.db.operations.count_documents({"run_id": run_id, "operation_id": {"$regex": "^accept:"}}) == 1
        checkpoints_before = self.ledger.db.runtime_checkpoints.count_documents({"thread_id": {"$regex": "^" + run_id}})
        self.stop()
        self.start()
        snapshot = self.wait_run(run_id)
        assert self.ledger.db.operations.count_documents({"run_id": run_id, "operation_id": {"$regex": "^accept:"}}) == 2
        assert next(task for task in snapshot["tasks"] if task["role_id"] == "before_crash")["attempt"] == 1
        assert snapshot["run"]["coordinator_epoch"] == 2
        self.report["cases"].append({"case": "process_death_after_accept_before_checkpoint", "run_id": run_id, "passed": True, "crash_exit_code": 86, "checkpoints_before_restart": checkpoints_before, "accepted_outputs_after_restart": 2, "recovered_epoch": 2, "export": self.export(run_id)})
        self.stop()

    def reservation_crash(self):
        run_id = self.fixture("Mock interrupted reservation fixture", [role("reserved_work", "screen_regions")], token_limit=512)
        self.start(SAFE_HARBOR_CRASH_AFTER_RESERVE="screen_regions", SAFE_HARBOR_OPERATIONAL_TOKEN_RESERVATION="512")
        assert self.process.wait(timeout=25) == 87
        assert self.ledger.get_run(run_id)["budget"]["reserved_tokens"] == 512
        self.stop()
        self.start(SAFE_HARBOR_OPERATIONAL_TOKEN_RESERVATION="512")
        snapshot = self.wait_run(run_id, terminal="budget_exhausted")
        budget = snapshot["run"]["budget"]
        assert budget["uncertain_tokens"] == 512 and budget["reserved_tokens"] == 0
        assert budget["tokens_used"] == 0 and budget["model_calls"] == 0
        self.report["cases"].append({"case": "process_death_after_reservation", "run_id": run_id, "passed": True, "crash_exit_code": 87, "uncertain_tokens": 512, "status": "budget_exhausted", "usage_note": "512 artificial operational reservation units; no actual model call or measured model usage", "export": self.export(run_id)})
        self.stop()

    def execute(self):
        try:
            self.ordinary()
            self.accepted_crash()
            self.reservation_crash()
            self.report["passed"] = True
        finally:
            self.stop()
            self.report["finished_at"] = now()
            (self.output / "report.json").write_text(json.dumps(self.report, indent=2))
            print(json.dumps(self.report, indent=2))


def role(role_id: str, kind: str, depends_on=None):
    return {"role_id": role_id, "kind": kind, "question": "Exercise operational persistence; do not infer a biological conclusion.", "depends_on": depends_on or [], "allowed_tools": [], "context_policy": "relevant_evidence", "instructions": "Explicit mock harness used only for deterministic operational E2E."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8013)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "safe_harbor" / "runtime-e2e" / str(int(time.time())))
    args = parser.parse_args()
    Journey(args.port, args.output).execute()

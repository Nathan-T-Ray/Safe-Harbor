"""Shared plumbing for the Safe Harbor runtime E2E journeys (SH-Q03, SH-Q04, SH-Q05).

Extends the process/ledger patterns of ``runtime_operations.Journey``: every journey
starts actual ``uvicorn safe_harbor.api:app`` processes against an isolated MongoDB
replica-set database, kills them for real, and restarts fresh processes. Nothing here
asserts anything; the journey scripts record per-check evidence and pass/fail honestly.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env", override=False)

from runtime_operations import Journey  # noqa: E402
from shared.contracts import Budget, Run  # noqa: E402
from safe_harbor.harness import baseline_harness  # noqa: E402
from safe_harbor.harness.specification import canonical_hash  # noqa: E402
from safe_harbor.runtime.compiler import compile_harness  # noqa: E402
from safe_harbor.runtime.ledger import Ledger, identifier, now  # noqa: E402
from safe_harbor.science import get_catalog  # noqa: E402

TERMINAL = ("complete", "blocked", "budget_exhausted", "failed")


class E2E(Journey):
    """Journey with per-check evidence, raw HTTP status access and flexible fixtures."""

    def __init__(self, name: str, port: int, output: Path):
        if not (8030 <= port <= 8039 or 8070 <= port <= 8079):
            raise SystemExit("Use API ports 8030-8039 or 8070-8079 for these journeys.")
        self.name = name
        self.port = port
        self.base = f"http://127.0.0.1:{port}"
        self.output = output
        self.output.mkdir(parents=True, exist_ok=True)
        self.database = f"sh_e2e_{name}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        self.ledger = Ledger(database=self.database)
        self.ledger.initialize()
        self.process = None
        self.log = None
        self.processes = []
        self.catalog = get_catalog()
        self.report = {
            "journey": name, "started_at": now(), "database": self.database, "api_port": port,
            "mode": "deterministic_operational", "model_calls": 0,
            "labels": {
                "execution": "deterministic_operational: real scientific tools over real source tables; no model call; no API key present",
                "fault_injection": "operational crash hooks / delays / token reservations are fault-injection only and never reported as model usage",
                "biological_claims": "none; these journeys test runtime persistence and control flow only",
            },
            "checks": [], "processes": self.processes,
        }

    # ------------------------------------------------------------------ HTTP
    def call(self, method: str, path: str, body=None, timeout: float = 15):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base + path, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                return exc.code, json.loads(raw)
            except json.JSONDecodeError:
                return exc.code, {"raw": raw.decode(errors="replace")}

    # -------------------------------------------------------------- process
    def kill(self, sig: str = "SIGKILL") -> int:
        """Externally kill the running API/coordinator process (no graceful shutdown)."""
        self.process.kill()
        code = self.process.wait(timeout=10)
        self.processes[-1]["killed_with"] = sig
        return code

    def wait_exit(self, timeout: float = 60) -> int:
        code = self.process.wait(timeout=timeout)
        self.processes[-1]["exit_code"] = code
        self.processes[-1]["ended_at"] = now()
        return code

    # ------------------------------------------------------------- fixtures
    def candidate_ids(self, count: int) -> list[str]:
        return [candidate["candidate_id"] for candidate in self.catalog["candidates"][:count]]

    def fixture_run(self, harness: dict, candidate_ids: list[str], *, budget: dict | None = None, label: str) -> str:
        """Create a run directly in the ledger, flagged operational_fixture so the runtime's
        labeled fault-injection knobs (delay before accept, token reservation) apply.
        Evidence versions mirror api.create_run exactly."""
        by_id = {candidate["candidate_id"]: candidate for candidate in self.catalog["candidates"]}
        run_id = identifier(f"e2e-{self.name}")
        versions = {"criteria:v1": 1, "source:data_version": self.catalog["data_version"]}
        for cid in candidate_ids:
            for scope in ("expression", "annotation", "sequence", "catalog"):
                versions[f"scope:{cid}:{scope}"] = 1
        run = Run(
            run_id=run_id, objective=f"Operational E2E ({label}); no biological inference or model execution.",
            mode="deterministic", status="queued", candidate_ids=candidate_ids, data_version=self.catalog["data_version"],
            harness_hash=harness["harness_hash"], created_at=now(), budget=Budget(**(budget or {})),
            evidence_versions=versions, evidence_availability={cid: {"control_evidence": True} for cid in candidate_ids},
            replan_rounds=0, operational_fixture=True,
            execution_limits={"workers": 2, "task_nodes": 24, "replan_rounds": 3, "transient_retries": 1},
        ).model_dump()
        tasks = compile_harness(harness, run_id, candidate_ids)
        self.ledger.create(run, [by_id[cid] for cid in candidate_ids], tasks, harness)
        return run_id

    # --------------------------------------------------------------- polling
    def db_run(self, run_id: str) -> dict:
        return self.ledger.get_run(run_id)

    def db_tasks(self, run_id: str) -> list[dict]:
        return list(self.ledger.db.tasks.find({"run_id": run_id}, {"_id": 0}))

    def wait_until(self, predicate, timeout: float = 90, interval: float = 0.1, what: str = "condition"):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            value = predicate()
            if value:
                return value
            if self.process is not None and self.process.poll() is not None and self.process.returncode not in (86, 87):
                raise AssertionError(f"API process exited {self.process.returncode} while waiting for {what}")
            time.sleep(interval)
        raise AssertionError(f"Timed out waiting for {what}")

    def wait_terminal(self, run_id: str, timeout: float = 120) -> dict:
        return self.wait_until(lambda: (run := self.db_run(run_id))["status"] in TERMINAL and run, timeout, what=f"terminal status of {run_id}")

    # --------------------------------------------------------------- evidence
    def events(self, run_id: str) -> list[dict]:
        return list(self.ledger.db.events.find({"run_id": run_id}, {"_id": 0}).sort("sequence", 1))

    def max_concurrent_running(self, run_id: str) -> int:
        state, peak = {}, 0
        for event in self.events(run_id):
            for task in event["upserts"].get("tasks", []):
                state[task["task_id"]] = task["status"]
            peak = max(peak, sum(status == "running" for status in state.values()))
        return peak

    def operations(self, run_id: str, prefix: str | None = None, status: str | None = None) -> list[dict]:
        query = {"run_id": run_id}
        if prefix:
            query["operation_id"] = {"$regex": "^" + re.escape(prefix)}
        if status:
            query["status"] = status
        return list(self.ledger.db.operations.find(query, {"_id": 0, "accepted_result": 0}))

    def accepted_ops(self, run_id: str, task_id: str) -> list[dict]:
        """Acceptances of exactly this task (not of its ':revisionN' successors)."""
        pattern = "^accept:" + re.escape(task_id) + r":\d+:\d+$"
        return list(self.ledger.db.operations.find({"run_id": run_id, "status": "accepted", "operation_id": {"$regex": pattern}}, {"_id": 0, "accepted_result": 0}))

    def checkpoints(self, thread_prefix: str) -> int:
        return self.ledger.db.runtime_checkpoints.count_documents({"thread_id": {"$regex": "^" + thread_prefix}})

    def check(self, check_id: str, passed: bool, **evidence) -> bool:
        self.report["checks"].append({"check": check_id, "passed": bool(passed), "evidence": evidence})
        print(("PASS " if passed else "FAIL ") + check_id, flush=True)
        return bool(passed)

    def export_run(self, run_id: str) -> str | None:
        status, body = self.call("GET", f"/runs/{run_id}/export", timeout=30)
        if status != 200:
            return None
        path = self.output / f"{run_id}.export.json"
        path.write_text(json.dumps(body, indent=1, default=str))
        return str(path)

    def execute(self, cases):
        try:
            for case in cases:
                try:
                    case()
                except Exception as exc:  # a case crash is a recorded failure, never a silent pass
                    self.check(f"{case.__name__}:completed_without_harness_error", False, error=f"{exc.__class__.__name__}: {exc}", traceback=traceback.format_exc()[-4000:])
                finally:
                    self.stop()
        finally:
            self.stop()
            self.report["finished_at"] = now()
            self.report["passed"] = bool(self.report["checks"]) and all(check["passed"] for check in self.report["checks"])
            self.report["summary"] = {"checks": len(self.report["checks"]), "failed": [c["check"] for c in self.report["checks"] if not c["passed"]]}
            (self.output / "report.json").write_text(json.dumps(self.report, indent=2, default=str))
            print(json.dumps({"passed": self.report["passed"], **self.report["summary"], "report": str(self.output / "report.json")}, indent=2))
        return 0 if self.report["passed"] else 1


def mock_harness(name: str, roles: list[dict], proposal_mode: str = "mock") -> dict:
    """A raw harness record (not validated). Used for topology fixtures and invalid-plan probes."""
    base = baseline_harness()
    record = {"schema_version": 1, "name": name, "parent_hash": None, "roles": roles, "patch": None,
              "proposal_mode": proposal_mode, "immutable_constraints": base["immutable_constraints"],
              "description": "E2E fixture; operational only, no scientific claim."}
    record["harness_hash"] = canonical_hash(record)
    return record


def default_output(name: str) -> Path:
    return ROOT / "artifacts" / "safe_harbor" / name / time.strftime("%Y%m%dT%H%M%S")

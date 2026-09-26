#!/usr/bin/env python3
"""E2E proof that Safe Harbor runs against the MongoDB deployment in MONGODB_URI (MongoDB Atlas).

  set -a; . ./.env; set +a
  PYTHONPATH=backend:. .venv/bin/python e2e/safe_harbor/atlas_connectivity.py

Checks, all against the real deployment (nothing mocked):
  1. target_is_atlas: MONGODB_URI host ends in .mongodb.net. A non-Atlas target fails here unless
     --allow-non-atlas is given, in which case the whole report is labelled a stand-in and can never
     count as Atlas verification.
  2. ping (round-trip latency samples) and hello (replica set / transaction capability).
  3. A multi-document, multi-collection transaction (write concern majority, snapshot read concern)
     in a scratch database sh_e2e_atlas_<ts>_<hex>_txn: commit makes both writes visible; uncommitted
     writes are invisible outside the session; abort discards both writes.
  4. The real API (uvicorn safe_harbor.api:app on port 8096) against a unique database
     sh_e2e_atlas_<ts>_<hex>_api runs one deterministic single-candidate investigation
     (POST /runs {"candidate_ids":["pansio-1"],"mode":"deterministic"}) to completion; events read
     through the API are ordered and gap-free 1..through_sequence; LangGraph checkpoint collections
     (runtime_checkpoints, runtime_checkpoint_writes) hold documents in that database.
Latency (ping RTT, transaction time, run duration) and describe_target() are recorded in
artifacts/safe_harbor/atlas-connectivity/<ts>/report.json. Scratch databases are dropped unless --keep-db.
Deterministic mode only: OPENROUTER_API_KEY is blanked for the API child process, no model is called.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from pymongo.read_concern import ReadConcern  # noqa: E402
from pymongo.write_concern import WriteConcern  # noqa: E402

from safe_harbor.mongo import describe_target, is_atlas, make_client, mongo_uri, redact  # noqa: E402

PORT = 8096
TERMINAL = ("complete", "blocked", "budget_exhausted", "failed")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Journey:
    def __init__(self, args):
        self.args = args
        self.uri = mongo_uri()
        self.atlas = is_atlas(self.uri)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.output = args.output_dir or ROOT / "artifacts" / "safe_harbor" / "atlas-connectivity" / stamp
        self.output.mkdir(parents=True, exist_ok=True)
        base = f"sh_e2e_atlas_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        self.txn_db, self.api_db = base + "_txn", base + "_api"
        self.base = f"http://127.0.0.1:{PORT}"
        self.process = None
        self.client = None
        self.report = {
            "journey": "atlas_connectivity", "started_at": now(),
            "target": {**describe_target(self.uri), "uri": redact(self.uri), "is_atlas": self.atlas},
            "stand_in": not self.atlas,
            "label": ("MongoDB Atlas connectivity proof" if self.atlas else
                      "STAND-IN: non-Atlas deployment run with --allow-non-atlas; this does NOT verify Atlas connectivity"),
            "scratch_databases": [self.txn_db, self.api_db], "api_port": PORT, "mode": "deterministic",
            "model_calls": 0, "latency": {}, "checks": [],
        }

    # ------------------------------------------------------------------ helpers
    def check(self, check_id: str, passed: bool, **evidence) -> bool:
        self.report["checks"].append({"id": check_id, "passed": bool(passed), **evidence})
        print(f"[{'PASS' if passed else 'FAIL'}] {check_id} {json.dumps(evidence, default=str)[:240]}")
        return bool(passed)

    def call(self, method: str, path: str, body=None, timeout: float = 30):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base + path, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                return exc.code, json.loads(raw)
            except ValueError:
                return exc.code, {"raw": raw.decode(errors="replace")[:500]}

    # ------------------------------------------------------------------ steps
    def target(self) -> bool:
        return self.check("target_is_atlas", self.atlas, host=self.report["target"]["host"], kind=self.report["target"]["kind"],
                          allowed_stand_in=bool(self.args.allow_non_atlas and not self.atlas))

    def ping(self):
        self.client = make_client(self.uri)
        samples = []
        for _ in range(5):
            started = time.perf_counter()
            self.client.admin.command("ping")
            samples.append((time.perf_counter() - started) * 1000)
        hello = self.client.admin.command("hello")
        self.report["latency"]["ping_ms"] = {"samples": [round(s, 2) for s in samples], "min": round(min(samples), 2), "median": round(statistics.median(samples), 2)}
        transactional = bool(hello.get("setName")) or hello.get("msg") == "isdbgrid"
        self.report["deployment"] = {"set_name": hello.get("setName"), "max_wire_version": hello.get("maxWireVersion"), "is_writable_primary": hello.get("isWritablePrimary")}
        self.check("ping", True, median_ms=self.report["latency"]["ping_ms"]["median"])
        self.check("transaction_capable_deployment", transactional, set_name=hello.get("setName"))

    def transaction(self):
        db = self.client[self.txn_db]
        for name in ("ledger", "journal"):
            db.create_collection(name)
        options = dict(read_concern=ReadConcern("snapshot"), write_concern=WriteConcern("majority"))
        committed_id = uuid.uuid4().hex
        with self.client.start_session() as session:
            started = time.perf_counter()
            session.start_transaction(**options)
            db.ledger.insert_one({"_id": committed_id, "kind": "commit", "amount": 1}, session=session)
            db.journal.insert_one({"_id": committed_id, "kind": "commit", "sequence": 1}, session=session)
            own_read = db.ledger.find_one({"_id": committed_id}, session=session) is not None
            outside_before = db.ledger.find_one({"_id": committed_id}) is None
            session.commit_transaction()
            commit_ms = (time.perf_counter() - started) * 1000
        visible = db.ledger.count_documents({"_id": committed_id}) == 1 and db.journal.count_documents({"_id": committed_id}) == 1
        self.check("transaction_commit", own_read and outside_before and visible, read_own_write=own_read,
                   invisible_outside_before_commit=outside_before, both_visible_after_commit=visible, write_concern="majority")

        aborted_id = uuid.uuid4().hex
        with self.client.start_session() as session:
            started = time.perf_counter()
            session.start_transaction(**options)
            db.ledger.insert_one({"_id": aborted_id, "kind": "abort"}, session=session)
            db.journal.insert_one({"_id": aborted_id, "kind": "abort"}, session=session)
            session.abort_transaction()
            abort_ms = (time.perf_counter() - started) * 1000
        discarded = db.ledger.count_documents({"_id": aborted_id}) == 0 and db.journal.count_documents({"_id": aborted_id}) == 0
        self.check("transaction_abort", discarded, both_discarded=discarded)
        self.report["latency"]["transaction_commit_ms"] = round(commit_ms, 2)
        self.report["latency"]["transaction_abort_ms"] = round(abort_ms, 2)

    def start_api(self):
        env = dict(os.environ, PYTHONPATH=f"{ROOT / 'backend'}:{ROOT}", MONGODB_DATABASE=self.api_db, OPENROUTER_API_KEY="")
        for key in list(env):
            if key.startswith("SAFE_HARBOR_CRASH_") or key.startswith("SAFE_HARBOR_OPERATIONAL_"):
                env.pop(key)
        log_path = self.output / "api.log"
        self.log = log_path.open("w")
        started = time.perf_counter()
        self.process = subprocess.Popen([sys.executable, "-m", "uvicorn", "safe_harbor.api:app", "--host", "127.0.0.1", "--port", str(PORT)],
                                        cwd=ROOT, env=env, stdout=self.log, stderr=subprocess.STDOUT)
        until = time.monotonic() + 60
        health = None
        while time.monotonic() < until:
            if self.process.poll() is not None:
                break
            try:
                status, health = self.call("GET", "/health", timeout=5)
                if status == 200 and health.get("database") == self.api_db:
                    break
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(0.2)
        ok = bool(health and health.get("database") == self.api_db and self.process.poll() is None)
        self.report["latency"]["api_startup_ms"] = round((time.perf_counter() - started) * 1000, 2)
        self.check("api_started_against_target", ok, pid=self.process.pid, health=health, exit_code=self.process.poll(), log=str(log_path.relative_to(ROOT)) if log_path.is_relative_to(ROOT) else str(log_path))
        return ok

    def run_investigation(self):
        started = time.perf_counter()
        status, created = self.call("POST", "/runs", {"candidate_ids": ["pansio-1"], "mode": "deterministic"})
        if not self.check("run_created", status == 201, http_status=status, run_id=created.get("run_id"), body=None if status == 201 else created):
            return
        run_id = created["run_id"]
        until = time.monotonic() + self.args.run_timeout
        snapshot = None
        while time.monotonic() < until:
            status, snapshot = self.call("GET", f"/runs/{run_id}/snapshot")
            if status == 200 and snapshot["run"]["status"] in TERMINAL:
                break
            if self.process.poll() is not None:
                break
            time.sleep(0.5)
        duration = (time.perf_counter() - started) * 1000
        self.report["latency"]["run_duration_ms"] = round(duration, 2)
        final = snapshot["run"]["status"] if snapshot and "run" in snapshot else None
        self.check("run_complete", final == "complete", run_id=run_id, status=final, through_sequence=snapshot.get("through_sequence") if snapshot else None,
                   tasks=len(snapshot.get("tasks", [])) if snapshot else None)

        events, after, through = [], 0, 0
        while True:
            status, page = self.call("GET", f"/runs/{run_id}/events?after_sequence={after}")
            if status != 200:
                break
            events.extend(page["events"])
            if not page["has_more"] or not page["events"]:
                through = page["through_sequence"]
                break
            after = page["events"][-1]["sequence"]
        sequences = [event["sequence"] for event in events]
        self.check("events_ordered_gap_free", status == 200 and sequences == list(range(1, through + 1)) and through > 0,
                   events=len(sequences), through_sequence=through if status == 200 else None, first=sequences[:1], last=sequences[-1:])

        db = self.client[self.api_db]
        ledger_events = db.events.count_documents({"run_id": run_id})
        checkpoints = db.runtime_checkpoints.count_documents({})
        writes = db.runtime_checkpoint_writes.count_documents({})
        run_threads = db.runtime_checkpoints.count_documents({"thread_id": {"$regex": "^" + run_id}})
        self.check("ledger_events_in_target", ledger_events == len(sequences), ledger_events=ledger_events, api_events=len(sequences))
        self.check("langgraph_checkpoints_in_target", checkpoints > 0 and writes > 0 and run_threads > 0,
                   runtime_checkpoints=checkpoints, runtime_checkpoint_writes=writes, checkpoints_for_run_threads=run_threads, database=self.api_db)

    def stop_api(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        if self.process:
            self.report["api_exit_code"] = self.process.returncode
            self.log.close()

    def cleanup(self):
        if self.client is None:
            return
        if self.args.keep_db:
            self.report["scratch_databases_dropped"] = False
            return
        for name in (self.txn_db, self.api_db):
            self.client.drop_database(name)
        remaining = set(self.client.list_database_names()) & {self.txn_db, self.api_db}
        self.report["scratch_databases_dropped"] = not remaining

    def run(self) -> int:
        try:
            if not self.target() and not self.args.allow_non_atlas:
                self.report["error"] = "MONGODB_URI is not a MongoDB Atlas (*.mongodb.net) deployment. Put the Atlas SRV string in .env, or pass --allow-non-atlas for a labelled stand-in run."
            else:
                self.ping()
                self.transaction()
                if self.start_api():
                    self.run_investigation()
        except Exception as exc:  # recorded honestly, never swallowed as a pass
            self.report["error"] = redact(f"{type(exc).__name__}: {exc}")[:2000]
            self.report["traceback"] = redact(traceback.format_exc())[-4000:]
            self.check("unexpected_error", False, error=self.report["error"][:300])
        finally:
            self.stop_api()
            try:
                self.cleanup()
            except Exception as exc:
                self.report["cleanup_error"] = redact(f"{type(exc).__name__}: {exc}")[:500]
        checks = self.report["checks"]
        failed = [c["id"] for c in checks if not c["passed"] and not (c["id"] == "target_is_atlas" and self.args.allow_non_atlas)]
        self.report["passed"] = bool(checks) and not failed and "error" not in self.report
        self.report["atlas_verified"] = self.report["passed"] and self.atlas
        self.report["failed_checks"] = failed
        self.report["finished_at"] = now()
        path = self.output / "report.json"
        path.write_text(json.dumps(self.report, indent=2, default=str) + "\n")
        print(json.dumps({k: self.report[k] for k in ("label", "target", "latency", "passed", "atlas_verified", "failed_checks")}, indent=2, default=str))
        print(f"report: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
        return 0 if self.report["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--allow-non-atlas", action="store_true", help="labelled stand-in run against a non-Atlas replica set")
    parser.add_argument("--keep-db", action="store_true", help="keep the scratch databases for inspection")
    parser.add_argument("--run-timeout", type=float, default=240)
    parser.add_argument("--output-dir", type=Path, default=None)
    return Journey(parser.parse_args()).run()


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""SH-Q10 E2E: bounded context over accumulated history after a fresh-process restart.

Run from the repository root:
  PYTHONPATH=backend:. .venv/bin/python e2e/safe_harbor/history.py

Mode: deterministic_operational. The harness is an explicitly labeled mock fixture
(as in runtime_operations.py); every task runs real deterministic science tools over
the verified catalog. No model is called and no biological conclusion is drawn.

Journey:
  1. Create an isolated MongoDB database and one run whose DAG is
     origin (older evidence) -> K chained intervening tasks -> two recall tasks.
       recall_declared   depends on [origin, last intervening]  (acceptance path)
       recall_chain_only depends on [last intervening] only     (diagnostic)
  2. Process 1 (uvicorn API) executes origin and all intervening tasks, then dies
     via SAFE_HARBOR_CRASH_AFTER_ACCEPT immediately after the last intervening
     task is accepted (exit 86; coordinator.py).
  3. Process 2 (fresh) reclaims the run with a new epoch and executes the recall
     tasks. Their worker_trace artifacts record the actual context packet.
  4. Process 3 (fresh) retrieves the recall trace and older evidence by exact
     artifact ID through GET /runs/{id}/artifacts/{artifact_id}.

Acceptance: the recall_declared packet carries the original objective and every
origin evidence artifact (exact ID; content hash verified), either inline or as an
omitted ID retrievable by bounded lookup; the packet and its evidence selection are
within the code-defined bound and smaller than the full history. Measured sizes are
written to report.json. Exit status is nonzero on any failed check.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path

from safe_harbor.runtime.compiler import MAX_TASKS, compile_harness
from safe_harbor.runtime.ledger import Ledger, digest, identifier, now
from safe_harbor.science import get_catalog

from shared.contracts import Budget, Run

ROOT = Path(__file__).resolve().parents[2]
# Code-defined bound: worker.py build_context_packet passes max_characters=28000 to
# harness.select_context_artifacts (and uses 28000 in its fallback). It bounds the
# selected evidence only; no limit on the whole packet is defined in code.
EVIDENCE_CHARACTER_LIMIT = 28000
CRASH_EXIT = 86  # coordinator.py: os._exit(86) after durable acceptance
OBJECTIVE = "SH-Q10 operational history E2E: keep the original objective and exact older evidence reachable from bounded context after restart. No biological inference or model execution."
INTERVENING_TOOLS = ["list_evidence", "table_slice", "expression_comparison", "control_overlap", "gene_proximity", "reference_sequence"]

# Static source observations (not measured); re-checked against the source at authoring time.
CODE_FINDINGS = [
    {"id": "context_direct_dependencies_only", "where": "backend/safe_harbor/runtime/worker.py:43-49",
     "observation": "build_context_packet gathers evidence only from the task's direct depends_on parents; older ancestors' artifacts are neither included nor listed in omitted_artifact_ids. Older evidence reaches a later task only when explicitly declared as a dependency."},
    {"id": "evidence_bound_not_packet_bound", "where": "backend/safe_harbor/runtime/worker.py:55,62; backend/safe_harbor/harness/__init__.py:63-69",
     "observation": "The 28000-character bound applies to selected evidence. Objective, candidate, criteria, input_read_set and budget are added without any whole-packet limit."},
    {"id": "no_bounded_artifact_discovery_endpoint", "where": "backend/safe_harbor/api.py:130-146; backend/safe_harbor/runtime/ledger.py:355-366",
     "observation": "The API retrieves an artifact only by exact ID. Discovering a task's result_artifact_ids via the API requires /snapshot (server replays every event) or paging /events. This E2E reads the single materialized task document from MongoDB to obtain IDs."},
    {"id": "dependency_lookup_not_run_scoped", "where": "backend/safe_harbor/runtime/worker.py:44",
     "observation": "Parent task lookup filters by task_id only (no run_id). Task IDs embed run_id, so this is not exercised as a defect here."},
]


def role(role_id: str, kind: str, tools: list[str], depends_on: list[str], question: str) -> dict:
    return {"role_id": role_id, "kind": kind, "question": question, "depends_on": depends_on, "allowed_tools": tools,
            "max_tool_calls": len(tools), "context_policy": "relevant_evidence",
            "instructions": "Explicit mock harness for deterministic operational history E2E only; no model interpretation."}


def size(value) -> dict:
    text = json.dumps(value)
    return {"characters": len(text), "utf8_bytes": len(text.encode("utf-8"))}


class HistoryJourney:
    def __init__(self, port: int, output: Path, intervening: int, timeout: float):
        if not 1 <= intervening <= MAX_TASKS - 3:
            raise SystemExit(f"--intervening must be 1..{MAX_TASKS - 3} (24-node plan limit, 3 non-intervening tasks)")
        self.port, self.base, self.output = port, f"http://127.0.0.1:{port}", output
        self.intervening, self.timeout = intervening, timeout
        self.output.mkdir(parents=True, exist_ok=True)
        self.database = f"safe_harbor_history_{int(time.time())}"
        self.ledger = Ledger(database=self.database)
        self.ledger.initialize()
        self.process = self.log = None
        self.processes: list[dict] = []
        self.checks: list[dict] = []
        self.report = {
            "ticket": "SH-Q10", "started_at": now(), "database": self.database,
            "mode": "deterministic_operational", "harness_mode": "mock",
            "mode_note": "Mock harness fixture; real deterministic science tools; no model calls; no biological conclusion.",
            "processes": self.processes, "checks": self.checks, "code_findings": CODE_FINDINGS,
        }

    # --- process and HTTP helpers (same pattern as runtime_operations.py) ---
    def raw(self, path: str, body=None, timeout: float = 30) -> bytes:
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base + path, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()

    def request(self, path: str, body=None, timeout: float = 30):
        return json.loads(self.raw(path, body, timeout))

    def start(self, **hooks):
        env = dict(os.environ, PYTHONPATH=f"{ROOT / 'backend'}:{ROOT}", MONGODB_DATABASE=self.database)
        for key in list(env):
            if key.startswith(("SAFE_HARBOR_CRASH_", "SAFE_HARBOR_OPERATIONAL_")):
                env.pop(key)
        env.update(hooks)
        path = self.output / f"process-{len(self.processes) + 1}.log"
        self.log = path.open("w")
        self.process = subprocess.Popen([sys.executable, "-m", "uvicorn", "safe_harbor.api:app", "--host", "127.0.0.1", "--port", str(self.port)], cwd=ROOT, env=env, stdout=self.log, stderr=subprocess.STDOUT)
        self.processes.append({"index": len(self.processes) + 1, "pid": self.process.pid, "hooks": hooks, "log": str(path), "started_at": now()})
        until = time.monotonic() + 25
        while time.monotonic() < until:
            if self.process.poll() is not None:
                if self.process.returncode == CRASH_EXIT and hooks:
                    return
                raise AssertionError(f"API process exited {self.process.returncode}; inspect {path}")
            try:
                if self.request("/health", timeout=5)["database"] == self.database:
                    return
            except (OSError, urllib.error.URLError, ValueError):
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
        self.process = self.log = None

    def check(self, name: str, passed: bool, **detail):
        self.checks.append({"check": name, "passed": bool(passed), **detail})
        return bool(passed)

    # --- fixture ---
    def fixture(self) -> dict:
        source = get_catalog()
        candidate = source["candidates"][0]
        cid = candidate["candidate_id"]
        roles = [role("origin", "screen_regions", ["inspect_candidate", "screen_candidate"], [], "Record the original candidate and screen evidence that later tasks must still reach.")]
        previous = "origin"
        for index in range(1, self.intervening + 1):
            last = index == self.intervening
            role_id = f"intervening_{index:02d}"
            # Only the last intervening task has kind inspect_evidence: the crash hook is keyed by kind.
            tool = "reference_sequence" if last else INTERVENING_TOOLS[(index - 1) % len(INTERVENING_TOOLS)]
            roles.append(role(role_id, "inspect_evidence" if last else "compute_features", [tool], [previous], f"Intervening operational history step {index}: run one approved deterministic tool."))
            previous = role_id
        roles.append(role("recall_declared", "compute_features", [], ["origin", previous], "Recall the original objective and the older origin evidence after restart (declared dependency)."))
        roles.append(role("recall_chain_only", "compute_features", [], [previous], "Diagnostic: is older origin evidence reachable through the dependency chain alone?"))
        harness = {"name": "SH-Q10 mock history fixture", "parent_hash": None, "roles": roles, "patch": None, "proposal_mode": "mock", "mode": "mock", "immutable_constraints": {"purpose": "Operational history E2E only; no scientific conclusion"}}
        harness["harness_hash"] = digest(harness)
        run_id = identifier("history-e2e")
        versions = {"criteria:v1": 1, "source:data_version": source["data_version"], **{f"scope:{cid}:{scope}": 1 for scope in ("expression", "annotation", "sequence", "catalog")}}
        run = Run(run_id=run_id, objective=OBJECTIVE, mode="deterministic", status="queued", candidate_ids=[cid], data_version=source["data_version"], harness_hash=harness["harness_hash"], created_at=now(), budget=Budget(), evidence_versions=versions, evidence_availability={cid: {"control_evidence": True}}, replan_rounds=0, operational_fixture=True).model_dump()
        tasks = compile_harness(harness, run_id, [cid])
        self.ledger.create(run, [candidate], tasks, harness)
        ids = {task["role_id"]: task["task_id"] for task in tasks}
        self.report.update(run_id=run_id, candidate_id=cid, task_count=len(tasks), intervening_tasks=self.intervening, objective=OBJECTIVE)
        return {"run_id": run_id, "ids": ids, "last": previous}

    def task(self, task_id: str) -> dict:
        # One materialized document (bounded); not a history replay.
        return self.ledger.db.tasks.find_one({"task_id": task_id}, {"_id": 0})

    def wait_run(self, run_id: str) -> dict:
        until = time.monotonic() + self.timeout
        while time.monotonic() < until:
            run = self.ledger.get_run(run_id)
            if run["status"] == "complete":
                return run
            if run["status"] in ("blocked", "budget_exhausted", "failed"):
                raise AssertionError(f"Run stopped as {run['status']}: {run.get('stop_reason')}")
            time.sleep(0.25)
        raise AssertionError(f"Run did not complete within {self.timeout}s")

    def artifact(self, run_id: str, artifact_id: str) -> tuple[dict, int]:
        body = self.raw(f"/runs/{run_id}/artifacts/{artifact_id}")
        return json.loads(body), len(body)

    def trace_of(self, run_id: str, task_id: str) -> tuple[dict, int]:
        for artifact_id in self.task(task_id)["result_artifact_ids"]:
            record, length = self.artifact(run_id, artifact_id)
            if record["kind"] == "worker_trace":
                return record, length
        raise AssertionError(f"No worker_trace for {task_id}")

    # --- journey ---
    def execute(self) -> bool:
        try:
            self.journey()
        except Exception as exc:  # noqa: BLE001 - any failure is recorded in the report and exits nonzero
            self.check("journey_completed", False, error=f"{exc.__class__.__name__}: {exc}", traceback=traceback.format_exc())
        finally:
            self.stop()
            passed = bool(self.checks) and all(item["passed"] for item in self.checks)
            self.report.update(passed=passed, finished_at=now(), failed_checks=[item["check"] for item in self.checks if not item["passed"]])
            (self.output / "report.json").write_text(json.dumps(self.report, indent=2))
            print(json.dumps(self.report, indent=2))
        return passed

    def journey(self):
        fixture = self.fixture()
        run_id, ids = fixture["run_id"], fixture["ids"]

        # Process 1: accumulate history, die right after the last intervening acceptance.
        self.start(SAFE_HARBOR_CRASH_AFTER_ACCEPT="inspect_evidence")
        exit_code = self.process.wait(timeout=self.timeout)
        self.stop()
        self.check("process_1_crashed_after_last_intervening_accept", exit_code == CRASH_EXIT, exit_code=exit_code)
        origin_before = self.task(ids["origin"])
        last_before = self.task(ids[fixture["last"]])
        self.check("history_accepted_before_crash", origin_before["status"] == "complete" and last_before["status"] == "complete",
                   origin_status=origin_before["status"], last_intervening_status=last_before["status"])
        self.check("recall_not_run_before_crash", all(self.task(ids[r])["status"] == "queued" for r in ("recall_declared", "recall_chain_only")))
        self.report["before_restart"] = {
            "through_sequence": self.ledger.get_run(run_id)["through_sequence"],
            "runtime_checkpoints": self.ledger.db.runtime_checkpoints.count_documents({"thread_id": {"$regex": "^" + run_id}}),
        }

        # Process 2: fresh process recovers and executes the recall tasks.
        self.start()
        run = self.wait_run(run_id)
        self.stop()
        origin, declared, chain = self.task(ids["origin"]), self.task(ids["recall_declared"]), self.task(ids["recall_chain_only"])
        self.check("recall_executed_in_fresh_epoch", declared["coordinator_epoch"] > origin["coordinator_epoch"] and chain["coordinator_epoch"] > origin["coordinator_epoch"],
                   origin_epoch=origin["coordinator_epoch"], recall_epochs=[declared["coordinator_epoch"], chain["coordinator_epoch"]], run_epoch=run["coordinator_epoch"])
        budget = run["budget"]
        self.check("no_model_usage", budget["model_calls"] == 0 and budget["tokens_used"] == 0, model_calls=budget["model_calls"], tokens_used=budget["tokens_used"])

        # Process 3: fresh process; bounded retrieval by exact ID only.
        self.start()
        origin_evidence = []
        bounded_bytes = 0
        for artifact_id in origin["result_artifact_ids"]:
            record, length = self.artifact(run_id, artifact_id)
            if record["kind"] == "worker_trace":
                continue
            bounded_bytes += length
            origin_evidence.append({"artifact_id": artifact_id, "kind": record["kind"], "tool_name": record["data"].get("tool_name"),
                                    "content_hash": record["content_hash"], "hash_verified": digest(record["data"]) == record["content_hash"], "retrieval_bytes": length})
        self.check("origin_evidence_exists_and_hashes_verify", bool(origin_evidence) and all(item["hash_verified"] for item in origin_evidence), origin_evidence=origin_evidence)
        declared_trace, declared_trace_bytes = self.trace_of(run_id, ids["recall_declared"])
        chain_trace, chain_trace_bytes = self.trace_of(run_id, ids["recall_chain_only"])
        bounded_bytes += declared_trace_bytes

        # Full history, measured for comparison only (never used to answer the recall).
        export_bytes = self.raw(f"/runs/{run_id}/export", timeout=120)
        export = json.loads(export_bytes)
        event_pages, event_bytes, after = 0, 0, 0
        while True:
            page_bytes = self.raw(f"/runs/{run_id}/events?after_sequence={after}", timeout=60)
            page = json.loads(page_bytes)
            event_pages += 1
            event_bytes += len(page_bytes)
            if not page["events"]:
                break
            after = page["events"][-1]["sequence"]
            if not page["has_more"]:
                break
        self.stop()

        events = export["events"]
        history = {
            "event_count": len(events), "through_sequence": export["snapshot"]["through_sequence"],
            "export_response_bytes": len(export_bytes), "export_serialized": size(export),
            "events_serialized": size(events), "events_api_pages": event_pages, "events_api_response_bytes": event_bytes,
            "artifact_count": len(export["snapshot"]["artifacts"]), "task_count": len(export["snapshot"]["tasks"]),
        }
        self.check("history_is_ordered_and_complete", [event["sequence"] for event in events] == list(range(1, history["through_sequence"] + 1)), event_count=len(events))
        self.report["history"] = history

        results = {}
        for name, trace, trace_bytes in (("recall_declared", declared_trace, declared_trace_bytes), ("recall_chain_only", chain_trace, chain_trace_bytes)):
            packet = trace["data"]["context_packet"]
            packet_text = json.dumps(packet)
            included = {item["artifact_id"]: item for item in packet["evidence"]}
            omitted = set(packet["omitted_artifact_ids"])
            selection = packet.get("context_selection_trace", {})
            references = []
            for item in origin_evidence:
                inline = included.get(item["artifact_id"])
                references.append({"artifact_id": item["artifact_id"], "tool_name": item["tool_name"],
                                   "inline": inline is not None, "inline_hash_matches": bool(inline) and inline["content_hash"] == item["content_hash"] and digest(inline["data"]) == item["content_hash"],
                                   "omitted_but_referenced": item["artifact_id"] in omitted, "id_anywhere_in_packet": item["artifact_id"] in packet_text})
            results[name] = {
                "task_id": ids[name], "worker_trace_artifact_id": trace["artifact_id"], "worker_trace_retrieval_bytes": trace_bytes,
                "recorded_context_characters": trace["data"]["context_characters"], "measured_packet": size(packet),
                "evidence_serialized": size(packet["evidence"]), "evidence_count": len(packet["evidence"]), "omitted_count": len(omitted),
                "context_selection_trace": selection, "objective_present": packet.get("objective") == OBJECTIVE,
                "origin_references": references,
                "packet_to_export_ratio": round(len(packet_text) / len(export_bytes), 4),
            }
        self.report["context_packets"] = results
        self.report["bounded_retrieval_bytes"] = bounded_bytes

        d = results["recall_declared"]
        selected = d["context_selection_trace"].get("selected_characters", d["context_selection_trace"].get("characters"))
        self.check("context_characters_recorded_matches_packet", d["recorded_context_characters"] == d["measured_packet"]["characters"])
        self.check("original_objective_in_packet", d["objective_present"] and self.ledger.get_run(run_id)["objective"] == OBJECTIVE)
        self.check("exact_older_evidence_referenced", all(ref["inline_hash_matches"] or ref["omitted_but_referenced"] for ref in d["origin_references"]),
                   inline=sum(ref["inline_hash_matches"] for ref in d["origin_references"]), omitted_referenced=sum(ref["omitted_but_referenced"] for ref in d["origin_references"]))
        self.check("evidence_selection_within_code_bound", selected is not None and selected <= EVIDENCE_CHARACTER_LIMIT and d["context_selection_trace"].get("max_characters", EVIDENCE_CHARACTER_LIMIT) <= EVIDENCE_CHARACTER_LIMIT,
                   selected_characters=selected, limit=EVIDENCE_CHARACTER_LIMIT)
        self.check("packet_smaller_than_full_history", d["measured_packet"]["utf8_bytes"] < history["export_response_bytes"] and d["measured_packet"]["utf8_bytes"] < history["events_serialized"]["utf8_bytes"],
                   packet_bytes=d["measured_packet"]["utf8_bytes"], export_bytes=history["export_response_bytes"], events_bytes=history["events_serialized"]["utf8_bytes"])
        self.check("bounded_retrieval_smaller_than_full_history", bounded_bytes < history["export_response_bytes"], bounded_bytes=bounded_bytes, export_bytes=history["export_response_bytes"])

        c = results["recall_chain_only"]
        transitive = any(ref["id_anywhere_in_packet"] for ref in c["origin_references"])
        self.report["findings"] = [{
            "id": "transitive_older_evidence", "measured": True,
            "status": "supported" if transitive else "unsupported",
            "detail": "Origin evidence IDs appeared in the chain-only packet." if transitive else
                      "With only the dependency chain, the recall packet contained no origin evidence ID (inline or omitted). Older evidence is reachable only through a declared dependency or exact-ID lookup (worker.py:43-49).",
            "affects_acceptance": False,
        }]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8014)
    parser.add_argument("--intervening", type=int, default=MAX_TASKS - 3, help="Chained intervening tasks (1..21)")
    parser.add_argument("--timeout", type=float, default=240.0, help="Seconds to wait per process phase")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "safe_harbor" / "history-e2e" / str(int(time.time())))
    args = parser.parse_args()
    sys.exit(0 if HistoryJourney(args.port, args.output, args.intervening, args.timeout).execute() else 1)

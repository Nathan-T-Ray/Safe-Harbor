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
       recall_declared   depends on [origin, last intervening]
       recall_chain_only depends on [last intervening] only (transitive ancestry)
  2. Process 1 (uvicorn API) executes origin and all intervening tasks, then dies
     via SAFE_HARBOR_CRASH_AFTER_ACCEPT immediately after the last intervening
     task is accepted (exit 86; coordinator.py).
  3. Process 2 (fresh) reclaims the run with a new epoch and executes the recall
     tasks. Their worker_trace artifacts record the actual context packet.
  4. Process 3 (fresh) reads the recorded packets, rebuilds them through
     GET /runs/{id}/tasks/{task}/context, and retrieves every origin evidence
     artifact through the task-scoped GET /runs/{id}/tasks/{task}/evidence/{artifact_id}
     (pointer/offset/limit paging), comparing it with GET /runs/{id}/artifacts/{id}.

Acceptance (both recall tasks): the packet carries the original objective; every
origin evidence artifact appears in evidence_manifest with its original ID, kind,
revision and content_hash, and is either an inline bounded summary carrying the
original's content_hash (context.compact_artifact; the summary is NOT re-hashed) or
an omitted ID; the original reconstructed from the task evidence endpoint is equal
to the /artifacts record and digest(reconstruction) == content_hash; the whole
serialized packet (worker.py measure) is <= context_limit_bytes == 60000 and smaller
than the full export. Measured sizes are written to report.json. Exit status is
nonzero on any failed check.
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
import urllib.parse
import urllib.request
from pathlib import Path

from safe_harbor.runtime.compiler import MAX_TASKS, compile_harness
from safe_harbor.runtime.ledger import Ledger, digest, identifier, now
from safe_harbor.science import get_catalog

from shared.contracts import Budget, Run

ROOT = Path(__file__).resolve().parents[2]
# Code-defined bounds (re-read at authoring time):
#   worker.py build_context_packet: whole packet json.dumps(packet, ensure_ascii=False).encode() <= 60000,
#     then packet["context_limit_bytes"] = 60000; evidence selection max_characters=28000.
#   context.py retrieve: limit 1..20 for list slices; a selected value > 24000 UTF-8 bytes returns
#     status narrower_pointer_required (available_keys for objects, total_items for arrays).
PACKET_BYTE_LIMIT = 60000
EVIDENCE_CHARACTER_LIMIT = 28000
RETRIEVAL_PAGE_LIMIT = 20
CRASH_EXIT = 86  # coordinator.py: os._exit(86) after durable acceptance
OBJECTIVE = "SH-Q10 operational history E2E: keep the original objective and exact older evidence reachable from bounded context after restart. No biological inference or model execution."
INTERVENING_TOOLS = ["list_evidence", "table_slice", "expression_comparison", "control_overlap", "gene_proximity", "reference_sequence"]

# Static source observations (not measured); re-checked against the source at authoring time.
CODE_FINDINGS = [
    {"id": "task_outputs_not_discoverable_by_bounded_api", "where": "backend/safe_harbor/api.py:149-176; backend/safe_harbor/runtime/context.py:13-26",
     "observation": "The task context/evidence endpoints expose a task's ancestor manifest, but no bounded endpoint returns a task document (status, epoch, result_artifact_ids). worker_trace artifacts are excluded from manifests. This E2E reads single task documents from MongoDB for those fields only (labeled mongo_task_read)."},
    {"id": "packet_bound_measured_before_limit_field", "where": "backend/safe_harbor/runtime/worker.py:82-86",
     "observation": "The 60000-byte whole-packet check runs before context_limit_bytes is added, so the delivered packet is that field's size larger than the measured value; the E2E measures both."},
    {"id": "selection_trace_not_updated_after_packet_trim", "where": "backend/safe_harbor/runtime/worker.py:67,82-83",
     "observation": "If the 60000-byte loop moves evidence to omitted_artifact_ids, context_selection_trace still lists the pre-trim included IDs. Not exercised when the packet fits."},
    {"id": "context_characters_uses_ascii_escaped_length", "where": "backend/safe_harbor/runtime/worker.py:319",
     "observation": "worker_trace.context_characters is len(json.dumps(packet)) (ASCII-escaped characters), not the UTF-8 byte measure used for the bound."},
]


def role(role_id: str, kind: str, tools: list[str], depends_on: list[str], question: str) -> dict:
    return {"role_id": role_id, "kind": kind, "question": question, "depends_on": depends_on, "allowed_tools": tools,
            "max_tool_calls": len(tools), "context_policy": "relevant_evidence",
            "instructions": "Explicit mock harness for deterministic operational history E2E only; no model interpretation."}


def size(value) -> dict:
    # characters: ASCII-escaped json.dumps length (as worker_trace.context_characters); utf8_bytes: worker.py bound measure.
    return {"characters": len(json.dumps(value)), "utf8_bytes": len(json.dumps(value, ensure_ascii=False).encode("utf-8"))}


def packet_measure(packet: dict) -> int:
    # Exactly worker.py build_context_packet's bound measure.
    return len(json.dumps(packet, ensure_ascii=False).encode())


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
        roles.append(role("recall_chain_only", "compute_features", [], [previous], "Recall the older origin evidence after restart through transitive ancestry only (no declared dependency)."))
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
        # mongo_task_read: one materialized task document (bounded; not a history replay).
        # The API has no bounded task-document endpoint (see CODE_FINDINGS).
        return self.ledger.db.tasks.find_one({"run_id": self.report["run_id"], "task_id": task_id}, {"_id": 0})

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
        body = self.raw(f"/runs/{run_id}/artifacts/{urllib.parse.quote(artifact_id, safe='')}")
        return json.loads(body), len(body)

    def evidence_page(self, run_id: str, task_id: str, artifact_id: str, pointer: str, offset: int, limit: int, stats: dict) -> dict:
        query = urllib.parse.urlencode({"pointer": pointer, "offset": offset, "limit": limit})
        body = self.raw(f"/runs/{run_id}/tasks/{urllib.parse.quote(task_id, safe='')}/evidence/{urllib.parse.quote(artifact_id, safe='')}?{query}")
        stats["requests"] += 1
        stats["response_bytes"] += len(body)
        page = json.loads(body)
        stats["hashes"].add(page.get("content_hash"))
        if "revision" in page:
            stats["revisions"].add(page["revision"])
        return page

    def reconstruct(self, run_id: str, task_id: str, artifact_id: str, pointer: str, stats: dict):
        """Rebuild the value at pointer exactly as context.retrieve defines it.

        retrieve() returns an object/scalar subtree whole (offset/limit ignored), an array as
        data[offset:offset+limit] with total_items, and narrower_pointer_required when the
        selected value exceeds 24000 UTF-8 bytes (available_keys for objects, total_items for
        arrays). A single scalar above that bound cannot be returned; it is recorded, not faked.
        """
        page = self.evidence_page(run_id, task_id, artifact_id, pointer, 0, RETRIEVAL_PAGE_LIMIT, stats)
        status = page.get("status")
        if status == "missing_subtree":
            raise AssertionError(f"retrieve reported missing_subtree at {pointer!r}")
        if status is None and page.get("total_items") is None:
            return page["data"]
        if status == "narrower_pointer_required" and page.get("total_items") is None:
            if page.get("available_keys"):
                return {key: self.reconstruct(run_id, task_id, artifact_id, f"{pointer}/{key.replace('~', '~0').replace('/', '~1')}", stats) for key in page["available_keys"]}
            stats["unretrievable_pointers"].append(pointer)
            return None
        total, items, offset, limit = page["total_items"], [], 0, RETRIEVAL_PAGE_LIMIT
        while offset < total:
            if page is None:
                page = self.evidence_page(run_id, task_id, artifact_id, pointer, offset, limit, stats)
            if page.get("status") == "narrower_pointer_required":
                if limit > 1:
                    limit, page = max(1, limit // 2), None
                    continue
                items.append(self.reconstruct(run_id, task_id, artifact_id, f"{pointer}/{offset}", stats))
                offset += 1
            else:
                if page["total_items"] != total or not page["data"]:
                    raise AssertionError(f"Inconsistent array paging at {pointer!r} offset {offset}")
                items.extend(page["data"])
                offset += len(page["data"])
            page = None
        return items

    def retrieve_original(self, run_id: str, task_id: str, artifact_id: str) -> tuple[object, dict]:
        stats = {"requests": 0, "response_bytes": 0, "hashes": set(), "revisions": set(), "unretrievable_pointers": [], "http_error": None}
        try:
            data = self.reconstruct(run_id, task_id, artifact_id, "", stats)
        except urllib.error.HTTPError as exc:
            data, stats["http_error"] = None, f"{exc.code}: {exc.read().decode(errors='replace')[:300]}"
        stats["hashes"], stats["revisions"] = sorted(item for item in stats["hashes"] if item), sorted(stats["revisions"])
        return data, stats

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

        # Process 3: fresh process; bounded, task-scoped retrieval only.
        self.start()
        origin_evidence = []
        originals = {}
        artifact_bytes = 0
        for artifact_id in origin["result_artifact_ids"]:  # IDs from mongo_task_read (no bounded API for task outputs)
            record, length = self.artifact(run_id, artifact_id)
            if record["kind"] == "worker_trace":
                continue
            artifact_bytes += length
            originals[artifact_id] = record
            origin_evidence.append({"artifact_id": artifact_id, "kind": record["kind"], "revision": record["revision"], "tool_name": record["data"].get("tool_name"),
                                    "provenance_task_id": record["provenance"]["task_id"], "content_hash": record["content_hash"],
                                    "hash_verified": digest(record["data"]) == record["content_hash"], "artifacts_endpoint_bytes": length})
        self.check("origin_evidence_exists_and_hashes_verify", bool(origin_evidence) and all(item["hash_verified"] and item["provenance_task_id"] == ids["origin"] for item in origin_evidence), origin_evidence=origin_evidence)
        traces = {name: self.trace_of(run_id, ids[name]) for name in ("recall_declared", "recall_chain_only")}

        recall = {}
        for name in ("recall_declared", "recall_chain_only"):
            task_id = ids[name]
            context_body = self.raw(f"/runs/{run_id}/tasks/{urllib.parse.quote(task_id, safe='')}/context", timeout=60)
            retrievals = {}
            for artifact_id in originals:
                data, stats = self.retrieve_original(run_id, task_id, artifact_id)
                retrievals[artifact_id] = (data, stats)
            recall[name] = {"context_body": context_body, "retrievals": retrievals}

        # Scope control: a task's own outputs are not in its ancestor manifest (context.py available_artifacts).
        scope_probe = None
        try:
            self.evidence_page(run_id, ids["origin"], next(iter(originals)), "", 0, 1, {"requests": 0, "response_bytes": 0, "hashes": set(), "revisions": set()})
        except urllib.error.HTTPError as exc:
            scope_probe = exc.code
        self.check("evidence_endpoint_is_task_scoped", scope_probe == 403, origin_task_retrieving_own_output_status=scope_probe)

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

        run_limit = (run.get("model_settings") or {}).get("context_limit_bytes")
        results = {}
        bounded_bytes = artifact_bytes
        for name in ("recall_declared", "recall_chain_only"):
            trace, trace_bytes = traces[name]
            packet = trace["data"]["context_packet"]
            packet_bytes = packet_measure(packet)
            # worker.py measures before adding context_limit_bytes; reproduce that exact measure too.
            measured_before_limit = packet_measure({key: value for key, value in packet.items() if key != "context_limit_bytes"})
            rebuilt = json.loads(recall[name]["context_body"])
            manifest = {item["artifact_id"]: item for item in packet.get("evidence_manifest", [])}
            rebuilt_manifest = {item["artifact_id"]: item for item in rebuilt.get("evidence_manifest", [])}
            included = {item["artifact_id"]: item for item in packet["evidence"]}
            omitted = set(packet["omitted_artifact_ids"])
            references = []
            for artifact_id, original in originals.items():
                entry, inline = manifest.get(artifact_id), included.get(artifact_id)
                data, stats = recall[name]["retrievals"][artifact_id]
                bounded_bytes += stats["response_bytes"]
                identity = {"artifact_id": artifact_id, "kind": original["kind"], "content_hash": original["content_hash"], "revision": original["revision"]}
                exact = (data is not None and not stats["unretrievable_pointers"] and stats["http_error"] is None
                         and digest(data) == original["content_hash"] and data == original["data"]
                         and json.dumps(data, ensure_ascii=False) == json.dumps(original["data"], ensure_ascii=False))
                references.append({
                    "artifact_id": artifact_id, "tool_name": original["data"].get("tool_name"),
                    "manifest_identity_matches": entry == identity, "rebuilt_manifest_identity_matches": rebuilt_manifest.get(artifact_id) == identity,
                    "inline": inline is not None, "omitted": artifact_id in omitted,
                    # Inline entries are compact_artifact summaries: their content_hash names the immutable original.
                    "inline_hash_is_original": inline is not None and inline["artifact_id"] == artifact_id and inline["content_hash"] == original["content_hash"] and inline.get("revision") == original["revision"],
                    "inline_representation": inline.get("context_representation") if inline else None,
                    "inline_data_is_summary": inline is not None and digest(inline["data"]) != original["content_hash"],
                    "retrieval_requests": stats["requests"], "retrieval_response_bytes": stats["response_bytes"],
                    "retrieval_reported_hashes": stats["hashes"], "retrieval_reported_revisions": stats["revisions"],
                    "unretrievable_pointers": stats["unretrievable_pointers"], "http_error": stats["http_error"],
                    "retrieved_hash_and_revision_match": stats["hashes"] == [original["content_hash"]] and stats["revisions"] in ([], [original["revision"]]),
                    "retrieved_exact_original": exact,
                })
            differing = sorted(key for key in set(packet) | set(rebuilt) if packet.get(key) != rebuilt.get(key))
            results[name] = {
                "task_id": ids[name], "worker_trace_artifact_id": trace["artifact_id"], "worker_trace_retrieval_bytes": trace_bytes,
                "recorded_context_characters": trace["data"]["context_characters"], "measured_packet": size(packet),
                "packet_utf8_bytes": packet_bytes, "packet_utf8_bytes_before_limit_field": measured_before_limit,
                "context_limit_bytes": packet.get("context_limit_bytes"), "run_model_settings_context_limit_bytes": run_limit,
                "evidence_serialized": size(packet["evidence"]), "evidence_count": len(packet["evidence"]), "omitted_count": len(omitted),
                "manifest_count": len(manifest), "context_selection_trace": packet.get("context_selection_trace", {}),
                "objective_present": packet.get("objective") == OBJECTIVE, "origin_references": references,
                "rebuilt_context_endpoint_bytes": len(recall[name]["context_body"]), "rebuilt_packet_utf8_bytes": packet_measure(rebuilt),
                "rebuilt_context_limit_bytes": rebuilt.get("context_limit_bytes"), "rebuilt_differing_keys": differing,
                "rebuilt_evidence_identity_matches": [(item["artifact_id"], item["content_hash"]) for item in rebuilt["evidence"]] == [(item["artifact_id"], item["content_hash"]) for item in packet["evidence"]]
                and rebuilt["omitted_artifact_ids"] == packet["omitted_artifact_ids"] and rebuilt_manifest == manifest,
                "packet_to_export_ratio": round(packet_bytes / len(export_bytes), 4),
            }
            bounded_bytes += trace_bytes
        self.report["context_packets"] = results
        self.report["bounded_retrieval_bytes"] = bounded_bytes

        self.check("original_objective_in_packets", all(item["objective_present"] for item in results.values()) and self.ledger.get_run(run_id)["objective"] == OBJECTIVE)
        for name, item in results.items():
            refs = item["origin_references"]
            selected = item["context_selection_trace"].get("selected_characters", item["context_selection_trace"].get("characters"))
            self.check(f"{name}_context_characters_recorded_matches_packet", item["recorded_context_characters"] == item["measured_packet"]["characters"])
            self.check(f"{name}_origin_ids_and_hashes_in_manifest", all(ref["manifest_identity_matches"] for ref in refs),
                       manifest_count=item["manifest_count"], origin_ids=[ref["artifact_id"] for ref in refs])
            self.check(f"{name}_origin_inline_or_omitted_by_original_hash", all(ref["inline_hash_is_original"] != ref["omitted"] for ref in refs),
                       inline=sum(ref["inline_hash_is_original"] for ref in refs), omitted=sum(ref["omitted"] for ref in refs))
            self.check(f"{name}_origin_retrieved_exactly_via_task_evidence_endpoint", all(ref["retrieved_hash_and_revision_match"] and ref["retrieved_exact_original"] for ref in refs),
                       requests=sum(ref["retrieval_requests"] for ref in refs), response_bytes=sum(ref["retrieval_response_bytes"] for ref in refs),
                       unretrievable_pointers={ref["artifact_id"]: ref["unretrievable_pointers"] for ref in refs if ref["unretrievable_pointers"]},
                       http_errors={ref["artifact_id"]: ref["http_error"] for ref in refs if ref["http_error"]})
            self.check(f"{name}_whole_packet_within_60kb_bound",
                       item["context_limit_bytes"] == PACKET_BYTE_LIMIT and run_limit in (None, PACKET_BYTE_LIMIT)
                       and item["packet_utf8_bytes_before_limit_field"] <= PACKET_BYTE_LIMIT and item["packet_utf8_bytes"] <= PACKET_BYTE_LIMIT,
                       packet_bytes=item["packet_utf8_bytes"], measured_before_limit_field=item["packet_utf8_bytes_before_limit_field"],
                       context_limit_bytes=item["context_limit_bytes"], run_context_limit_bytes=run_limit)
            self.check(f"{name}_evidence_selection_within_code_bound", selected is not None and selected <= EVIDENCE_CHARACTER_LIMIT and item["context_selection_trace"].get("max_characters", EVIDENCE_CHARACTER_LIMIT) <= EVIDENCE_CHARACTER_LIMIT,
                       selected_characters=selected, limit=EVIDENCE_CHARACTER_LIMIT)
            self.check(f"{name}_packet_smaller_than_full_history", item["packet_utf8_bytes"] < history["export_response_bytes"] and item["packet_utf8_bytes"] < history["events_serialized"]["utf8_bytes"],
                       packet_bytes=item["packet_utf8_bytes"], export_bytes=history["export_response_bytes"], events_bytes=history["events_serialized"]["utf8_bytes"])
            self.check(f"{name}_context_endpoint_matches_recorded_packet",
                       item["rebuilt_evidence_identity_matches"] and item["rebuilt_packet_utf8_bytes"] <= PACKET_BYTE_LIMIT and item["rebuilt_context_limit_bytes"] == PACKET_BYTE_LIMIT
                       and all(ref["rebuilt_manifest_identity_matches"] for ref in refs) and set(item["rebuilt_differing_keys"]) <= {"remaining_budget"},
                       rebuilt_packet_bytes=item["rebuilt_packet_utf8_bytes"], differing_keys=item["rebuilt_differing_keys"])
        self.check("bounded_retrieval_smaller_than_full_history", bounded_bytes < history["export_response_bytes"], bounded_bytes=bounded_bytes, export_bytes=history["export_response_bytes"])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8014)
    parser.add_argument("--intervening", type=int, default=MAX_TASKS - 3, help="Chained intervening tasks (1..21)")
    parser.add_argument("--timeout", type=float, default=240.0, help="Seconds to wait per process phase")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "safe_harbor" / "history-e2e" / str(int(time.time())))
    args = parser.parse_args()
    sys.exit(0 if HistoryJourney(args.port, args.output, args.intervening, args.timeout).execute() else 1)

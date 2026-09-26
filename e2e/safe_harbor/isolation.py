#!/usr/bin/env python3
"""SH-Q06 E2E: answer-key, evidence-retrieval and artifact-manifest isolation.

Run from the repository root against a transaction-capable MongoDB:
  PYTHONPATH=backend:. .venv/bin/python e2e/safe_harbor/isolation.py [--port 8022]

Mode: deterministic_operational. No model is called. Every observation is made
through a real uvicorn API process (safe_harbor.api:app) backed by an isolated
MongoDB database: the script only issues HTTP requests and reads MongoDB
documents to discover IDs and inspect recorded operations. It does not import or
call runtime, science, harness or evaluation functions.

Journeys:
  * three deterministic runs (A, B, C) executed by the coordinator and the
    scored worker; run C then receives the prepared withhold-control-evidence
    revision through POST /runs/{run}/evidence-revisions and re-executes;
  * GET /runs/{run}/tasks/{task}/context for every task of every run;
  * GET /runs/{run}/tasks/{task}/evidence/{artifact}: valid ancestor retrieval
    (positive control), same-run non-ancestors, other runs' artifacts, other
    runs' task IDs, evaluator-path / traversal / NoSQL-shaped artifact IDs and
    pointers, offset/limit bounds, and pre-revision (withheld-control) versions;
  * GET /runs/{run}/artifacts/{artifact} run scoping;
  * POST /runs/{run}/assessment-validation citation boundaries;
  * forged POST /runs, /experiments and /evidence-revisions bodies;
  * evaluator-only marker scans over every HTTP body collected above.

Every attempt records expected versus observed outcome and the code boundary it
relies on. Exit status is nonzero if any attempt fails.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from pymongo import MongoClient

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # the API loads .env itself; the script only needs MONGODB_URI
    load_dotenv = None

ROOT = Path(__file__).resolve().parents[2]
EVALUATOR = ROOT / "data" / "safe_harbor" / "evaluator"
EVALUATOR_SOURCE = ROOT / "backend" / "safe_harbor" / "evaluation" / "reference_answers.py"
REFERENCE_PATH = "data/safe_harbor/evaluator/reference_answers.json"
SPLITS_PATH = "data/safe_harbor/evaluator/splits.json"
# Same default as backend/safe_harbor/runtime/ledger.py:39 (Ledger.__init__).
DEFAULT_MONGODB_URI = "mongodb://127.0.0.1:27021/?replicaSet=safe-harbor-dev"
# Run C re-executes five tasks after the revision; same assigned budget as e2e/safe_harbor/context_assessment_export.py.
REVISION_BUDGET = {"token_limit": 60000, "tool_limit": 80, "cost_limit_usd": 5}
SOURCE_KINDS = {"reference_assets", "source_manifest"}  # frozen by api.py create_run, not worker output
RETRIEVAL_DENIED = "Artifact is outside the task's same-run ancestor manifest"
TASK_OUTSIDE_RUN = "Task is outside this run or does not exist."

# Evaluator-only record keys (data/safe_harbor/evaluator/*, safe_harbor.evaluation.reference_answers.load_reference,
# evaluation/scoring.py). Verified absent from runtime/science/harness/api/shared sources and normalized data.
# Deliberately NOT markers: exclusion_decision and its enum values, limitation codes (evaluation LIM), public
# case IDs / scenario IDs, runtime_tools, evidence_manifest, case_context: these are worker output/assignment
# contracts that legitimately appear in contexts, assessments and exports.
ANSWER_KEY_FIELDS = (
    "required_numbers", "independent_diagnostics", "reference_method", "review_status", "human_reviewed",
    "rubric_notes", "required_decisions", "required_limitations", "unavailable_numbers", "reference_review_status",
)
SPLIT_FIELDS = ("split_hash", "promotion_rule")

ARTIFACT_ID_ATTACKS = [
    "..%2F..%2F..%2F" + urllib.parse.quote(REFERENCE_PATH, safe=""), "../../catalog", "..%2F..%2Fexport",
    "%2E%2E%2F%2E%2E%2Fcontext", urllib.parse.quote(SPLITS_PATH, safe=""),
    urllib.parse.quote("{\"$ne\":null}", safe=""), urllib.parse.quote("{\"$gt\":\"\"}", safe=""),
    urllib.parse.quote(".*", safe=""), "reference_answers", "reference_answers.json", "splits", "splits.json",
    "evaluator-only-private-fixture", "artifact-" + "0" * 32,
]
POINTER_ATTACKS = [
    "../../" + REFERENCE_PATH, REFERENCE_PATH, "/../../" + REFERENCE_PATH, "/" + SPLITS_PATH, "{\"$ne\":null}",
    "/$where", "/__class__/__init__/__globals__", "file://" + str(EVALUATOR / "reference_answers.json"), "/..",
    "\\..\\evaluator\\splits.json",
]
BOUND_ATTACKS = [{"limit": "0"}, {"limit": "21"}, {"offset": "-1"}, {"offset": "x"}, {"limit": "1e9"}]


def digest(value) -> str:
    """Independent re-implementation of runtime/ledger.py:23 digest (canonical JSON sha256)."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def q(value: str) -> str:
    return urllib.parse.quote(value, safe=":")


def only_detail(body) -> bool:
    return isinstance(body, dict) and bool(body) and set(body) <= {"detail", "errors"}


def expected_manifest(snapshot: dict, task: dict) -> list[str]:
    """Documented contract (runtime/context.py:1,13-26): the run's frozen reference/source-manifest plus results of
    transitively completed ancestors in the same run, excluding worker traces. Computed from the HTTP snapshot."""
    run_id = snapshot["run"]["run_id"]
    tasks = {item["task_id"]: item for item in snapshot["tasks"]}
    artifacts = {item["artifact_id"]: item for item in snapshot["artifacts"]}
    ids = [f"{run_id}:reference:{task['candidate_id']}", f"{run_id}:source-manifest"]
    frontier, visited = list(task["depends_on"]), set()
    while frontier:
        parent_id = frontier.pop(0)
        if parent_id in visited:
            continue
        visited.add(parent_id)
        parent = tasks.get(parent_id)
        if parent and parent["status"] == "complete":
            frontier.extend(parent["depends_on"])
            ids.extend(parent.get("result_artifact_ids", []))
    return [key for key in dict.fromkeys(ids) if key in artifacts and artifacts[key]["kind"] != "worker_trace"]


class Isolation:
    def __init__(self, port: int, output: Path, timeout: float):
        self.port = port
        self.base = f"http://127.0.0.1:{port}"
        self.output = output
        self.output.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.database = f"safe_harbor_isolation_{int(time.time())}"
        if load_dotenv:
            load_dotenv(ROOT / ".env", override=False)
        self.client = MongoClient(os.getenv("MONGODB_URI") or DEFAULT_MONGODB_URI, serverSelectionTimeoutMS=5000, tz_aware=True)
        self.db = self.client[self.database]
        self.process = None
        self.log = None
        self.processes = []
        self.attempts = []
        self.surfaces: dict[str, list[str]] = {}
        self.runs: dict[str, dict] = {}
        self.candidate_ids: list[str] = []
        self.report = {
            "ticket": "SH-Q06", "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "database": self.database,
            "mode": "deterministic_operational",
            "harness": "frozen baseline harness selected by POST /runs without harness_hash",
            "interfaces": "HTTP to a real uvicorn safe_harbor.api:app process + MongoDB document reads; no in-process runtime/science/harness/evaluation calls",
            "model_calls_made_by_this_script": 0, "processes": self.processes, "attempts": self.attempts,
            "not_exercised": [], "findings": [], "limitations": [],
        }

    # ----------------------------------------------------------------- recording
    def record(self, attempt_id, category, interface, boundary, expected, observed, passed):
        self.attempts.append({"attempt_id": attempt_id, "category": category, "interface": interface,
                              "boundary": boundary, "expected": expected, "observed": observed, "passed": bool(passed)})
        return passed

    def check(self, attempt_id, category, interface, boundary, expected, call):
        """call() returns (passed, observed)."""
        try:
            passed, observed = call()
        except Exception as exc:  # noqa: BLE001 - any error is recorded as a failed attempt
            passed, observed = False, {"outcome": "error", "exception": type(exc).__name__, "message": str(exc)[:400], "traceback": traceback.format_exc()[-1500:]}
        return self.record(attempt_id, category, interface, boundary, expected, observed, passed)

    def section(self, name, function):
        try:
            function()
        except Exception as exc:  # noqa: BLE001 - a broken section is recorded as a failure, later sections still run
            self.record(f"section-error:{name}", "journey", name, "journey must execute to produce evidence", "section completes",
                        {"outcome": "error", "exception": type(exc).__name__, "message": str(exc)[:400], "traceback": traceback.format_exc()[-2000:]}, False)

    # ------------------------------------------------------------------ process
    def http(self, method: str, path: str, body=None, surface: str | None = None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base + path, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as exc:
            status, raw = exc.code, exc.read()
        text = raw.decode("utf-8", "replace")
        try:
            parsed = json.loads(text)
        except ValueError:
            parsed = text
        if surface:
            self.surfaces.setdefault(surface, []).append(text)
        return status, parsed, text

    def request(self, method: str, path: str, body=None, expected=200, surface: str | None = None):
        status, parsed, text = self.http(method, path, body, surface)
        if status != expected:
            raise AssertionError(f"{method} {path} returned {status} (expected {expected}): {text[:300]}")
        return parsed

    def start(self):
        env = dict(os.environ, PYTHONPATH=f"{ROOT / 'backend'}:{ROOT}", MONGODB_DATABASE=self.database)
        for key in list(env):
            if key.startswith(("SAFE_HARBOR_CRASH_", "SAFE_HARBOR_OPERATIONAL_")):
                env.pop(key)
        path = self.output / f"process-{len(self.processes) + 1}.log"
        self.log = path.open("w")
        self.process = subprocess.Popen([sys.executable, "-m", "uvicorn", "safe_harbor.api:app", "--host", "127.0.0.1", "--port", str(self.port)],
                                        cwd=ROOT, env=env, stdout=self.log, stderr=subprocess.STDOUT)
        self.processes.append({"pid": self.process.pid, "log": str(path), "port": self.port})
        until = time.monotonic() + 25
        while time.monotonic() < until:
            if self.process.poll() is not None:
                raise AssertionError(f"API process exited {self.process.returncode}; inspect {path}")
            try:
                status, body, _ = self.http("GET", "/health")
                if status == 200 and body.get("database") == self.database:
                    if not body.get("coordinator_available"):
                        raise AssertionError("API started without a coordinator; the scored worker cannot run")
                    self.processes[-1]["health"] = body
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
        if self.log:
            self.log.close()
        self.process = None
        self.log = None

    def wait_run(self, run_id: str) -> dict:
        until = time.monotonic() + self.timeout
        while time.monotonic() < until:
            snapshot = self.request("GET", f"/runs/{q(run_id)}/snapshot")
            status = snapshot["run"]["status"]
            if status == "complete":
                return snapshot
            if status in ("blocked", "budget_exhausted", "failed"):
                raise AssertionError(f"Run {run_id} stopped as {status}: {snapshot['run'].get('stop_reason')}")
            time.sleep(0.2)
        raise AssertionError(f"Run did not complete within {self.timeout}s: {run_id}")

    def evidence_path(self, run_id, task_id, artifact_id, raw=False, query=None):
        path = f"/runs/{q(run_id)}/tasks/{q(task_id)}/evidence/{artifact_id if raw else q(artifact_id)}"
        return path + ("?" + urllib.parse.urlencode(query) if query else "")

    # --------------------------------------------------------------- 1. runs
    def api_runs(self):
        self.start()
        catalog = self.request("GET", "/catalog", surface="catalog")
        self.candidate_ids = [candidate["candidate_id"] for candidate in catalog["candidates"]]
        plan = (("A", self.candidate_ids[0], None), ("B", self.candidate_ids[1], None), ("C", self.candidate_ids[0], REVISION_BUDGET))
        for label, cid, budget in plan:
            body = {"candidate_ids": [cid], "mode": "deterministic", **({"budget": budget} if budget else {})}
            created = self.request("POST", "/runs", body, expected=201)
            self.runs[label] = {"run_id": created["run_id"], "candidate_id": cid}
        for label, info in self.runs.items():
            info["initial"] = self.wait_run(info["run_id"])
            self.surfaces.setdefault(f"snapshot:{label}", []).append(json.dumps(info["initial"], ensure_ascii=False))
            self.completion(label, info)
        info = self.runs["C"]
        status, revision, text = self.http("POST", f"/runs/{q(info['run_id'])}/evidence-revisions", {"fixture_id": "withhold-control-evidence"}, surface="revision:C")
        info["revision"] = {"status": status, "body": revision}
        if status != 200:
            raise AssertionError(f"withhold-control-evidence revision returned {status}: {text[:300]}")
        info["final"] = self.wait_run(info["run_id"])
        self.runs["A"]["final"] = self.request("GET", f"/runs/{q(self.runs['A']['run_id'])}/snapshot")
        self.runs["B"]["final"] = self.request("GET", f"/runs/{q(self.runs['B']['run_id'])}/snapshot")
        for label, info in self.runs.items():
            self.surfaces.setdefault(f"snapshot:{label}", []).append(json.dumps(info["final"], ensure_ascii=False))
            self.request("GET", f"/runs/{q(info['run_id'])}/events", surface=f"events:{label}")

    def completion(self, label, info):
        def verify():
            snapshot, cid = info["initial"], info["candidate_id"]
            run = snapshot["run"]
            run_id = run["run_id"]
            artifacts = {artifact["artifact_id"]: artifact for artifact in snapshot["artifacts"]}
            harness = next((item for item in snapshot["harness_versions"] if item["harness_hash"] == run["harness_hash"]), None)
            roles = sorted(role["role_id"] for role in harness["roles"]) if harness else None
            produced_by = {artifact_id: task["task_id"] for task in snapshot["tasks"] for artifact_id in task.get("result_artifact_ids", [])}
            problems, per_task = [], {}
            if run["status"] != "complete" or run["mode"] != "deterministic":
                problems.append(f"run status/mode {run['status']}/{run['mode']}")
            if run["budget"]["model_calls"] != 0 or run["budget"]["tokens_used"] != 0:
                problems.append("deterministic run recorded model usage")
            if roles is None or sorted(task["role_id"] for task in snapshot["tasks"]) != roles:
                problems.append("task roles differ from the run's recorded harness version")
            for task in snapshot["tasks"]:
                accepted = self.db.operations.count_documents({"run_id": run_id, "status": "accepted", "operation_id": {"$regex": "^" + re.escape(f"accept:{task['task_id']}:")}})
                produced = [artifacts[artifact_id] for artifact_id in task.get("result_artifact_ids", []) if artifact_id in artifacts]
                tools = [artifact["data"]["tool_name"] for artifact in produced if artifact["kind"] == "scientific_tool_result"]
                expected_tools = task["allowed_tools"][:task["budget"]["max_tool_calls"]]
                traces = [artifact for artifact in produced if artifact["kind"] == "worker_trace"]
                per_task[task["role_id"]] = {"status": task["status"], "accepted_operations": accepted, "tool_results": tools, "worker_traces": len(traces)}
                if task["status"] != "complete" or accepted < 1 or tools != expected_tools or len(traces) != 1:
                    problems.append(f"task {task['role_id']} incomplete, unaccepted, tool mismatch or trace count {len(traces)}")
                if len(produced) != len(task.get("result_artifact_ids", [])):
                    problems.append(f"task {task['role_id']} result artifacts missing from snapshot")
            # Adapter/trace fields exist only on worker-produced artifacts (runtime/worker.py _artifact); the
            # frozen reference_assets/source_manifest records created by api.py are checked separately.
            worker = {artifact_id: artifacts[artifact_id] for artifact_id in produced_by if artifact_id in artifacts}
            adapters = sorted({str(artifact["provenance"].get("adapter")) for artifact in worker.values()})
            bad_provenance = sorted(artifact_id for artifact_id, artifact in worker.items()
                                    if artifact["provenance"].get("adapter") != "deterministic_operational"
                                    or artifact["provenance"].get("task_id") != produced_by[artifact_id]
                                    or artifact["provenance"].get("model_id") is not None)
            traces = [artifact for artifact in worker.values() if artifact["kind"] == "worker_trace"]
            trace_adapters = sorted({str(artifact["data"].get("execution_adapter")) for artifact in traces})
            trace_model_calls = sum(artifact["data"].get("usage", {}).get("model_calls", 0) for artifact in traces)
            if adapters != ["deterministic_operational"] or bad_provenance or trace_adapters != ["deterministic_operational"] or trace_model_calls:
                problems.append("worker-produced artifact adapter/provenance mismatch")
            source = sorted(artifact_id for artifact_id, artifact in artifacts.items() if artifact["kind"] in SOURCE_KINDS)
            expected_source = sorted([f"{run_id}:reference:{candidate}" for candidate in run["candidate_ids"]] + [f"{run_id}:source-manifest"])
            if source != expected_source or set(source) & set(produced_by):
                problems.append("frozen source artifacts differ from the run's reference/source-manifest set")
            unowned = sorted(artifact_id for artifact_id, artifact in artifacts.items() if artifact_id not in produced_by and artifact["kind"] not in SOURCE_KINDS)
            hash_mismatch = sorted(artifact_id for artifact_id, artifact in artifacts.items() if digest(artifact["data"]) != artifact["content_hash"])
            if hash_mismatch:
                problems.append("artifact content_hash does not match its data")
            assessments = [item for item in snapshot["assessments"] if item["candidate_id"] == cid]
            if not assessments or any(item["screen_status"] not in ("pass", "fail", "incomplete") for item in assessments):
                problems.append("no accepted typed assessment")
            observed = {"run_id": run_id, "candidate_id": cid, "status": run["status"], "budget": run["budget"], "tasks": per_task,
                        "artifacts": len(artifacts), "worker_artifacts": len(worker), "worker_adapters": adapters,
                        "bad_worker_provenance": bad_provenance, "trace_execution_adapters": trace_adapters,
                        "frozen_source_artifacts": source, "artifacts_without_producing_task": unowned,
                        "content_hash_mismatches": hash_mismatch, "assessments": len(assessments), "problems": problems}
            return not problems, observed
        self.check(f"legitimate-run-{label}", "legitimate_task", "POST /runs (deterministic) -> coordinator -> scored worker -> ledger.accept; GET snapshot; Mongo operations",
                   "positive control: isolation boundaries still allow the scored worker's assigned work",
                   "run complete; every harness task accepted with its assigned tool results and one worker trace; worker-produced artifacts carry adapter deterministic_operational; frozen source artifacts are exactly reference+source-manifest; model_calls == 0", verify)

    def exports(self):
        for label, info in self.runs.items():
            status, export, text = self.http("GET", f"/runs/{q(info['run_id'])}/export", surface=f"export:{label}")
            path = self.output / f"{info['run_id']}.json"
            path.write_text(text)
            info["export"] = str(path)

            def verify(export=export, status=status, info=info):
                ok = status == 200 and isinstance(export, dict) and export["snapshot"] == info["final"]
                return ok, {"status": status, "snapshot_matches_final": ok, "export": info["export"]}
            self.check(f"export-{label}", "legitimate_task", "GET /runs/{id}/export", "runtime/ledger.py export reconstructs the current snapshot",
                       "200; export.snapshot equals GET snapshot", verify)

    # ----------------------------------------------- 2. forged request bodies
    def forged_requests(self):
        cid = self.candidate_ids[0]
        run_a = self.runs["A"]["run_id"]
        base = {"candidate_ids": [cid], "mode": "deterministic"}
        attempts = [
            ("runs-extra-allowed_tools", "POST", "/runs", {**base, "allowed_tools": ["load_reference", "read_file"]}, 422, "shared/contracts.py CreateRun extra='forbid'"),
            ("runs-extra-evidence_availability", "POST", "/runs", {**base, "evidence_availability": {cid: {"control_evidence": True}}}, 422, "shared/contracts.py CreateRun extra='forbid'"),
            ("runs-extra-harness-record", "POST", "/runs", {**base, "harness": {"roles": [{"role_id": "probe", "allowed_tools": ["load_reference"]}]}}, 422, "shared/contracts.py CreateRun extra='forbid'"),
            ("runs-unsaved-harness-hash", "POST", "/runs", {**base, "harness_hash": "0" * 64}, 404, "harness/__init__.py:34-35 only saved immutable harness versions"),
            ("runs-path-harness-hash", "POST", "/runs", {**base, "harness_hash": "../../" + REFERENCE_PATH}, 422, "harness/__init__.py:30-31 hex-64 hash check"),
            ("runs-budget-extra-key", "POST", "/runs", {**base, "budget": {"tool_limit": 40, "reference_answers": True}}, 422, "api.py:104-105 assigned budget keys only"),
            ("runs-candidate-evaluator-path", "POST", "/runs", {"candidate_ids": [REFERENCE_PATH], "mode": "deterministic"}, 422, "api.py:98-99 catalog candidate IDs only"),
            ("runs-candidate-case-id", "POST", "/runs", {"candidate_ids": [f"{cid}--full_sources"], "mode": "deterministic"}, 422, "api.py:98-99 catalog candidate IDs only"),
            ("runs-candidate-nosql", "POST", "/runs", {"candidate_ids": [{"$ne": None}], "mode": "deterministic"}, 422, "shared/contracts.py CreateRun candidate_ids: list[str]"),
            ("runs-mode-mock", "POST", "/runs", {**base, "mode": "mock"}, 422, "api.py:88-89 live runs are deterministic or real_model"),
            ("experiments-extra-harness", "POST", "/experiments", {"mode": "deterministic", "harness": {"roles": []}}, 422, "shared/contracts.py CreateExperiment extra='forbid'"),
            ("experiments-candidate-evaluator-path", "POST", "/experiments", {"mode": "deterministic", "candidate_ids": [REFERENCE_PATH]}, 422, "evaluation/runner.py:89-92 frozen case candidates only"),
            ("revision-unknown-fixture", "POST", f"/runs/{q(run_a)}/evidence-revisions", {"fixture_id": REFERENCE_PATH}, 422, "api.py:223-224 prepared fixtures only"),
            ("revision-extra-field", "POST", f"/runs/{q(run_a)}/evidence-revisions", {"fixture_id": "withhold-control-evidence", "candidate_id": cid}, 422, "shared/contracts.py EvidenceRevision extra='forbid'"),
        ]
        before = {"runs": self.db.runs.count_documents({}), "evaluations": self.db.evaluations.count_documents({}),
                  "run_a_through_sequence": self.db.runs.find_one({"run_id": run_a})["through_sequence"]}
        for attempt_id, method, path, body, expected_status, boundary in attempts:
            def call(method=method, path=path, body=body, expected_status=expected_status):
                status, parsed, text = self.http(method, path, body, surface="forged_requests")
                return status == expected_status and only_detail(parsed), {"status": status, "body": text[:300]}
            self.check(f"forged-{attempt_id}", "unapproved_request", f"{method} {path}", boundary,
                       f"HTTP {expected_status} with only an error detail", call)

        def nothing_created():
            run_a_record = self.db.runs.find_one({"run_id": run_a})
            after = {"runs": self.db.runs.count_documents({}), "evaluations": self.db.evaluations.count_documents({}),
                     "run_a_through_sequence": run_a_record["through_sequence"]}
            availability = run_a_record["evidence_availability"][cid]["control_evidence"]
            return after == before and availability is True, {"before": before, "after": after, "run_a_control_evidence": availability}
        self.check("forged-requests-created-nothing", "unapproved_request", "MongoDB runs/evaluations collections",
                   "rejected requests must not create runs, experiments or revisions", "counts and run A sequence unchanged; run A control evidence still available", nothing_created)
        self.report["not_exercised"].append("Unapproved tool names and prohibited harness patches: no API endpoint accepts tool names or harness records (POST /runs accepts only a saved harness_hash; POST /experiments accepts mode/candidate_ids). Only the forged bodies above were exercised; in-process execute_tool/run_tool/validate_harness probes were removed under the E2E-only rule.")

    # --------------------------------------------- 3. artifact endpoint
    def artifact_endpoint(self):
        run_a, run_b = self.runs["A"], self.runs["B"]
        a_ids = [artifact["artifact_id"] for artifact in run_a["final"]["artifacts"]]
        b_artifacts = run_b["final"]["artifacts"]
        b_ids = [artifact["artifact_id"] for artifact in b_artifacts if artifact["kind"] == "worker_trace"][:1] + \
                [artifact["artifact_id"] for artifact in b_artifacts if artifact["kind"] != "worker_trace"][:3]
        boundary = "backend/safe_harbor/api.py:159-165 run-scoped artifacts.find_one({run_id, artifact_id}) -> 404"

        def positive():
            status, body, _ = self.http("GET", f"/runs/{q(run_a['run_id'])}/artifacts/{q(a_ids[0])}", surface="artifact_endpoint")
            ok = status == 200 and body["artifact_id"] == a_ids[0] and body["run_id"] == run_a["run_id"]
            return ok, {"status": status, "artifact_id": body.get("artifact_id") if isinstance(body, dict) else None}
        self.check("artifact-in-run-positive-control", "legitimate_task", "GET /runs/{id}/artifacts/{artifact_id}", "positive control",
                   "200 with the run's own artifact", positive)

        def expect_404(attempt_id, path, note, statuses=(404,)):
            def call():
                status, body, text = self.http("GET", path, surface="artifact_endpoint")
                return status in statuses and only_detail(body), {"status": status, "body": text[:300]}
            self.check(attempt_id, "out_of_manifest_artifact", f"GET {path}", note or boundary, f"HTTP {'/'.join(map(str, statuses))}; only an error detail", call)

        for artifact_id in b_ids:
            expect_404(f"artifact-cross-run:{artifact_id}", f"/runs/{q(run_a['run_id'])}/artifacts/{q(artifact_id)}", None)
        expect_404("artifact-nonexistent", f"/runs/{q(run_a['run_id'])}/artifacts/artifact-{'0' * 32}", None)
        expect_404("artifact-unknown-run", f"/runs/run-{'0' * 32}/artifacts/{q(a_ids[0])}", "backend/safe_harbor/api.py:161 ledger.get_run -> LedgerError 404")
        for index, artifact_id in enumerate(ARTIFACT_ID_ATTACKS):
            expect_404(f"artifact-attack-{index:02d}", f"/runs/{q(run_a['run_id'])}/artifacts/{artifact_id}",
                       boundary + "; slash-bearing ids do not match the single-segment route", statuses=(400, 404))

    # ---------------------------------------- 4. task context endpoint
    def contexts(self):
        for label, info in self.runs.items():
            snapshot = info["final"]
            run = snapshot["run"]
            artifacts = {artifact["artifact_id"]: artifact for artifact in snapshot["artifacts"]}
            for task in snapshot["tasks"]:
                def verify(task=task, snapshot=snapshot, run=run, artifacts=artifacts, label=label):
                    status, body, text = self.http("GET", f"/runs/{q(run['run_id'])}/tasks/{q(task['task_id'])}/context", surface=f"contexts:{label}")
                    if status != 200:
                        return False, {"status": status, "body": text[:300]}
                    manifest = expected_manifest(snapshot, task)
                    listed = {item["artifact_id"]: item for item in body["evidence_manifest"]}
                    evidence = body["evidence"]
                    problems = []
                    if set(listed) != set(manifest):
                        problems.append("evidence_manifest differs from same-run completed-ancestor set")
                    if any(listed[key]["content_hash"] != artifacts[key]["content_hash"] or listed[key]["kind"] != artifacts[key]["kind"] for key in set(listed) & set(manifest)):
                        problems.append("manifest hash/kind differs from the stored artifact")
                    outside = sorted({item["artifact_id"] for item in evidence} - set(manifest)) + sorted(set(body["omitted_artifact_ids"]) - set(manifest))
                    if outside:
                        problems.append("evidence/omitted IDs outside the manifest")
                    if any(item.get("run_id") != run["run_id"] or item.get("kind") == "worker_trace" for item in evidence):
                        problems.append("foreign-run or worker_trace evidence")
                    if body["runtime_tools"] != ["retrieve_evidence"] or body["allowed_tools"] != task["allowed_tools"]:
                        problems.append("tool exposure differs from the task assignment")
                    if body["evidence_availability"] != run["evidence_availability"][task["candidate_id"]] or not isinstance(body["case_context"], dict):
                        problems.append("availability/case_context mismatch")
                    observed = {"task_id": task["task_id"], "task_status": task["status"], "manifest": len(listed), "expected_manifest": len(manifest),
                                "evidence": len(evidence), "omitted": len(body["omitted_artifact_ids"]), "outside_manifest": outside,
                                "allowed_tools": body["allowed_tools"], "runtime_tools": body["runtime_tools"],
                                "evidence_availability": body["evidence_availability"], "case_context_keys": sorted(body["case_context"]), "problems": problems}
                    return not problems, observed
                self.check(f"context:{label}:{task['task_id'].split(':', 1)[-1]}", "out_of_manifest_artifact", "GET /runs/{run}/tasks/{task}/context",
                           "api.py:168-175 -> runtime/worker.py build_context_packet; manifest from runtime/context.py:13-26 available_artifacts",
                           "200; evidence_manifest == same-run completed ancestors (+ frozen source); evidence/omitted within it; no worker traces; only assigned tools + retrieve_evidence",
                           verify)

    # ------------------------------------------ 5. evidence retrieval
    def retrieval(self):
        for label, info in self.runs.items():
            other_label = "B" if label == "A" else "A"
            self.retrieval_for(label, info["final"], self.runs[other_label]["final"], other_label)
        self.retrieval_attacks()

    def retrieval_for(self, label, snapshot, other, other_label):
        run_id = snapshot["run"]["run_id"]
        artifacts = {artifact["artifact_id"]: artifact for artifact in snapshot["artifacts"]}
        other_tasks = {task["role_id"]: task for task in other["tasks"] if task["status"] == "complete"}
        boundary = "api.py:178-190 -> runtime/context.py:46-52 retrieve: artifact_id must be in available_artifacts (same run, completed ancestors, no worker_trace) -> LedgerError 403"
        for task in snapshot["tasks"]:
            short = task["task_id"].split(":", 1)[-1]
            manifest = expected_manifest(snapshot, task)

            def ancestors(task=task, manifest=manifest):
                results, ok = {}, bool(manifest)
                for artifact_id in manifest:
                    stored = artifacts[artifact_id]
                    status, body, _ = self.http("GET", self.evidence_path(run_id, task["task_id"], artifact_id), surface=f"evidence_allowed:{label}")
                    entry = {"status": status, "kind": stored["kind"]}
                    good = (status == 200 and isinstance(body, dict) and body.get("artifact_id") == artifact_id
                            and body.get("content_hash") == stored["content_hash"] == digest(stored["data"]))
                    if good and "data" in body:
                        entry["representation"] = "full"
                        good = (body["data"] == stored["data"] and body.get("revision") == stored["revision"]
                                and body.get("input_read_set") == [{"key": f"artifact:{artifact_id}", "version": stored["content_hash"], "kind": "artifact"}])
                    elif good:
                        entry["representation"] = body.get("status")
                        good = body.get("status") == "narrower_pointer_required" and set(body.get("available_keys", [])) == set(stored["data"])
                    entry["passed"] = good
                    results[artifact_id] = entry
                    ok = ok and good
                return ok, {"task_id": task["task_id"], "task_status": task["status"], "ancestors": len(manifest), "results": results}
            self.check(f"evidence-ancestor-positive:{label}:{short}", "legitimate_task", "GET /runs/{run}/tasks/{task}/evidence/{ancestor}",
                       "positive control for runtime/context.py:46-71 retrieve",
                       "200 for every same-run completed-ancestor artifact; content_hash equals the stored hash and digest(data); full data equal or narrower_pointer_required with the stored keys",
                       ancestors)

            def non_ancestors(task=task, manifest=manifest):
                targets = [artifact_id for artifact_id in artifacts if artifact_id not in manifest]
                results, ok = {}, True
                for artifact_id in targets:
                    status, body, _ = self.http("GET", self.evidence_path(run_id, task["task_id"], artifact_id), surface=f"evidence_denied:{label}")
                    good = status == 403 and only_detail(body) and body.get("detail") == RETRIEVAL_DENIED
                    results[artifact_id] = {"status": status, "kind": artifacts[artifact_id]["kind"], "producer": artifacts[artifact_id]["provenance"].get("task_id"), "passed": good}
                    ok = ok and good
                return ok, {"task_id": task["task_id"], "non_ancestors": len(targets), "results": results}
            self.check(f"evidence-same-run-non-ancestor:{label}:{short}", "out_of_manifest_artifact", "GET /runs/{run}/tasks/{task}/evidence/{same-run non-ancestor}",
                       boundary, f"403 '{RETRIEVAL_DENIED}' for every same-run artifact outside the manifest (own outputs, siblings, descendants, all worker traces, superseded versions, revision records)",
                       non_ancestors)

            def cross_run(task=task):
                peer = other_tasks.get(task["role_id"])
                targets = [f"{other['run']['run_id']}:source-manifest"] + [f"{other['run']['run_id']}:reference:{candidate}" for candidate in other["run"]["candidate_ids"]]
                targets += expected_manifest(other, peer) if peer else []
                if task["kind"] == "assess_candidate":
                    targets += [artifact["artifact_id"] for artifact in other["artifacts"]]
                results, ok = {}, True
                for artifact_id in dict.fromkeys(targets):
                    status, body, _ = self.http("GET", self.evidence_path(run_id, task["task_id"], artifact_id), surface=f"evidence_denied:{label}")
                    good = status == 403 and only_detail(body) and body.get("detail") == RETRIEVAL_DENIED
                    results[artifact_id] = {"status": status, "passed": good}
                    ok = ok and good
                return ok and bool(results), {"task_id": task["task_id"], "other_run": other["run"]["run_id"], "targets": len(results), "results": results}
            self.check(f"evidence-other-run-artifact:{label}:{short}", "out_of_manifest_artifact", f"GET /runs/{{{label}}}/tasks/{{task}}/evidence/{{run {other_label} artifact}}",
                       boundary + "; available_artifacts filters run_id (context.py:21,25)",
                       "403 for the other run's frozen source artifacts and the artifacts that are ancestors of the same role in that run (all of its artifacts for the assess task)",
                       cross_run)

        def foreign_task_ids():
            results, ok = {}, True
            for task in other["tasks"]:
                peer_manifest = expected_manifest(other, task)
                for path in (f"/runs/{q(run_id)}/tasks/{q(task['task_id'])}/context",
                             self.evidence_path(run_id, task["task_id"], peer_manifest[0])):
                    status, body, _ = self.http("GET", path, surface=f"evidence_denied:{label}")
                    good = status == 404 and only_detail(body) and body.get("detail") == TASK_OUTSIDE_RUN
                    results[path] = {"status": status, "passed": good}
                    ok = ok and good
            for path in (f"/runs/run-{'0' * 32}/tasks/{q(snapshot['tasks'][0]['task_id'])}/context",
                         self.evidence_path(f"run-{'0' * 32}", snapshot["tasks"][0]["task_id"], f"{run_id}:source-manifest")):
                status, body, _ = self.http("GET", path, surface=f"evidence_denied:{label}")
                good = status == 404 and only_detail(body)
                results[path] = {"status": status, "body": body, "passed": good}
                ok = ok and good
            return ok, {"requests": len(results), "results": results}
        self.check(f"evidence-other-run-task-id:{label}", "out_of_manifest_artifact", f"GET /runs/{{{label}}}/tasks/{{run {other_label} task}}/(context|evidence/...)",
                   "api.py:172-174,182-184 tasks.find_one({run_id, task_id}) -> 404; unknown run -> ledger.get_run 404",
                   f"404 '{TASK_OUTSIDE_RUN}' for every run-{other_label} task ID under run {label}; 404 for an unknown run", foreign_task_ids)

    def retrieval_attacks(self):
        snapshot = self.runs["A"]["final"]
        run_id = snapshot["run"]["run_id"]
        artifacts = {artifact["artifact_id"]: artifact for artifact in snapshot["artifacts"]}
        assess = next(task for task in snapshot["tasks"] if task["kind"] == "assess_candidate" and task["status"] == "complete")
        manifest = expected_manifest(snapshot, assess)
        anchor = f"{run_id}:reference:{assess['candidate_id']}"
        tool_result = next(artifacts[key] for key in manifest if artifacts[key]["kind"] == "scientific_tool_result" and artifacts[key]["data"].get("evidence_ids"))
        other_id = self.runs["B"]["final"]["artifacts"][0]["artifact_id"]
        interface = "GET /runs/{A}/tasks/{assess}/evidence/..."

        for index, artifact_id in enumerate(ARTIFACT_ID_ATTACKS):
            def call(artifact_id=artifact_id):
                status, body, text = self.http("GET", self.evidence_path(run_id, assess["task_id"], artifact_id, raw=True), surface="evidence_attacks")
                return status in (400, 403, 404) and only_detail(body), {"status": status, "body": text[:300]}
            self.check(f"evidence-artifact-id-attack-{index:02d}", "evaluator_data", interface + artifact_id,
                       "context.py:50-52 exact manifest-key lookup (403); slash-bearing IDs do not match the route (404)",
                       "400/403/404 with only an error detail", call)

        for index, pointer in enumerate(POINTER_ATTACKS):
            def call(pointer=pointer):
                status, body, text = self.http("GET", self.evidence_path(run_id, assess["task_id"], anchor, query={"pointer": pointer}), surface="evidence_attacks")
                if not pointer.startswith("/"):
                    return status == 422 and only_detail(body), {"status": status, "body": text[:300]}
                ok = status == 200 and body.get("status") == "missing_subtree" and "data" not in body and body.get("artifact_id") == anchor
                return ok, {"status": status, "body": text[:300]}
            expected = "422 non-JSON-pointer" if not pointer.startswith("/") else "200 status missing_subtree, no data (pointer only walks the ancestor artifact's own data)"
            self.check(f"evidence-pointer-attack-{index:02d}", "evaluator_data", interface + f"{anchor}?pointer={pointer}",
                       "context.py:54-60 JSON pointer resolved only inside the selected manifest artifact's data", expected, call)

        for index, query in enumerate(BOUND_ATTACKS):
            def call(query=query):
                status, body, text = self.http("GET", self.evidence_path(run_id, assess["task_id"], anchor, query=query), surface="evidence_attacks")
                return status == 422 and only_detail(body), {"status": status, "body": text[:300]}
            self.check(f"evidence-bounds-attack-{index:02d}", "out_of_manifest_artifact", interface + f"{anchor}?{urllib.parse.urlencode(query)}",
                       "api.py:179 Query(offset ge=0; limit 1..20)", "422", call)

        def query_override():
            status, body, _ = self.http("GET", self.evidence_path(run_id, assess["task_id"], anchor, query={"artifact_id": other_id, "run_id": self.runs["B"]["run_id"], "task_id": "x"}), surface="evidence_attacks")
            return status == 200 and body.get("artifact_id") == anchor and body.get("content_hash") == artifacts[anchor]["content_hash"], {"status": status, "artifact_id": body.get("artifact_id") if isinstance(body, dict) else None}
        self.check("evidence-query-parameter-override", "out_of_manifest_artifact", interface + f"{anchor}?artifact_id=<run B>&run_id=<run B>",
                   "api.py:179 path parameters are authoritative; extra query parameters are ignored",
                   "200 for the path-named ancestor artifact only (never run B's)", query_override)

        def pointer_positive():
            path = self.evidence_path(run_id, assess["task_id"], tool_result["artifact_id"], query={"pointer": "/evidence_ids", "offset": 0, "limit": 1})
            status, body, _ = self.http("GET", path, surface="evidence_allowed:A")
            ids = tool_result["data"]["evidence_ids"]
            ok = status == 200 and body.get("data") == ids[:1] and body.get("total_items") == len(ids) and body.get("content_hash") == tool_result["content_hash"]
            missing_status, missing, _ = self.http("GET", self.evidence_path(run_id, assess["task_id"], tool_result["artifact_id"], query={"pointer": "/calculation/nonexistent"}), surface="evidence_allowed:A")
            ok = ok and missing_status == 200 and missing.get("status") == "missing_subtree" and missing["input_read_set"][0]["version"] == tool_result["content_hash"]
            return ok, {"status": status, "data": body.get("data") if isinstance(body, dict) else None, "total_items": body.get("total_items") if isinstance(body, dict) else None,
                        "expected_total": len(ids), "missing_subtree_status": missing_status}
        self.check("evidence-pointer-offset-positive-control", "legitimate_task", interface + f"{tool_result['artifact_id']}?pointer=/evidence_ids&offset=0&limit=1",
                   "positive control: context.py:57-71 pointer/offset/limit", "first element only, total_items == stored length; missing pointer -> missing_subtree bound to the content hash", pointer_positive)

    # ------------------------------------- 6. withheld-control versions
    def withheld(self):
        info = self.runs["C"]
        snapshot, initial, revision = info["final"], info["initial"], info["revision"]["body"]
        run = snapshot["run"]
        run_id, cid = run["run_id"], info["candidate_id"]
        artifacts = {artifact["artifact_id"]: artifact for artifact in snapshot["artifacts"]}
        superseded = [task for task in snapshot["tasks"] if task["status"] == "superseded"]
        successors = [task for task in snapshot["tasks"] if task.get("supersedes_task_id")]
        pre_versions = sorted({artifact_id for task in superseded for artifact_id in task.get("result_artifact_ids", [])})
        control_versions = [artifact_id for artifact_id in pre_versions if artifacts[artifact_id]["data"].get("tool_name") == "control_overlap"]
        revision_records = [artifact["artifact_id"] for artifact in snapshot["artifacts"] if artifact["kind"] == "evidence_revision"]
        boundary = "runtime/revisions.py supersedes affected tasks; runtime/context.py:21 only status=='complete' ancestors enter the manifest -> retrieve 403"

        def applied():
            ok = (info["revision"]["status"] == 200 and sorted(revision.get("successor_task_ids", [])) == sorted(task["task_id"] for task in successors)
                  and run["evidence_availability"][cid]["control_evidence"] is False and initial["run"]["evidence_availability"][cid]["control_evidence"] is True
                  and all(task["status"] == "complete" for task in successors) and bool(successors) and bool(control_versions) and len(revision_records) == 1)
            return ok, {"revision_response": revision, "control_evidence_before": initial["run"]["evidence_availability"][cid]["control_evidence"],
                        "control_evidence_after": run["evidence_availability"][cid]["control_evidence"], "superseded": [task["task_id"] for task in superseded],
                        "successors": {task["task_id"]: task["status"] for task in successors}, "pre_revision_control_artifacts": control_versions,
                        "revision_records": revision_records, "run_status": run["status"]}
        self.check("withheld-revision-applied", "legitimate_task", "POST /runs/{C}/evidence-revisions {withhold-control-evidence} -> coordinator re-execution",
                   "api.py:221-232 -> runtime/revisions.py apply_revision", "200; control_evidence False; successors complete; pre-revision control_overlap versions exist", applied)

        def via(tasks, targets, surface):
            results, ok = {}, bool(tasks) and bool(targets)
            for task in tasks:
                manifest = set(expected_manifest(snapshot, task))
                for artifact_id in targets:
                    if artifact_id in manifest:
                        results[f"{task['task_id']} -> {artifact_id}"] = {"skipped": "legitimately in this task's manifest"}
                        continue
                    status, body, _ = self.http("GET", self.evidence_path(run_id, task["task_id"], artifact_id), surface=surface)
                    good = status == 403 and only_detail(body) and body.get("detail") == RETRIEVAL_DENIED
                    results[f"{task['task_id']} -> {artifact_id}"] = {"status": status, "passed": good}
                    ok = ok and good
            return ok, {"requests": sum("status" in item for item in results.values()), "results": results}
        self.check("withheld-pre-revision-versions-via-successors", "withheld_control", "GET /runs/{C}/tasks/{successor}/evidence/{pre-revision artifact}", boundary,
                   "403 for every superseded-task artifact (incl. pre-revision control_overlap) from every successor task",
                   lambda: via(successors, pre_versions, "evidence_denied:C"))
        self.check("withheld-control-versions-via-superseded-tasks", "withheld_control", "GET /runs/{C}/tasks/{superseded}/evidence/{pre-revision control_overlap}", boundary,
                   "403: superseded ancestors no longer contribute to any manifest, so even superseded tasks cannot reach withheld-control versions",
                   lambda: via(superseded, control_versions, "evidence_denied:C"))
        self.check("withheld-revision-record-not-retrievable", "withheld_control", "GET /runs/{C}/tasks/{any}/evidence/{evidence_revision artifact}", boundary,
                   "403 for the evidence_revision record from every task", lambda: via(snapshot["tasks"], revision_records, "evidence_denied:C"))

        def successor_contexts():
            results, ok = {}, bool(successors)
            for task in successors:
                status, body, text = self.http("GET", f"/runs/{q(run_id)}/tasks/{q(task['task_id'])}/context", surface="contexts:C")
                if status != 200:
                    results[task["task_id"]] = {"status": status, "body": text[:200]}
                    ok = False
                    continue
                listed = {item["artifact_id"] for item in body["evidence_manifest"]}
                leaked = sorted(listed & set(pre_versions))
                good = body["evidence_availability"] == {"control_evidence": False} and not leaked
                results[task["task_id"]] = {"status": status, "evidence_availability": body["evidence_availability"], "pre_revision_in_manifest": leaked, "passed": good}
                ok = ok and good
            return ok, results
        self.check("withheld-successor-contexts", "withheld_control", "GET /runs/{C}/tasks/{successor}/context", boundary,
                   "control_evidence False; no pre-revision artifact in any successor evidence_manifest", successor_contexts)

        def unavailable_retrievable():
            assess = next(task for task in successors if task["kind"] == "assess_candidate")
            manifest = expected_manifest(snapshot, assess)
            current = [key for key in manifest if artifacts[key]["data"].get("tool_name") == "control_overlap"]
            results, ok = {}, bool(current)
            for artifact_id in current:
                status, body, _ = self.http("GET", self.evidence_path(run_id, assess["task_id"], artifact_id, query={"pointer": "/calculation"}), surface="evidence_allowed:C")
                data = body.get("data", {}) if isinstance(body, dict) else {}
                good = status == 200 and data.get("status") == "unavailable" and "shared_count" not in data and body.get("content_hash") == artifacts[artifact_id]["content_hash"]
                results[artifact_id] = {"status": status, "calculation": data, "passed": good}
                ok = ok and good
            assessment = next((item for item in snapshot["assessments"] if item["task_id"] == assess["task_id"]), None)
            withheld_numbers = {key: (assessment or {}).get("numerical_findings", {}).get(key, "missing") for key in ("control_de_count", "shared_de_count", "targeted_only_count", "overlap_fraction")}
            ok = ok and assessment is not None and all(value is None for value in withheld_numbers.values())
            return ok, {"task_id": assess["task_id"], "current_control_overlap": results, "assessment_control_numbers": withheld_numbers}
        self.check("withheld-current-version-positive-control", "legitimate_task", "GET /runs/{C}/tasks/{successor assess}/evidence/{current control_overlap}?pointer=/calculation",
                   "runtime/worker.py execute_tool unavailable control_overlap result is a legitimate ancestor artifact",
                   "200 with calculation.status 'unavailable' and no shared_count; successor assessment control numbers are null", unavailable_retrievable)

    # ------------------------------------- 7. assessment validation
    def assessment_validation(self):
        snapshot = self.runs["A"]["final"]
        run_id = snapshot["run"]["run_id"]
        route = f"/runs/{q(run_id)}/assessment-validation"
        task = next(item for item in snapshot["tasks"] if item["kind"] == "assess_candidate" and item["status"] == "complete")
        assessment = next(item for item in snapshot["assessments"] if item["task_id"] == task["task_id"])
        manifest = set(expected_manifest(snapshot, task)) | set(task["result_artifact_ids"])
        same_run_outside = next(artifact["artifact_id"] for artifact in snapshot["artifacts"] if artifact["kind"] == "worker_trace" and artifact["artifact_id"] not in manifest)
        other = self.runs["B"]["final"]
        other_artifact = next(artifact["artifact_id"] for artifact in other["artifacts"] if artifact["kind"] == "scientific_tool_result")
        other_task = next(item["task_id"] for item in other["tasks"] if item["kind"] == "assess_candidate")
        # Same operational fixture shape as e2e/safe_harbor/context_assessment_export.py (not a model output).
        proposal = {"conclusion": "Operational validation fixture only: the expression comparison needs contextual interpretation, and overall suitability remains uncertain.",
                    "exclusion_decision": "unresolved", "numerical_findings": assessment["numerical_findings"], "numerical_evidence": assessment["numerical_evidence"],
                    "evidence_ids": assessment["evidence_ids"], "unresolved_questions": ["Overall suitability remains uncertain."],
                    "limitations": ["Control overlap cannot establish causality or biological safety."], "limitation_codes": [],
                    "screen_status": assessment["screen_status"], "evidence_status": "unknown"}
        sequence = snapshot["run"]["through_sequence"]
        interface = "POST /runs/{A}/assessment-validation"
        boundary = "api.py:194-209 -> runtime/assessments.py:71-79 citations limited to available_artifacts + the task's own tool results"

        def post(body):
            return self.http("POST", route, body, surface="assessment_validation")

        def positive():
            status, body, text = post({"task_id": task["task_id"], "proposal": proposal})
            ok = status == 200 and body.get("valid") is True and body.get("model_called") is False and body.get("state_changed") is False
            return ok, {"status": status, "body": text[:400]}
        self.check("validation-positive-control", "legitimate_task", interface, "positive control", "200 valid; model_called false; state_changed false", positive)

        cases = {
            "other-run-artifact": {"evidence_ids": proposal["evidence_ids"] + [other_artifact]},
            "same-run-non-ancestor-trace": {"evidence_ids": proposal["evidence_ids"] + [same_run_outside]},
            "evaluator-path": {"evidence_ids": proposal["evidence_ids"] + [REFERENCE_PATH]},
            "numerical-evidence-other-run": {"numerical_evidence": {**proposal["numerical_evidence"], "de_count": [other_artifact]}},
        }
        for name, change in cases.items():
            def call(change=change):
                status, body, text = post({"task_id": task["task_id"], "proposal": {**copy.deepcopy(proposal), **change}})
                ok = status == 200 and body.get("valid") is False and body.get("validated_proposal") is None and body.get("errors")
                return bool(ok), {"status": status, "errors": body.get("errors") if isinstance(body, dict) else text[:300]}
            self.check(f"validation-citation-{name}", "out_of_manifest_artifact", interface, boundary,
                       "200 valid false with a citation error; no validated proposal", call)

        def extra_field():
            status, body, text = post({"task_id": task["task_id"], "proposal": proposal, "reference_answers": True})
            return status == 422 and only_detail(body), {"status": status, "body": text[:300]}
        self.check("validation-extra-body-field", "unapproved_request", interface, "api.py:188-191 ValidateAssessmentRequest extra='forbid'", "422", extra_field)

        def foreign_task():
            status, body, text = post({"task_id": other_task, "proposal": proposal})
            return status == 404 and only_detail(body), {"status": status, "body": text[:300]}
        self.check("validation-other-run-task", "out_of_manifest_artifact", interface, "api.py:200-202 tasks.find_one({run_id, task_id, complete}) -> 404", "404", foreign_task)

        def unchanged():
            current = self.db.runs.find_one({"run_id": run_id})["through_sequence"]
            return current == sequence, {"through_sequence_before": sequence, "through_sequence_after": current}
        self.check("validation-state-unchanged", "legitimate_task", "MongoDB runs.through_sequence", "assessment-validation is read-only", "unchanged", unchanged)

    # --------------------------------------------- 8. evaluator-data scans
    def markers(self) -> dict:
        reference = json.loads((EVALUATOR / "reference_answers.json").read_text())
        splits = json.loads((EVALUATOR / "splits.json").read_text())
        answer_key = set(ANSWER_KEY_FIELDS) | {REFERENCE_PATH, "reference_answers.json", reference["reference_method"]}
        for answer in reference["answers"].values():
            answer_key.add(answer["review_status"])
            answer_key.update(answer["justification"])
        # Rubric text is a literal in the evaluator source (evaluation/reference_answers.py load_reference);
        # it is read as text, not imported or executed.
        match = re.search(r"\['rubric_notes'\]\s*=\s*(\[.*?\])", EVALUATOR_SOURCE.read_text(), re.DOTALL)
        rubric = ast.literal_eval(match.group(1)) if match else []
        if not rubric:
            self.report["limitations"].append("Rubric notes could not be extracted from evaluation/reference_answers.py; rubric text was not scanned.")
        answer_key.update(rubric)
        split_markers = set(SPLIT_FIELDS) | {SPLITS_PATH, "splits.json", splits["split_hash"], splits["source_family"], splits["grouping"],
                                             splits["promotion_rule"]["additional_benefit"], *splits["limitations"]}
        return {"answer_key": sorted(answer_key), "evaluator_split": sorted(split_markers), "rubric_notes": list(rubric)}

    def scans(self):
        markers = self.markers()
        variants = {kind: [(marker, {marker, json.dumps(marker, ensure_ascii=False)[1:-1], json.dumps(marker)[1:-1]}) for marker in values]
                    for kind, values in markers.items() if kind != "rubric_notes"}
        self.report["marker_counts"] = {kind: len(values) for kind, values in markers.items()}

        def found_in(text):
            return {kind: sorted({raw for raw, forms in pairs if any(form in text for form in forms)}) for kind, pairs in variants.items()}

        control = "\n".join(path.read_text() for path in (EVALUATOR / "reference_answers.json", EVALUATOR / "splits.json", EVALUATOR_SOURCE))
        hits = found_in(control)
        rubric_hits = [note for note in markers["rubric_notes"] if note in hits["answer_key"]]
        self.record("scanner-positive-control", "evaluator_data", "marker scanner",
                    "scanner must detect evaluator records (answers, rubric text, split manifest) in the evaluator files themselves",
                    "answer_key, rubric and evaluator_split markers detected", {**{kind: len(values) for kind, values in hits.items()}, "rubric_notes_detected": len(rubric_hits)},
                    all(hits.values()) and bool(rubric_hits) and len(rubric_hits) == len(markers["rubric_notes"]))
        for label, texts in sorted(self.surfaces.items()):
            joined = "\n".join(texts)
            hits = found_in(joined)
            self.record(f"scan:{label}", "evaluator_data_in_context", f"HTTP bodies: {label}",
                        "worker-visible and exported surfaces must carry no evaluator-only answer, rubric or split values",
                        {"answer_key": [], "evaluator_split": []}, {**hits, "bodies": len(texts), "characters": len(joined)}, not any(hits.values()))
        self.report["limitations"].append("Reference numeric values (DE counts, distances) are intentionally not leak markers: approved tools legitimately recompute the same numbers from source data. Markers are evaluator-only keys, review/method labels, justification and rubric text, and split-manifest values.")

    # --------------------------------------------------------------- execute
    def execute(self) -> int:
        try:
            self.section("api_runs", self.api_runs)
            if {"A", "B", "C"} <= set(self.runs) and all("final" in info for info in self.runs.values()):
                self.section("exports", self.exports)
                self.section("forged_requests", self.forged_requests)
                self.section("artifact_endpoint", self.artifact_endpoint)
                self.section("contexts", self.contexts)
                self.section("retrieval", self.retrieval)
                self.section("withheld", self.withheld)
                self.section("assessment_validation", self.assessment_validation)
            self.section("scans", self.scans)
        finally:
            self.stop()
            failed = [attempt for attempt in self.attempts if not attempt["passed"]]
            self.report["findings"] = [{"kind": "boundary_failure", "attempt_id": attempt["attempt_id"], "boundary": attempt["boundary"], "observed": attempt["observed"]} for attempt in failed]
            self.report["limitations"] += [
                "Deterministic operational mode only: no model attempted to exploit the interfaces. retrieve_evidence is invoked by workers only on the real-model path; here the same runtime/context.py retrieve() is exercised through GET /runs/{run}/tasks/{task}/evidence/{artifact}, which is an operator endpoint sharing that boundary.",
                "Isolation is interface-level, not OS-level: data/safe_harbor/evaluator/* and safe_harbor.evaluation are readable/importable by the API process (the evaluator control plane, including POST /experiments and the harness optimizer, uses them by design). Workers are denied because their only interfaces are the assigned approved tools, retrieve_evidence and the context packet.",
                "API endpoints are unauthenticated (e.g. GET /runs/{id}/artifacts/{aid}, /export, /experiments/{id}); they are operator interfaces, and no worker tool can issue HTTP requests.",
                "Withheld-control denial is structural: retrieve() has no availability-specific branch; pre-revision versions are unreachable because revisions supersede their producing tasks and only completed ancestors enter a manifest.",
            ]
            self.report["runs"] = {label: {"run_id": info["run_id"], "candidate_id": info["candidate_id"], "export": info.get("export"), "revision": info.get("revision")}
                                   for label, info in self.runs.items()}
            self.report["model_calls_recorded_by_runs"] = sum(info["final"]["run"]["budget"]["model_calls"] for info in self.runs.values() if "final" in info)
            self.report["summary"] = {"attempts": len(self.attempts), "passed": len(self.attempts) - len(failed), "failed": len(failed)}
            self.report["passed"] = not failed and bool(self.attempts)
            self.report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            (self.output / "report.json").write_text(json.dumps(self.report, indent=2, ensure_ascii=False, default=str))
            print(json.dumps({"report": str(self.output / "report.json"), **self.report["summary"], "passed": self.report["passed"],
                              "failed_attempts": [attempt["attempt_id"] for attempt in failed]}, indent=2))
            self.client.close()
        return 0 if self.report["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SH-Q06 answer-key, evidence-retrieval and artifact isolation E2E (deterministic operational)")
    parser.add_argument("--port", type=int, default=8022)
    parser.add_argument("--timeout", type=float, default=180.0, help="seconds to wait for each deterministic run to complete")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "safe_harbor" / "isolation-e2e" / str(int(time.time())))
    args = parser.parse_args()
    sys.exit(Isolation(args.port, args.output, args.timeout).execute())

#!/usr/bin/env python3
"""SH-Q07 E2E: prove a saved structural harness change executes.

Run from the repository root against the transaction-capable replica set:
  PYTHONPATH=backend:. .venv/bin/python e2e/safe_harbor/adaptation.py --port 8041

The journey starts its own API/coordinator process on an isolated MongoDB
database with model credentials removed from the child environment, so no
provider request can be made. It then:

1. Scans every database on the configured replica set for a genuine automatic
   (real-model) harness proposal: a saved ``real_model`` HarnessVersion whose
   recorded optimizer response reproduces the exact patch and hash. If one is
   found it is substantiated, copied into the isolated ledger and executed.
2. Saves a clearly labelled E2E-authored deterministic operational patch that
   uses all four approved mutations (split role, insert reviewer, change
   context, reassign tools). This is a control-path proof, NOT an automatic
   proposal, and cannot establish model improvement.
3. Executes the fixed H0 baseline and each saved candidate through the real
   HTTP API, then compares the compiled architecture, executed task graph,
   dependency order from the committed event stream, per-role worker traces,
   context-selection traces and tool calls. Harness hashes on runs/tasks must
   equal the saved versions and immutable run settings must be identical.
4. Proves boundedness: out-of-bounds patches are rejected by the patch
   compiler, and forged saved records that alter criteria, evaluation, input
   data, model identity, budgets or permissions are rejected by POST /runs
   without creating a run.
5. Runs the product's deterministic experiment through POST /experiments and
   inspects the persisted validation/promotion record and the subsequent
   selected-version final run with its ordered report event. A real-model
   experiment request is recorded as blocked (credentials removed).

Each check is ``passed``, ``failed`` or ``blocked`` (an acceptance element that
cannot be exercised honestly in this environment, e.g. no genuine model
proposal exists). Exit status: 0 all passed, 1 any failure/error, 2 no failures
but at least one acceptance element blocked. No unit or component tests; the
isolated database remains available for inspection.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

from pymongo import MongoClient

from safe_harbor.harness import apply_patch, canonical_hash, get_harness, save_harness
from safe_harbor.harness.specification import IMMUTABLE_CONSTRAINTS
from safe_harbor.runtime.compiler import APPROVED_TOOLS, compile_harness
from safe_harbor.runtime.ledger import Ledger, LedgerError, now

ROOT = Path(__file__).resolve().parents[2]
URI = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27021/?replicaSet=safe-harbor-dev")
CANDIDATES = ["pansio-1", "olonne-18"]
ASSIGNED_BUDGET = {"token_limit": 60000, "tool_limit": 40, "cost_limit_usd": 5.0}
NUMERICAL_TOOLS = {"expression_comparison", "control_overlap", "gene_proximity", "screen_candidate"}
IMMUTABLE_RUN_FIELDS = ("mode", "data_version", "evidence_versions", "evidence_availability", "execution_limits", "model_id", "model_provider", "model_settings", "model_pricing", "objective", "scientific_contract", "candidate_ids", "assembly", "cell_context")

# E2E-authored deterministic operational control-path patch. It exercises every
# approved mutation kind. It is NOT an automatic or model-generated proposal.
OPERATIONAL_PATCH = {"operations": [
    {"op": "split_role", "role_id": "assess", "roles": [
        {"role_id": "assess_quantify", "kind": "compute_features",
         "question": "Which exact targeted, untargeted-control and overlap counts bear on the expression-exclusion question?",
         "allowed_tools": ["expression_comparison", "control_overlap"], "context_policy": "numerical_first",
         "instructions": "E2E-authored operational role. Obtain exact counts and denominators with tools only; do not interpret safety or causality."},
        {"role_id": "assess_synthesis", "kind": "assess_candidate",
         "question": "Do these measured expression changes justify excluding this candidate region?",
         "allowed_tools": ["gene_proximity"], "context_policy": "relevant_evidence",
         "instructions": "E2E-authored operational role. Synthesize upstream quantities; keep unresolved questions explicit; never assign a global safety label."}]},
    {"op": "insert_reviewer", "after_role_id": "assess_synthesis", "role": {
        "role_id": "control_contradiction_review", "kind": "review_candidate",
        "question": "Do any unavailable, incomplete or conflicting control calculations undermine the synthesized assessment?",
        "allowed_tools": ["control_overlap"], "context_policy": "contradictions_first",
        "instructions": "E2E-authored operational reviewer. Surface unavailable or conflicting control evidence first; absence is not a negative biological result."}},
    {"op": "change_context", "role_id": "review", "context_policy": "numerical_first"},
    {"op": "reassign_tools", "from_role_id": "inspect", "to_role_id": "screen", "tools": ["reference_sequence"]},
]}


def sha256_json(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def spec_architecture(spec: dict) -> dict:
    roles = spec["roles"]
    return {"harness_hash": spec["harness_hash"], "role_ids": [role["role_id"] for role in roles],
            "edges": sorted([dependency, role["role_id"]] for role in roles for dependency in role["depends_on"]),
            "kinds": {role["role_id"]: role["kind"] for role in roles},
            "tools": {role["role_id"]: role["allowed_tools"] for role in roles},
            "context_policies": {role["role_id"]: role["context_policy"] for role in roles}}


def executed_architecture(tasks: list[dict], candidate_id: str) -> dict:
    own = [task for task in tasks if task["candidate_id"] == candidate_id]
    role_of = {task["task_id"]: task["role_id"] for task in own}
    return {"role_ids": sorted(role_of.values()),
            "edges": sorted([role_of[dependency], task["role_id"]] for task in own for dependency in task["depends_on"]),
            "tools": {task["role_id"]: task["allowed_tools"] for task in own},
            "context_policies": {task["role_id"]: task["context_policy"] for task in own}}


def forged(record: dict, change) -> dict:
    """Copy a valid saved record, apply an out-of-bounds change, and re-hash it
    so the rejection is caused by the bound itself rather than a hash mismatch."""
    copy = deepcopy(record)
    change(copy)
    copy["harness_hash"] = canonical_hash(copy)
    return copy


class AdaptationJourney:
    def __init__(self, port: int, output: Path):
        self.port, self.output = port, output
        self.base = f"http://127.0.0.1:{port}"
        self.output.mkdir(parents=True, exist_ok=True)
        self.database = f"safe_harbor_adaptation_e2e_{int(time.time())}"
        self.ledger = Ledger(uri=URI, database=self.database)
        self.ledger.initialize()
        self.process = self.log = None
        self.report = {
            "ticket": "SH-Q07", "started_at": now(), "database": self.database, "port": port,
            "execution_mode": "deterministic_operational",
            "labels": {
                "structural_runs": "deterministic operational adapters over real ingested source data; zero model calls",
                "operational_patch": "E2E-authored control-path patch (not automatic, not model-generated)",
                "genuine_automatic_proposal": "real_model proposal only if found and substantiated in the ledger; never fabricated",
                "experiment": "product deterministic experiment (operational_only selection); cannot establish model improvement",
            },
            "model_calls": 0, "model_improvement_claim": False,
            "checks": [], "negative_patch_checks": [], "negative_api_checks": [], "comparisons": [],
        }

    # ---- infrastructure -------------------------------------------------
    def check(self, name: str, outcome: bool | str, **details):
        if isinstance(outcome, bool):
            outcome = "passed" if outcome else "failed"
        self.report["checks"].append({"check": name, "result": outcome, **details})
        print(f"[{outcome}] {name}", flush=True)

    def request(self, path: str, body=None, timeout: float = 20):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base + path, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.load(response)

    def request_error(self, path: str, body) -> tuple[int, dict]:
        try:
            status, payload = self.request(path, body)
            return status, payload
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")

    def get(self, path: str):
        return self.request(path)[1]

    def start(self):
        env = dict(os.environ, PYTHONPATH=f"{ROOT / 'backend'}:{ROOT}", MONGODB_URI=URI, MONGODB_DATABASE=self.database)
        for key in list(env):
            if key.startswith("SAFE_HARBOR_CRASH_") or key.startswith("SAFE_HARBOR_OPERATIONAL_"):
                env.pop(key)
        # Empty values (not merely absent) stop python-dotenv from loading a
        # server-side key: this journey must never reach a model provider.
        env.update(OPENROUTER_API_KEY="", MODEL_ID="")
        self.log = (self.output / "api.log").open("w")
        self.process = subprocess.Popen([sys.executable, "-m", "uvicorn", "safe_harbor.api:app", "--host", "127.0.0.1", "--port", str(self.port)], cwd=ROOT, env=env, stdout=self.log, stderr=subprocess.STDOUT)
        self.report["api_process_id"] = self.process.pid
        until = time.monotonic() + 30
        while time.monotonic() < until:
            if self.process.poll() is not None:
                raise AssertionError(f"API exited {self.process.returncode}; inspect {self.output / 'api.log'}")
            try:
                health = self.get("/health")
                if health["database"] == self.database and health["coordinator_available"]:
                    return health
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(0.2)
        raise AssertionError("Isolated API did not start")

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.report["api_exit_code"] = self.process.returncode if self.process else None
        if self.log:
            self.log.close()
        self.process = self.log = None

    def wait_complete(self, run_id: str, timeout: float = 120) -> dict:
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            snapshot = self.get(f"/runs/{run_id}/snapshot")
            status = snapshot["run"]["status"]
            if status == "complete":
                return snapshot
            if status in ("blocked", "failed", "budget_exhausted"):
                raise AssertionError(f"Run {run_id} ended {status}: {[(t['role_id'], t['status'], t.get('error')) for t in snapshot['tasks']]}")
            time.sleep(0.2)
        raise AssertionError(f"Run {run_id} did not complete within {timeout}s")

    # ---- 1. genuine automatic proposal ---------------------------------
    def scan_genuine_proposals(self) -> list[dict]:
        client = MongoClient(URI, serverSelectionTimeoutMS=5000)
        scanned, found = [], []
        try:
            for name in sorted(client.list_database_names()):
                if name in ("admin", "config", "local") or name == self.database:
                    continue
                db = client[name]
                collections = set(db.list_collection_names())
                entry = {"database": name,
                         "real_model_harness_versions": db.harness_versions.count_documents({"proposal_mode": "real_model"}) if "harness_versions" in collections else 0,
                         "optimizer_attempts": db.evaluations.count_documents({"type": "optimizer_attempt"}) if "evaluations" in collections else 0,
                         "optimizer_candidates_ready": db.evaluations.count_documents({"type": "optimizer_attempt", "status": "candidate_ready"}) if "evaluations" in collections else 0,
                         "optimizer_response_artifacts": db.artifacts.count_documents({"kind": "harness_optimizer_response"}) if "artifacts" in collections else 0,
                         "real_model_runs": db.runs.count_documents({"mode": "real_model"}) if "runs" in collections else 0}
                scanned.append(entry)
                if not entry["real_model_harness_versions"]:
                    continue
                for record in db.harness_versions.find({"proposal_mode": "real_model"}, {"_id": 0}):
                    found.append(self.substantiate(db, record))
        finally:
            client.close()
        self.report["genuine_proposal_scan"] = {"uri_host": URI.split("@")[-1].split("/")[0], "databases": scanned, "candidates": found}
        return [item for item in found if item["substantiated"]]

    def substantiate(self, db, record: dict) -> dict:
        """A genuine proposal must reproduce from its recorded model response."""
        metadata = record.get("proposal_metadata") or {}
        problems = []
        artifact = db.artifacts.find_one({"artifact_id": metadata.get("response_artifact_id")}, {"_id": 0}) if metadata.get("response_artifact_id") else None
        attempt = db.evaluations.find_one({"evaluation_id": f"optimizer:{metadata.get('experiment_id')}"}, {"_id": 0})
        parent = None
        if not artifact or artifact.get("kind") != "harness_optimizer_response" or (artifact.get("provenance") or {}).get("mode") != "real_model":
            problems.append("recorded real-model optimizer response artifact missing")
        else:
            try:
                parsed = json.loads(artifact["data"]["raw_content"])
                if parsed.get("patch") != record.get("patch"):
                    problems.append("saved patch differs from the recorded model response")
                parent = db.harness_versions.find_one({"harness_hash": record["parent_hash"]}, {"_id": 0}) or get_harness(record["parent_hash"], database=db)
                rebuilt = apply_patch(parent, parsed["patch"], proposal_mode="real_model", proposal_metadata=metadata)
                if rebuilt["harness_hash"] != record["harness_hash"]:
                    problems.append("recompiled patch does not reproduce the saved hash")
            except (ValueError, KeyError, TypeError, LedgerError) as exc:
                problems.append(f"response does not recompile: {exc}")
        if not attempt or attempt.get("status") != "candidate_ready" or attempt.get("candidate_hash") != record["harness_hash"]:
            problems.append("optimizer attempt record is not candidate_ready for this hash")
        promotion = db.evaluations.find_one({"evaluation_id": f"promotion:{metadata.get('experiment_id')}"}, {"_id": 0})
        return {"database": db.name, "harness_hash": record["harness_hash"], "model_id": metadata.get("model_id"), "experiment_id": metadata.get("experiment_id"),
                "response_artifact_id": metadata.get("response_artifact_id"), "rationale": metadata.get("rationale"), "patch": record.get("patch"),
                "substantiated": not problems, "problems": problems, "record": record, "parent": parent,
                "promotion": {key: (promotion or {}).get(key) for key in ("status", "promoted", "selected_harness_hash", "reasons", "mode")} if promotion else None}

    # ---- 3. execution comparison ---------------------------------------
    def execute(self, spec: dict, label: str) -> dict:
        status, created = self.request("/runs", {"mode": "deterministic", "candidate_ids": CANDIDATES, "harness_hash": spec["harness_hash"], "budget": ASSIGNED_BUDGET})
        snapshot = self.wait_complete(created["run_id"])
        export = self.get(f"/runs/{created['run_id']}/export")
        return {"label": label, "run_id": created["run_id"], "http_status": status, "spec": spec, "snapshot": snapshot, "export": export}

    def traces(self, snapshot: dict) -> dict:
        artifacts = {artifact["artifact_id"]: artifact for artifact in snapshot["artifacts"]}
        result = {}
        for task in snapshot["tasks"]:
            outputs = [artifacts[artifact_id] for artifact_id in task.get("result_artifact_ids", [])]
            trace = [artifact for artifact in outputs if artifact["kind"] == "worker_trace"]
            result[task["task_id"]] = {"task": task, "outputs": outputs, "trace": trace[0] if len(trace) == 1 else None, "trace_count": len(trace)}
        return result

    def event_order(self, export: dict) -> dict:
        started, completed = {}, {}
        for event in export["events"]:
            for task in event["upserts"].get("tasks", []):
                if task["status"] == "running":
                    started.setdefault(task["task_id"], event["sequence"])
                if task["status"] == "complete":
                    completed.setdefault(task["task_id"], event["sequence"])
        return {"started": started, "completed": completed}

    def verify_run(self, execution: dict) -> dict:
        """Per-run checks: compiled == executed, hashes frozen, traces per role, order."""
        spec, snapshot, export, label = execution["spec"], execution["snapshot"], execution["export"], execution["label"]
        run = snapshot["run"]
        tasks = snapshot["tasks"]
        compiled = compile_harness(spec, run["run_id"], CANDIDATES)
        structural = ("task_id", "role_id", "kind", "depends_on", "allowed_tools", "context_policy", "harness_hash", "question", "instructions", "completion_condition", "budget")
        compiled_view = sorted(({key: task.get(key) for key in structural} for task in compiled), key=lambda item: item["task_id"])
        executed_view = sorted(({key: task.get(key) for key in structural} for task in tasks), key=lambda item: item["task_id"])
        self.check(f"{label}: executed task graph equals compile_harness(saved spec)", compiled_view == executed_view, task_count=len(tasks), compiled_count=len(compiled))
        self.check(f"{label}: run and every task record the saved harness hash", run["harness_hash"] == spec["harness_hash"] and all(task["harness_hash"] == spec["harness_hash"] for task in tasks), run_harness_hash=run["harness_hash"], saved_harness_hash=spec["harness_hash"])
        saved = get_harness(spec["harness_hash"], database=self.ledger.db)
        frozen = [record for record in snapshot["harness_versions"] if record["harness_hash"] == spec["harness_hash"]]
        self.check(f"{label}: run event stream freezes the exact saved harness record", saved == spec and len(frozen) == 1 and frozen[0] == spec)
        self.check(f"{label}: all tasks complete with zero model calls/tokens", run["status"] == "complete" and all(task["status"] == "complete" for task in tasks) and run["budget"]["model_calls"] == 0 and run["budget"]["tokens_used"] == 0,
                   status=run["status"], model_calls=run["budget"]["model_calls"], tokens_used=run["budget"]["tokens_used"], tool_calls=run["budget"]["tool_calls"])
        sequences = [event["sequence"] for event in export["events"]]
        self.check(f"{label}: export equals snapshot with contiguous ordered events", export["snapshot"] == snapshot and sequences == list(range(1, snapshot["through_sequence"] + 1)), through_sequence=snapshot["through_sequence"])
        traced = self.traces(snapshot)
        trace_failures, per_role = [], {}
        for task_id, item in traced.items():
            task, trace = item["task"], item["trace"]
            if trace is None:
                trace_failures.append(f"{task_id}: {item['trace_count']} worker traces")
                continue
            data, packet = trace["data"], trace["data"]["context_packet"]
            expected_tools = task["allowed_tools"][:task["budget"]["max_tool_calls"]]
            called = [call["tool_name"] for call in data["tool_calls"]]
            scientific = [artifact for artifact in item["outputs"] if artifact["kind"] == "scientific_tool_result"]
            if trace["provenance"]["role_id"] != task["role_id"] or trace["provenance"]["harness_hash"] != spec["harness_hash"] or data["role_id"] != task["role_id"]:
                trace_failures.append(f"{task_id}: trace role/hash provenance mismatch")
            if packet["context_policy"] != task["context_policy"] or packet["context_selection_trace"].get("policy") != task["context_policy"] or packet["harness_hash"] != spec["harness_hash"]:
                trace_failures.append(f"{task_id}: context policy trace mismatch")
            if called != expected_tools or [artifact["data"]["tool_name"] for artifact in scientific] != called:
                trace_failures.append(f"{task_id}: tools {called} != assigned {expected_tools}")
            if data["execution_adapter"] != "deterministic_operational" or data["usage"]["model_calls"] != 0 or trace["provenance"]["model_id"] is not None:
                trace_failures.append(f"{task_id}: not a deterministic operational zero-model trace")
            per_role.setdefault(task["role_id"], []).append({
                "task_id": task_id, "candidate_id": task["candidate_id"], "worker_trace_id": trace["artifact_id"],
                "context_policy": packet["context_policy"], "tool_calls": called,
                "evidence_manifest_ids": [entry["artifact_id"] for entry in packet["evidence_manifest"]],
                "included_artifact_ids": packet["context_selection_trace"].get("included_artifact_ids", []),
                "output_kinds": sorted(artifact["kind"] for artifact in item["outputs"])})
        self.check(f"{label}: one role-attributed worker trace per executed task with assigned tools and context policy", not trace_failures, failures=trace_failures, traced_tasks=len(traced))
        order = self.event_order(export)
        order_failures = [f"{task['task_id']} started at {order['started'].get(task['task_id'])} before dependency {dependency} completed at {order['completed'].get(dependency)}"
                          for task in tasks for dependency in task["depends_on"]
                          if not (order["completed"].get(dependency) and order["started"].get(task["task_id"]) and order["completed"][dependency] < order["started"][task["task_id"]])]
        self.check(f"{label}: committed events show every task started only after its dependencies completed", not order_failures, failures=order_failures)
        by_role = {}
        for task in tasks:
            by_role.setdefault(task["role_id"], {"tool_calls": 0})
            by_role[task["role_id"]]["tool_calls"] += len(traced[task["task_id"]]["trace"]["data"]["tool_calls"]) if traced[task["task_id"]]["trace"] else 0
        return {"label": label, "run_id": run["run_id"], "harness_hash": spec["harness_hash"], "proposal_mode": spec["proposal_mode"],
                "architecture": spec_architecture(spec), "executed_architecture": {candidate: executed_architecture(tasks, candidate) for candidate in CANDIDATES},
                "task_count": len(tasks), "event_count": len(sequences), "measured_usage": run["budget"], "tool_calls_by_role": by_role,
                "executed_role_traces": per_role, "task_start_sequences": order["started"], "task_complete_sequences": order["completed"],
                "export_sha256": sha256_json(export)}

    def compare(self, baseline: dict, candidate: dict, spec: dict, name: str) -> dict:
        base_run, cand_run = baseline["snapshot"]["run"], candidate["snapshot"]["run"]
        base_arch, cand_arch = spec_architecture(baseline["spec"]), spec_architecture(spec)
        added = sorted(set(cand_arch["role_ids"]) - set(base_arch["role_ids"]))
        removed = sorted(set(base_arch["role_ids"]) - set(cand_arch["role_ids"]))
        edges_added = [edge for edge in cand_arch["edges"] if edge not in base_arch["edges"]]
        edges_removed = [edge for edge in base_arch["edges"] if edge not in cand_arch["edges"]]
        changed_policies = {role: [base_arch["context_policies"][role], cand_arch["context_policies"][role]] for role in set(base_arch["role_ids"]) & set(cand_arch["role_ids"]) if base_arch["context_policies"][role] != cand_arch["context_policies"][role]}
        changed_tools = {role: [base_arch["tools"][role], cand_arch["tools"][role]] for role in set(base_arch["role_ids"]) & set(cand_arch["role_ids"]) if base_arch["tools"][role] != cand_arch["tools"][role]}
        diff = {"roles_added": added, "roles_removed": removed, "edges_added": edges_added, "edges_removed": edges_removed, "context_policy_changes": changed_policies, "tool_assignment_changes": changed_tools}
        self.check(f"{name}: compiled architecture differs structurally from baseline", bool(added or removed) and bool(edges_added or edges_removed), **diff)
        base_exec = {c: executed_architecture(baseline["snapshot"]["tasks"], c) for c in CANDIDATES}
        cand_exec = {c: executed_architecture(candidate["snapshot"]["tasks"], c) for c in CANDIDATES}
        executed_ok = all(
            sorted(set(cand_exec[c]["role_ids"]) - set(base_exec[c]["role_ids"])) == added
            and sorted(set(base_exec[c]["role_ids"]) - set(cand_exec[c]["role_ids"])) == removed
            and [e for e in cand_exec[c]["edges"] if e not in base_exec[c]["edges"]] == edges_added
            and [e for e in base_exec[c]["edges"] if e not in cand_exec[c]["edges"]] == edges_removed
            for c in CANDIDATES)
        self.check(f"{name}: executed task graphs reproduce exactly that structural difference for every candidate", executed_ok,
                   baseline_task_count=len(baseline["snapshot"]["tasks"]), candidate_task_count=len(candidate["snapshot"]["tasks"]))
        base_traced_roles = {item["trace"]["provenance"]["role_id"] for item in self.traces(baseline["snapshot"]).values() if item["trace"]}
        cand_traced_roles = {item["trace"]["provenance"]["role_id"] for item in self.traces(candidate["snapshot"]).values() if item["trace"]}
        self.check(f"{name}: added roles produced worker traces only under the candidate; removed roles only under baseline",
                   set(added) <= cand_traced_roles and not set(added) & base_traced_roles and set(removed) <= base_traced_roles and not set(removed) & cand_traced_roles,
                   baseline_traced_roles=sorted(base_traced_roles), candidate_traced_roles=sorted(cand_traced_roles))
        # evidence_versions also registers each run's own output artifacts
        # (run-scoped IDs); input criteria/source/query-scope versions must match.
        def frozen(run, field):
            value = run.get(field)
            return {key: version for key, version in value.items() if not key.startswith("artifact:")} if field == "evidence_versions" else value
        same_run_settings = {field: frozen(base_run, field) == frozen(cand_run, field) for field in IMMUTABLE_RUN_FIELDS}
        limits_equal = all(base_run["budget"][key] == cand_run["budget"][key] == value for key, value in ASSIGNED_BUDGET.items())
        self.check(f"{name}: data, evidence versions, model identity/settings, limits and assigned budget identical across arms",
                   all(same_run_settings.values()) and limits_equal and baseline["spec"]["immutable_constraints"] == spec["immutable_constraints"] == IMMUTABLE_CONSTRAINTS,
                   differing_fields=[field for field, same in same_run_settings.items() if not same], assigned_budget=ASSIGNED_BUDGET)
        # Input data unchanged: every (candidate, tool) calculation is byte-identical across both runs.
        def calculations(snapshot):
            found = {}
            for artifact in snapshot["artifacts"]:
                if artifact["kind"] == "scientific_tool_result":
                    key = (artifact["data"].get("candidate_id"), artifact["data"]["tool_name"])
                    found.setdefault(key, set()).add(sha256_json({"calculation": artifact["data"].get("calculation"), "evidence_ids": artifact["data"].get("evidence_ids"), "source_hashes": artifact["data"].get("source_hashes")}))
            return found
        base_calc, cand_calc = calculations(baseline["snapshot"]), calculations(candidate["snapshot"])
        mismatched = [f"{c}/{t}" for (c, t) in set(base_calc) | set(cand_calc) if len(base_calc.get((c, t), set()) | cand_calc.get((c, t), set())) != 1]
        self.check(f"{name}: every scientific calculation is identical across arms (same input data; structure changed, not evidence)", not mismatched and set(base_calc) == set(cand_calc), mismatched=mismatched, calculation_keys=len(base_calc))
        return {"name": name, "baseline_run_id": base_run["run_id"], "candidate_run_id": cand_run["run_id"], "baseline_harness_hash": base_run["harness_hash"], "candidate_harness_hash": cand_run["harness_hash"],
                "structural_diff": diff, "tool_calls": {"baseline": base_run["budget"]["tool_calls"], "candidate": cand_run["budget"]["tool_calls"]},
                "task_counts": {"baseline": len(baseline["snapshot"]["tasks"]), "candidate": len(candidate["snapshot"]["tasks"])}}

    def operational_specific_checks(self, candidate: dict):
        """Mutation-specific effects of OPERATIONAL_PATCH visible in executed traces."""
        traced = self.traces(candidate["snapshot"])
        by = {(item["task"]["candidate_id"], item["task"]["role_id"]): item for item in traced.values()}
        artifacts = {artifact["artifact_id"]: artifact for artifact in candidate["snapshot"]["artifacts"]}
        failures, evidence = [], {}
        for c in CANDIDATES:
            quantify, synthesis = by[(c, "assess_quantify")], by[(c, "assess_synthesis")]
            reviewer, review, screen, inspect = by[(c, "control_contradiction_review")], by[(c, "review")], by[(c, "screen")], by[(c, "inspect")]
            quantify_outputs = {a["artifact_id"] for a in quantify["outputs"] if a["kind"] != "worker_trace"}
            synthesis_outputs = {a["artifact_id"] for a in synthesis["outputs"] if a["kind"] != "worker_trace"}
            reviewer_outputs = {a["artifact_id"] for a in reviewer["outputs"] if a["kind"] != "worker_trace"}
            synth_manifest = {e["artifact_id"] for e in synthesis["trace"]["data"]["context_packet"]["evidence_manifest"]}
            reviewer_manifest = {e["artifact_id"] for e in reviewer["trace"]["data"]["context_packet"]["evidence_manifest"]}
            review_manifest = {e["artifact_id"] for e in review["trace"]["data"]["context_packet"]["evidence_manifest"]}
            if synthesis["task"]["depends_on"] != [quantify["task"]["task_id"]] or not quantify_outputs <= synth_manifest:
                failures.append(f"{c}: split second role did not consume first role's outputs")
            if reviewer["task"]["depends_on"] != [synthesis["task"]["task_id"]] or not synthesis_outputs <= reviewer_manifest:
                failures.append(f"{c}: inserted reviewer did not consume the synthesis outputs")
            if reviewer["task"]["task_id"] not in review["task"]["depends_on"] or not reviewer_outputs <= review_manifest:
                failures.append(f"{c}: downstream review was not rewired through the inserted reviewer")
            screen_calls = [call["tool_name"] for call in screen["trace"]["data"]["tool_calls"]]
            inspect_calls = [call["tool_name"] for call in inspect["trace"]["data"]["tool_calls"]]
            if "reference_sequence" not in screen_calls or "reference_sequence" in inspect_calls:
                failures.append(f"{c}: reassigned tool did not move from inspect to screen in execution")
            included = review["trace"]["data"]["context_packet"]["context_selection_trace"]["included_artifact_ids"]
            ranks = [0 if artifacts.get(artifact_id, {}).get("data", {}).get("tool_name") in NUMERICAL_TOOLS else 1 for artifact_id in included]
            if review["trace"]["data"]["context_packet"]["context_policy"] != "numerical_first" or ranks != sorted(ranks):
                failures.append(f"{c}: review context was not numerical-first ordered")
            if reviewer["trace"]["data"]["context_packet"]["context_selection_trace"]["policy"] != "contradictions_first":
                failures.append(f"{c}: inserted reviewer did not use contradictions_first")
            evidence[c] = {"split_consumed_artifacts": len(quantify_outputs & synth_manifest), "reviewer_consumed_artifacts": len(synthesis_outputs & reviewer_manifest),
                           "review_consumed_reviewer_artifacts": len(reviewer_outputs & review_manifest), "screen_tool_calls": screen_calls, "inspect_tool_calls": inspect_calls,
                           "review_numerical_first_ranks": ranks}
        self.check("operational patch: split, inserted reviewer, context change and tool reassignment each visible in executed traces", not failures, failures=failures, evidence=evidence)

    # ---- 4. boundedness -------------------------------------------------
    def negative_patches(self, baseline: dict):
        role = {"role_id": "extra_review", "kind": "review_candidate", "question": "Is the assessment supported?", "allowed_tools": ["control_overlap"]}
        attempts = [
            ("criteria edit", {"operations": [{"op": "set_criteria", "criteria": {"max_gene_distance_bp": 1}}]}, {}),
            ("evaluation rule / evaluator edit", {"operations": [{"op": "set_evaluation_rules", "promotion_rule": {"cost_reduction_fraction": 0.0}}]}, {}),
            ("reference answer edit", {"operations": [{"op": "replace_reference_answers", "case_id": "olonne-18--full_sources"}]}, {}),
            ("input data edit", {"operations": [{"op": "set_input_data", "data_version": "other"}]}, {}),
            ("model identity edit", {"operations": [{"op": "set_model", "model_id": "other/model"}]}, {}),
            ("assigned budget edit", {"operations": [{"op": "set_budget", "token_limit": 10 ** 9}]}, {}),
            ("new role elevates tool-call cap", {"operations": [{"op": "insert_reviewer", "after_role_id": "assess", "role": {**role, "max_tool_calls": 8}}]}, {}),
            ("new role elevates model-call cap", {"operations": [{"op": "insert_reviewer", "after_role_id": "assess", "role": {**role, "max_model_calls": 9}}]}, {}),
            ("new role supplies its own dependencies", {"operations": [{"op": "insert_reviewer", "after_role_id": "assess", "role": {**role, "depends_on": []}}]}, {}),
            ("permission: unapproved tool on new role", {"operations": [{"op": "insert_reviewer", "after_role_id": "assess", "role": {**role, "allowed_tools": ["fetch_url"]}}]}, {}),
            ("permission: reassign unapproved tool", {"operations": [{"op": "reassign_tools", "from_role_id": "review", "to_role_id": "assess", "tools": ["read_evaluator_answers"]}]}, {}),
            ("split drops a tool capability", {"operations": [{"op": "split_role", "role_id": "assess", "roles": [{**role, "role_id": "a1", "kind": "compute_features", "allowed_tools": ["expression_comparison"]}, {**role, "role_id": "a2", "kind": "assess_candidate", "allowed_tools": ["gene_proximity"]}]}]}, {}),
            ("top-level immutable override alongside operations", {"operations": [{"op": "change_context", "role_id": "review", "context_policy": "numerical_first"}], "immutable_constraints": {"model_identity": "other"}}, {}),
            ("more than four operations", {"operations": [{"op": "change_context", "role_id": r, "context_policy": "numerical_first"} for r in ("screen", "inspect", "compare", "assess", "review")]}, {}),
            ("real-model label without recorded model response", {"operations": [{"op": "change_context", "role_id": "review", "context_policy": "numerical_first"}]}, {"proposal_mode": "real_model", "proposal_metadata": {"model_id": "fabricated"}}),
            ("no executable change", {"operations": [{"op": "change_context", "role_id": "review", "context_policy": "relevant_evidence"}]}, {}),
        ]
        before = self.ledger.db.harness_versions.count_documents({})
        for name, patch, kwargs in attempts:
            try:
                apply_patch(baseline, patch, **({"proposal_mode": "deterministic_operational"} | kwargs))
                outcome = {"attempt": name, "rejected": False, "error": None}
            except LedgerError as exc:
                outcome = {"attempt": name, "rejected": exc.code == 422, "http_equivalent_code": exc.code, "error": str(exc)}
            self.report["negative_patch_checks"].append(outcome)
        after = self.ledger.db.harness_versions.count_documents({})
        rejected = [item for item in self.report["negative_patch_checks"] if item["rejected"]]
        self.check("boundedness: every out-of-bounds or non-structural patch is rejected by the patch compiler", len(rejected) == len(attempts) and before == after,
                   rejected=len(rejected), attempted=len(attempts), saved_versions_before=before, saved_versions_after=after)

    def negative_api(self, candidate: dict):
        """Forged saved records (bypassing save_harness) must not execute via POST /runs."""
        cases = [(f"immutable constraint altered: {key}", (lambda k: lambda r: r["immutable_constraints"].__setitem__(k, "forged-" + str(r["immutable_constraints"][k])))(key)) for key in sorted(IMMUTABLE_CONSTRAINTS)]
        cases += [
            ("top-level budget setting injected", lambda r: r.__setitem__("budget", {"token_limit": 10 ** 9})),
            ("top-level model identity injected", lambda r: r.__setitem__("model_id", "other/model")),
            ("top-level criteria injected", lambda r: r.__setitem__("criteria", {"max_gene_distance_bp": 1})),
            ("role tool-call cap elevated", lambda r: r["roles"][0].__setitem__("max_tool_calls", 8)),
            ("role granted unapproved tool", lambda r: r["roles"][0].__setitem__("allowed_tools", r["roles"][0]["allowed_tools"][:3] + ["fetch_url"])),
            ("approved tool removed from harness", lambda r: [role.__setitem__("allowed_tools", [t for t in role["allowed_tools"] if t != "reference_sequence"]) for role in r["roles"]]),
            ("review removed upstream of report", lambda r: [role.__setitem__("depends_on", [d for d in role["depends_on"] if d != "review"]) for role in r["roles"] if role["kind"] == "publish_shortlist"]),
        ]
        runs_before = self.ledger.db.runs.count_documents({})
        for name, change in cases:
            record = forged(candidate, change)
            self.ledger.db.harness_versions.insert_one(deepcopy(record))
            status, body = self.request_error("/runs", {"mode": "deterministic", "candidate_ids": CANDIDATES, "harness_hash": record["harness_hash"], "budget": ASSIGNED_BUDGET})
            self.report["negative_api_checks"].append({"attempt": name, "forged_hash": record["harness_hash"], "http_status": status, "detail": body.get("detail"), "rejected": status == 422})
        tampered = deepcopy(candidate)
        tampered["roles"][0]["instructions"] += " tampered after hashing"
        self.ledger.db.harness_versions.insert_one({**tampered, "harness_hash": "f" * 64})
        status, body = self.request_error("/runs", {"mode": "deterministic", "candidate_ids": CANDIDATES, "harness_hash": "f" * 64, "budget": ASSIGNED_BUDGET})
        self.report["negative_api_checks"].append({"attempt": "content changed without matching hash", "http_status": status, "detail": body.get("detail"), "rejected": status == 422})
        for name, body_in in (("request body carries model identity", {"mode": "deterministic", "candidate_ids": CANDIDATES, "harness_hash": candidate["harness_hash"], "model_id": "other/model"}),
                              ("request budget carries non-limit field", {"mode": "deterministic", "candidate_ids": CANDIDATES, "harness_hash": candidate["harness_hash"], "budget": {**ASSIGNED_BUDGET, "model_calls": -5}}),
                              ("unknown harness hash", {"mode": "deterministic", "candidate_ids": CANDIDATES, "harness_hash": "0" * 64}),
                              ("real-model run while provider credentials are absent", {"mode": "real_model", "candidate_ids": CANDIDATES, "harness_hash": candidate["harness_hash"]})):
            status, body = self.request_error("/runs", body_in)
            self.report["negative_api_checks"].append({"attempt": name, "http_status": status, "detail": body.get("detail") if isinstance(body.get("detail"), str) else "schema validation", "rejected": status in (404, 409, 422)})
        runs_after = self.ledger.db.runs.count_documents({})
        rejected = [item for item in self.report["negative_api_checks"] if item["rejected"]]
        self.check("boundedness: POST /runs rejects every forged or out-of-bounds harness/request and creates no run", len(rejected) == len(self.report["negative_api_checks"]) and runs_before == runs_after,
                   rejected=len(rejected), attempted=len(self.report["negative_api_checks"]), runs_before=runs_before, runs_after=runs_after,
                   constraint_keys_checked=sorted(IMMUTABLE_CONSTRAINTS))

    # ---- 5. validation / promotion / selected-version run ---------------
    def experiment(self, deadline_seconds: float) -> dict:
        blocked = self.request("/experiments", {"mode": "real_model"})[1]
        self.check("real-model experiment is recorded as blocked without credentials (no optimizer call, no fabricated proposal)",
                   blocked["status"] == "blocked" and blocked["optimizer"] is None and len(blocked["results"]) == 24 and all(row["status"] == "not_run_blocked" and row["run_id"] is None and row["usage"]["model_calls"] == 0 for row in blocked["results"]),
                   experiment_id=blocked["evaluation_id"], status=blocked["status"], blockers=blocked.get("blockers"))
        started = time.monotonic()
        experiment_id = self.request("/experiments", {"mode": "deterministic"})[1]["evaluation_id"]
        while True:
            experiment = self.get(f"/experiments/{experiment_id}")
            if experiment["status"] in ("operational_complete", "complete", "blocked", "failed"):
                break
            if time.monotonic() - started > deadline_seconds:
                raise AssertionError(f"Experiment {experiment_id} still {experiment['status']} after {deadline_seconds}s")
            time.sleep(1)
        duration = round(time.monotonic() - started, 1)
        self.check("deterministic experiment completes through POST /experiments", experiment["status"] == "operational_complete", experiment_id=experiment_id, status=experiment["status"], error=experiment.get("error"), wall_seconds=duration)
        optimizer = experiment.get("optimizer") or {}
        h1_rows = [row for row in experiment["results"] if row["arm"] == "H1"]
        self.check("deterministic optimizer path refuses to invent a proposal; H1 rows kept as not_run_no_candidate",
                   optimizer.get("status") == "blocked" and optimizer.get("candidate_hash") is None and optimizer["usage"]["model_calls"] == 0 and len(h1_rows) == 6 and all(row["status"] == "not_run_no_candidate" and row["run_id"] is None for row in h1_rows),
                   optimizer_status=optimizer.get("status"), optimizer_reason=optimizer.get("reason"), h1_rows=len(h1_rows))
        persisted = self.ledger.db.evaluations.find_one({"evaluation_id": f"promotion:{experiment_id}"}, {"_id": 0})
        h0 = experiment["arms"]["H0"]
        self.check("validation/promotion decision is persisted in MongoDB evaluations and matches the experiment",
                   persisted is not None and persisted["type"] == "harness_selection" and persisted["status"] == experiment["promotion"]["status"] == "operational_only" and persisted["selected_harness_hash"] == experiment["selected_harness_hash"] == h0,
                   promotion_record_id=f"promotion:{experiment_id}", status=(persisted or {}).get("status"), selected_harness_hash=(persisted or {}).get("selected_harness_hash"), reason=(persisted or {}).get("reason"))
        attachment = experiment.get("report_attachment") or {}
        final = [row for row in experiment["results"] if row["split"] == "final" and row.get("run_id")]
        selected_final = [row for row in final if row["harness_hash"] == experiment["selected_harness_hash"]]
        attached = self.get(f"/runs/{attachment['run_id']}/snapshot") if attachment.get("run_id") else None
        events = self.get(f"/runs/{attachment['run_id']}/events?after_sequence={attachment['sequence'] - 1}")["events"] if attached else []
        validation_started = max((row.get("run_id") and self.ledger.db.runs.find_one({"run_id": row["run_id"]}, {"created_at": 1})["created_at"]) or "" for row in experiment["results"] if row["split"] == "validation")
        final_created = min(self.ledger.db.runs.find_one({"run_id": row["run_id"]}, {"created_at": 1})["created_at"] for row in final)
        self.check("subsequent selected-version final run records the selected harness hash and carries the ordered report event",
                   bool(attached) and attached["run"]["harness_hash"] == experiment["selected_harness_hash"] and bool(selected_final) and all(t["harness_hash"] == experiment["selected_harness_hash"] for t in attached["tasks"])
                   and any(e["sequence"] == attachment["sequence"] and e["cause"] == "experiment.reported" for e in events) and final_created > validation_started,
                   selected_run_id=attachment.get("run_id"), report_sequence=attachment.get("sequence"), selected_harness_hash=experiment["selected_harness_hash"],
                   final_runs_after_validation=final_created > validation_started)
        return {"blocked_real_model_experiment_id": blocked["evaluation_id"], "experiment_id": experiment_id, "status": experiment["status"], "wall_seconds": duration,
                "arms": experiment["arms"], "optimizer": {k: optimizer.get(k) for k in ("status", "reason", "candidate_hash", "usage")},
                "promotion": {k: (persisted or {}).get(k) for k in ("evaluation_id", "type", "status", "promoted", "selected_harness_hash", "reason", "reasons")},
                "selected_final_run_id": attachment.get("run_id"), "report_event_sequence": attachment.get("sequence"),
                "case_rows": len(experiment["results"]), "executed_case_runs": len([r for r in experiment["results"] if r.get("run_id")]),
                "report_model_improvement_claim": experiment["report"]["model_improvement_claim"]}

    # ---- orchestration ---------------------------------------------------
    def run(self, experiment_deadline: float):
        error = None
        try:
            genuine = self.scan_genuine_proposals()
            scan = self.report["genuine_proposal_scan"]
            self.check("ledger contains a genuine automatic (real-model) structural proposal substantiated by its recorded response",
                       "passed" if genuine else "blocked", databases_scanned=len(scan["databases"]), real_model_versions=sum(d["real_model_harness_versions"] for d in scan["databases"]),
                       optimizer_attempts=sum(d["optimizer_attempts"] for d in scan["databases"]), optimizer_candidates_ready=sum(d["optimizer_candidates_ready"] for d in scan["databases"]),
                       optimizer_response_artifacts=sum(d["optimizer_response_artifacts"] for d in scan["databases"]), real_model_runs=sum(d["real_model_runs"] for d in scan["databases"]),
                       reason=None if genuine else "No substantiated real-model optimizer proposal exists on this replica set; the optimizer was not invoked because this journey must not spend provider credits.")
            baseline = get_harness()
            operational = apply_patch(baseline, OPERATIONAL_PATCH, proposal_mode="deterministic_operational", proposal_metadata={
                "authoring": "e2e_authored_operational_control_path", "automatic_proposal": False, "ticket": "SH-Q07",
                "purpose": "Prove a saved structural change is executed; not an automatic proposal and not evidence of improvement."})
            save_harness(baseline, database=self.ledger.db)
            save_harness(operational, database=self.ledger.db)
            reloaded = get_harness(operational["harness_hash"], database=self.ledger.db)
            self.check("operational candidate saved immutably with parent, exact patch and provenance label",
                       reloaded == operational and reloaded["parent_hash"] == baseline["harness_hash"] and reloaded["patch"] == OPERATIONAL_PATCH and reloaded["proposal_mode"] == "deterministic_operational" and canonical_hash(reloaded) == reloaded["harness_hash"],
                       harness_hash=operational["harness_hash"], parent_hash=baseline["harness_hash"], roles=len(operational["roles"]))
            specs = [("operational_patch", operational)]
            for index, item in enumerate(genuine):
                if item["parent"] and item["parent"]["harness_hash"] != baseline["harness_hash"]:
                    save_harness(item["parent"], database=self.ledger.db)
                save_harness(item["record"], database=self.ledger.db)
                specs.append((f"genuine_proposal_{index + 1}", item["record"]))
            health = self.start()
            self.report["api_health"] = health
            self.check("isolated API has no model access (guard against provider spend)", health["model_available"] is False and health["database"] == self.database)
            catalog = self.get("/catalog")
            self.check("catalog serves the verified candidates used by the journey", set(CANDIDATES) <= {c["candidate_id"] for c in catalog["candidates"]}, data_version=catalog["data_version"])
            default_run = self.request("/runs", {"mode": "deterministic", "candidate_ids": CANDIDATES[:1], "budget": ASSIGNED_BUDGET})[1]
            default_snapshot = self.wait_complete(default_run["run_id"])
            self.check("saving a candidate does not silently change the default harness of new runs",
                       default_snapshot["run"]["harness_hash"] == baseline["harness_hash"], run_id=default_run["run_id"], harness_hash=default_snapshot["run"]["harness_hash"])
            base_exec = self.execute(baseline, "baseline_H0")
            base_summary = self.verify_run(base_exec)
            self.report["baseline"] = base_summary
            for label, spec in specs:
                cand_exec = self.execute(spec, label)
                summary = self.verify_run(cand_exec)
                comparison = self.compare(base_exec, cand_exec, spec, label)
                if label == "operational_patch":
                    self.operational_specific_checks(cand_exec)
                self.report["comparisons"].append({**comparison, "candidate": summary, "patch": spec["patch"], "proposal_metadata": spec.get("proposal_metadata")})
            rerun = self.get(f"/runs/{base_exec['run_id']}/snapshot")
            self.check("earlier baseline run stays frozen to its own version after candidate runs", rerun["run"]["harness_hash"] == baseline["harness_hash"] and all(t["harness_hash"] == baseline["harness_hash"] for t in rerun["tasks"]))
            self.negative_patches(baseline)
            self.negative_api(operational)
            self.report["experiment"] = self.experiment(experiment_deadline)
            promoted_structural = [item for item in genuine if (item.get("promotion") or {}).get("promoted") and (item["promotion"].get("selected_harness_hash") == item["harness_hash"])]
            self.check("a run under a PROMOTED (validation-selected) structurally different version executes",
                       "passed" if promoted_structural else "blocked",
                       reason=None if promoted_structural else "Promotion requires a genuine real-model proposal plus real-model validation scores; deterministic selection is operational_only by design and selected the unchanged H0. The structural runs above use explicitly selected saved hashes, not a promoted version.")
            self.report["genuine_proposals_executed"] = [{k: v for k, v in item.items() if k not in ("record", "parent")} for item in genuine]
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.check("journey completed without error", False, error=error)
            raise
        finally:
            self.stop()
            statuses = [item["result"] for item in self.report["checks"]]
            self.report.update(finished_at=now(), error=error,
                               summary={"passed": statuses.count("passed"), "failed": statuses.count("failed"), "blocked": statuses.count("blocked"), "checks": len(statuses),
                                        "failed_checks": [c["check"] for c in self.report["checks"] if c["result"] == "failed"],
                                        "blocked_checks": [c["check"] for c in self.report["checks"] if c["result"] == "blocked"]},
                               ticket_acceptance_complete=bool(statuses) and all(s == "passed" for s in statuses),
                               limitations=[
                                   "Structural runs use deterministic operational adapters: they prove the saved change is compiled and executed, not that it improves answers.",
                                   "The operational patch was authored in this E2E; it is not an automatic or model-generated proposal.",
                                   "No genuine real-model optimizer proposal exists on the scanned replica set, so automatic proposal inspection and promotion of a structural version remain unexercised.",
                                   "The deterministic experiment selects H0 as operational_only; no promotion, model improvement or cost win is claimed.",
                                   "Only the local replica set was scanned; other contributors' ledgers were not accessible.",
                               ])
            (self.output / "report.json").write_text(json.dumps(self.report, indent=2, ensure_ascii=False) + "\n")
            self.ledger.client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8041)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "safe_harbor" / "adaptation-e2e")
    parser.add_argument("--experiment-deadline", type=float, default=900)
    args = parser.parse_args()
    journey = AdaptationJourney(args.port, args.output)
    try:
        journey.run(args.experiment_deadline)
    except Exception:
        pass
    summary = journey.report["summary"]
    print(json.dumps({"ticket": "SH-Q07", "database": journey.database, "report": str(args.output / "report.json"), **summary, "ticket_acceptance_complete": journey.report["ticket_acceptance_complete"], "error": journey.report["error"]}, indent=2))
    sys.exit(1 if summary["failed"] or journey.report["error"] else 2 if summary["blocked"] else 0)


if __name__ == "__main__":
    main()

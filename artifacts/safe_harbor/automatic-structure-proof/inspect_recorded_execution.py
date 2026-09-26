"""Read-only audit of existing Mongo/API records; never dispatches work or calls a model.

This is artifact/provenance inspection, not a unit or component test. It does not
invoke the production patch/compiler or worker implementation. Output files are
local snapshots of an ongoing experiment; pending phases remain explicitly pending.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from urllib.request import urlopen

from pymongo import MongoClient

EXPERIMENT = "experiment-a879d0fa4f5e499b89a43ed8b7f7f400"
CANDIDATE = "453e57dd9f41b0cb35120608d3670cceaf8b15be4ce7e2c84684d65cb6097124"
OUT = Path(__file__).resolve().parent
API = "http://127.0.0.1:8016"


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def save(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": str(path.relative_to(OUT)), "sha256": sha256(path.read_bytes()).hexdigest()}


def get(path):
    with urlopen(API + path, timeout=30) as response:
        return json.load(response)


def architecture(roles):
    return {r["role_id"]: {k: r[k] for k in ("kind", "depends_on", "allowed_tools", "context_policy")} for r in roles}


client = MongoClient("mongodb://127.0.0.1:27021/?replicaSet=safe-harbor-dev", serverSelectionTimeoutMS=5000)
db = client.safe_harbor
experiment = get("/experiments/" + EXPERIMENT)
candidate = db.harness_versions.find_one({"harness_hash": CANDIDATE}, {"_id": 0})
parent = db.harness_versions.find_one({"harness_hash": candidate["parent_hash"]}, {"_id": 0})
optimizer = db.evaluations.find_one({"evaluation_id": "optimizer:" + EXPERIMENT}, {"_id": 0})
response = db.artifacts.find_one({"artifact_id": optimizer["proposal_artifact_id"]}, {"_id": 0})
raw = response["data"]
parsed = json.loads(raw["raw_content"])
request_packet = json.loads(raw["request"]["messages"][1]["content"])
development_ids = {c["case_id"] for c in experiment["cases"] if c["split"] == "development"}
development_rows = request_packet["development_results"]["runs"]
manifest_model = experiment["model_snapshot"]
model_summary = {k: v for k, v in manifest_model.items() if k != "model_pricing"}
model_summary["pricing_hash"] = manifest_model["model_pricing"]["pricing_hash"]
before, after = architecture(parent["roles"]), architecture(candidate["roles"])
checks = {
    "candidate_content_hash_matches": digest({k: v for k, v in candidate.items() if k != "harness_hash"}) == CANDIDATE,
    "parent_content_hash_matches": digest({k: v for k, v in parent.items() if k != "harness_hash"}) == parent["harness_hash"],
    "response_artifact_hash_matches_exact_data": digest(raw) == response["content_hash"],
    "request_hash_matches_saved_request": digest(raw["request"]) == optimizer["request_hash"],
    "raw_content_equals_provider_message": raw["raw_content"] == raw["response"]["choices"][0]["message"]["content"],
    "exact_model_patch_equals_saved_patch": parsed["patch"] == candidate["patch"] == optimizer["patch"],
    "exact_rationale_preserved": parsed["rationale"] == candidate["proposal_metadata"]["rationale"] == optimizer["rationale"],
    "response_provenance_binds_candidate_parent_request": candidate["proposal_metadata"]["response_artifact_id"] == response["artifact_id"] and response["provenance"]["parent_hash"] == parent["harness_hash"] and candidate["proposal_metadata"]["request_hash"] == response["provenance"]["request_hash"] == optimizer["request_hash"],
    "actual_model_proposal_not_manual_fixture": candidate["proposal_mode"] == response["provenance"]["mode"] == optimizer["mode"] == "real_model" and optimizer["usage"]["model_calls"] == 1,
    "immutable_constraints_identical": candidate["immutable_constraints"] == parent["immutable_constraints"],
    "development_cases_only": set(raw["development_case_ids"]) <= development_ids and all(x["case_id"] in development_ids for x in development_rows) and request_packet["development_results"]["split"] == response["provenance"]["source_split"] == "development",
    "model_settings_and_budget_frozen_in_request": request_packet["fixed_model_snapshot"] == model_summary and request_packet["same_assigned_budget_for_every_arm"] == optimizer["assigned_run_budget"] and raw["request"]["extra_body"]["provider"] == manifest_model["model_pricing"]["provider_routing"],
    "changed_task_topology_in_saved_spec": set(before) != set(after) and before != after,
}
report = {
    "schema_version": 1, "observed_at": datetime.now(timezone.utc).isoformat(),
    "inspection_mode": "read_only_recorded_real_model_execution", "model_calls_by_this_inspection": 0, "ledger_writes": 0,
    "experiment_id": EXPERIMENT, "experiment_status": experiment["status"], "comparison_manifest_hash": experiment["comparison_manifest_hash"],
    "parent_hash": parent["harness_hash"], "candidate_hash": CANDIDATE,
    "proposal": {"status": "compiled_and_saved" if all(checks.values()) else "integrity_failure", "checks": checks, "optimizer_usage": optimizer["usage"], "provider_response_id": raw["response"]["id"], "finish_reason": raw["response"]["choices"][0]["finish_reason"], "request_hash": optimizer["request_hash"], "response_artifact_id": response["artifact_id"], "patch": parsed["patch"], "rationale": parsed["rationale"]},
    "architecture": {"parent": before, "candidate": after, "roles_added": sorted(set(after)-set(before)), "roles_removed": sorted(set(before)-set(after)), "roles_modified": sorted(k for k in set(before)&set(after) if before[k] != after[k])},
    "execution": {"status": "pending_first_h1_run", "runs": []},
    "evaluation": {"status": "pending", "promotion": experiment.get("promotion"), "h1_case_results": [r for r in experiment["results"] if r["arm"] == "H1"]},
    "files": {"parent": save("parent-harness.json", parent), "candidate": save("candidate-harness.json", candidate), "response": save("optimizer-response.json", response), "optimizer": save("optimizer-attempt.json", optimizer), "experiment": save("experiment-observed.json", experiment)},
    "limitations": ["Compilation, executed topology, validation, and promotion are separate claims; pending stages are not successes.", "Exact model-authored new-role instructions contain literal [shared_instruction:...] markers. They were preserved, not silently expanded or repaired. Runtime mandatory metadata/output constraints remain separate.", "The optimizer rationale is its own hypothesis from development traces, not an independently established cause or improvement.", "This read-only inspection makes no provider call and does not force-dispatch a candidate run.", "No biological safety or broad generalization is demonstrated."],
}
known_runs = list(db.runs.find({"experiment_id": EXPERIMENT, "harness_hash": CANDIDATE}, {"run_id": 1, "created_at": 1}).sort("created_at", 1))
for known in known_runs[:1]:
    exported = get("/runs/" + known["run_id"] + "/export")
    snapshot = exported["snapshot"]
    run, tasks, events = snapshot["run"], snapshot["tasks"], exported["events"]
    task_by_id = {t["task_id"]: t for t in tasks}
    task_roles = {t["role_id"] for t in tasks if t.get("plan_revision", 0) == 0}
    mismatch = []
    for task in tasks:
        expected = after[task["role_id"]]
        dependency_roles = [task_by_id[x]["role_id"] for x in task["depends_on"]]
        actual = {"kind": task["kind"], "depends_on": dependency_roles, "allowed_tools": task["allowed_tools"], "context_policy": task["context_policy"]}
        if actual != expected or task["harness_hash"] != CANDIDATE:
            mismatch.append({"task_id": task["task_id"], "expected": expected, "actual": actual})
    traces = []
    for artifact in snapshot["artifacts"]:
        if artifact["kind"] not in ("worker_trace", "worker_failure_trace"):
            continue
        data = artifact["data"]
        task = task_by_id.get(artifact["provenance"].get("task_id"))
        if not task:
            continue
        packet = data.get("context_packet", {})
        traces.append({"artifact_id": artifact["artifact_id"], "artifact_kind": artifact["kind"], "task_id": task["task_id"], "role_id": task["role_id"], "mode": data.get("mode"), "execution_adapter": data.get("execution_adapter"), "context_policy": packet.get("context_policy"), "context_selection_trace": packet.get("context_selection_trace"), "allowed_tools": packet.get("allowed_tools"), "tool_calls": [{"tool_name": c["tool_name"], "arguments": c.get("arguments"), "model_call_id": c.get("model_call_id")} for c in data.get("tool_calls", [])], "provider_response_count": len(data.get("provider_responses", [])), "usage": data.get("usage")})
    added = set(after)-set(before)
    added_traces = [t for t in traces if t["role_id"] in added and t["artifact_kind"] == "worker_trace"]
    starts, completes = {}, {}
    for event in events:
        for task in event["upserts"].get("tasks", []):
            if task["status"] == "running":
                starts.setdefault(task["task_id"], event["sequence"])
            if task["status"] == "complete":
                completes.setdefault(task["task_id"], event["sequence"])
    dependency_violations = [{"task_id": task["task_id"], "dependency": dependency} for task in tasks if task["task_id"] in starts for dependency in task["depends_on"] if dependency not in completes or completes[dependency] >= starts[task["task_id"]]]
    settings = {k: experiment["model_snapshot"][k] for k in ("temperature", "max_output_tokens", "context_limit_bytes", "reasoning")}
    execution_checks = {"actual_task_topology_matches_saved_candidate": not mismatch and task_roles == set(after), "run_frozen_to_candidate": run["harness_hash"] == CANDIDATE, "mode_real_model": run["mode"] == "real_model", "assigned_budget_matches_optimizer_comparison": all(run["budget"].get(k) == v for k, v in optimizer["assigned_run_budget"].items()), "model_identity_settings_and_pricing_match": run.get("model_id") == experiment["model_snapshot"]["model_id"] and run.get("model_settings") == settings and run.get("model_pricing", {}).get("pricing_hash") == experiment["model_snapshot"]["model_pricing"]["pricing_hash"], "started_tasks_waited_for_committed_dependencies": not dependency_violations, "all_added_roles_have_accepted_real_model_traces": added <= {t["role_id"] for t in added_traces if t["mode"] == "real_model" and t["provider_response_count"] > 0}, "changed_reviewer_context_traced": any(t["role_id"] == "evidence_review" and t["context_policy"] == "contradictions_first" for t in added_traces), "moved_control_tool_actually_called_by_new_role": any(t["role_id"] == "evidence_review" and any(c["tool_name"] == "control_overlap" for c in t["tool_calls"]) for t in added_traces)}
    entry = {"run_id": run["run_id"], "status": run["status"], "case_context": run.get("case_context"), "through_sequence": snapshot["through_sequence"], "checks": execution_checks, "topology_mismatches": mismatch, "dependency_order_violations": dependency_violations, "task_states": [{k: t.get(k) for k in ("task_id", "role_id", "kind", "depends_on", "allowed_tools", "context_policy", "status", "attempt", "plan_revision")} for t in tasks], "role_traces": traces, "events": [{"sequence": e["sequence"], "cause": e["cause"], "task_ids": [t["task_id"] for t in e["upserts"].get("tasks", [])]} for e in events], "export": save(run["run_id"] + ".export.json", exported)}
    report["execution"]["runs"].append(entry)
if known_runs:
    executed = any(all(x["checks"].values()) for x in report["execution"]["runs"])
    report["execution"]["status"] = "changed_roles_and_tool_assignment_executed" if executed else "tasks_instantiated_execution_pending_or_incomplete"
if experiment.get("promotion"):
    report["evaluation"]["status"] = "selection_recorded_final_evaluation_pending" if experiment["status"] != "complete" else "completed"
report["model_improvement_claim"] = bool((experiment.get("promotion") or {}).get("model_improvement_demonstrated"))
save("report.json", report)
client.close()
print(json.dumps({"proposal": report["proposal"]["status"], "execution": report["execution"]["status"], "evaluation": report["evaluation"]["status"], "runs_inspected": len(known_runs), "model_calls_by_this_inspection": 0}))

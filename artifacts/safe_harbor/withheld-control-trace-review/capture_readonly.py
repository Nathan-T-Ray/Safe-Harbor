"""Inspect recorded tool paths only; no scoring, dispatch, model calls, or ledger writes."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from urllib.request import urlopen

OUT = Path(__file__).resolve().parent
API = "http://127.0.0.1:8016"
EXPERIMENT = "experiment-a879d0fa4f5e499b89a43ed8b7f7f400"
RUNS = {
    "optimizer_development_h0": "run-dc78b257a27a4d7b967d7814cc7259f5",
    "matched_validation_h0": "run-d6e1befd83154d239fdfeab61b2eaefe",
    "matched_validation_h1": "run-e9b7d35c48e245a7ace4dce1f77e10d2",
}


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def get(path):
    with urlopen(API + path, timeout=30) as response:
        return json.load(response)


def save(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": name, "sha256": sha256(path.read_bytes()).hexdigest()}


experiment = get("/experiments/" + EXPERIMENT)
report = {
    "schema_version": 1, "observed_at": datetime.now(timezone.utc).isoformat(),
    "inspection_mode": "read_only_real_model_recorded_trace_review", "model_calls_by_this_inspection": 0,
    "ledger_writes": 0, "evaluator_invocations": 0, "full_run_exports_duplicated": False,
    "experiment_id": EXPERIMENT, "comparison_manifest_hash": experiment["comparison_manifest_hash"],
    "experiment_status_at_inspection": experiment["status"],
    "optimizer_rationale_verbatim": experiment["optimizer"]["rationale"], "runs": {},
}
run_records = {}
for label, run_id in RUNS.items():
    exported = get("/runs/" + run_id + "/export")
    snapshot = exported["snapshot"]
    run = snapshot["run"]
    run_records[label] = run
    failures = [a for a in snapshot["artifacts"] if a["kind"] == "worker_failure_trace"]
    failed_tasks = [t for t in snapshot["tasks"] if t["status"] == "failed"]
    failure = failures[0]
    data = failure["data"]
    packet = data["context_packet"]
    calls = [
        {"call_index": p["call_index"], "provider_response_id": p["response"]["id"],
         "created": p["response"]["created"], "finish_reason": choice["finish_reason"],
         "tool_calls": choice["message"].get("tool_calls", [])}
        for p in data["provider_responses"] for choice in p["response"]["choices"]
    ]
    executed = [{"tool_name": c["tool_name"], "arguments": c["arguments"], "model_call_id": c["model_call_id"], "result_hash": digest(c["result"])} for c in data["tool_calls"]]
    unavailable = [e for c in data["tool_calls"] if c["tool_name"] == "list_evidence" for e in c["result"]["calculation"]["evidence"] if e.get("availability") == "unavailable"]
    requested = [c for response in calls for c in response["tool_calls"]]
    denied = [c for c in requested if c["function"]["name"] == "table_slice" and json.loads(c["function"]["arguments"]).get("contrast") == "untargeted"]
    allowed = set(failed_tasks[0]["allowed_tools"]) | set(failed_tasks[0].get("runtime_tools", []))
    event_projection = [{
        **{k: e[k] for k in ("schema_version", "run_id", "sequence", "event_id", "operation_id", "occurred_at", "type", "cause", "run_revision")},
        "complete_event_canonical_sha256": digest(e),
        "task_upserts": e["upserts"].get("tasks", []),
        "artifact_upserts": [{"artifact_id": a["artifact_id"], "kind": a["kind"], "content_hash": a["content_hash"]} for a in e["upserts"].get("artifacts", [])],
        "run_upserts": [{k: r.get(k) for k in ("status", "stop_reason", "coordinator_epoch", "evidence_versions", "evidence_availability", "budget")} for r in e["upserts"].get("runs", [])],
    } for e in exported["events"]]
    completed_tasks = [t for t in snapshot["tasks"] if t["status"] == "complete"]
    new_reviewer = [t for t in snapshot["tasks"] if t["role_id"] == "evidence_review" and t.get("plan_revision") == 1]
    case = {
        "label": label, "run_id": run_id, "mode": run["mode"], "run_status": run["status"],
        "through_sequence": snapshot["through_sequence"], "run_created_at": run["created_at"],
        "case_context": run["case_context"], "harness_hash": run["harness_hash"],
        "source_export_url": API + "/runs/" + run_id + "/export", "export_canonical_sha256": digest(exported),
        "failure_artifact_id": failure["artifact_id"], "failure_artifact_created_at": failure["created_at"],
        "failure_artifact_hash_valid": digest(data) == failure["content_hash"],
        "failed_task": failed_tasks[0], "failure_usage": data["usage"], "run_usage": run["budget"],
        "context_availability": packet["evidence_availability"], "context_policy": packet["context_policy"],
        "context_expression_scope": [v for v in packet["input_read_set"] if v["key"].endswith(":expression")],
        "provider_tool_requests": calls, "completed_tool_results": executed,
        "unavailable_evidence_inventory": unavailable, "unavailable_contrast_requests": denied,
        "unapproved_tool_names_requested": sorted({c["function"]["name"] for c in requested} - allowed),
        "completed_role_ids": [t["role_id"] for t in completed_tasks],
        "new_reviewer_task_records": new_reviewer,
        "new_reviewer_started": any(t.get("started_at") for t in new_reviewer),
        "assessment_count": len(snapshot["assessments"]),
        "versioned_dossier_count": sum(a["kind"] == "versioned_dossier" for a in snapshot["artifacts"]),
        "exact_failure_artifact_file": save(run_id + ".failure-artifact.json", failure),
        "event_task_projection_file": save(run_id + ".events-tasks.json", {"projection_note": "Exact event envelopes/task upserts; large artifact payloads referenced by immutable ID/hash. Full run export is not duplicated.", "snapshot_tasks": snapshot["tasks"], "events": event_projection}),
    }
    report["runs"][label] = case

h0, h1 = run_records["matched_validation_h0"], run_records["matched_validation_h1"]
report["matched_case_conditions"] = {
    "same_case_context": h0["case_context"] == h1["case_context"],
    "same_model_id": h0["model_id"] == h1["model_id"],
    "same_model_settings": h0["model_settings"] == h1["model_settings"],
    "same_pricing_hash": h0["model_pricing"]["pricing_hash"] == h1["model_pricing"]["pricing_hash"],
    "same_data_version": h0["data_version"] == h1["data_version"],
    "same_scientific_criteria_source_and_query_versions": {k: v for k, v in h0["evidence_versions"].items() if not k.startswith("artifact:")} == {k: v for k, v in h1["evidence_versions"].items() if not k.startswith("artifact:")},
    "same_evidence_availability": h0["evidence_availability"] == h1["evidence_availability"],
    "same_assigned_limits": all(h0["budget"][k] == h1["budget"][k] for k in ("token_limit", "tool_limit", "cost_limit_usd")),
    "distinct_frozen_harnesses": h0["harness_hash"] != h1["harness_hash"],
}
report["evidence_version_scope_note"] = "Scientific criteria/source/query versions are compared. Full application evidence-version maps differ because derived artifacts and immutable run-specific artifact IDs belong to separate runs; this is expected isolation, not shared derived-answer reuse."
report["findings"] = [
    "The development H0 failure cited by the optimizer occurred: inspect requested an unavailable untargeted table and the task failed with PermissionError.",
    "Matched validation H0 and H1 both repeated that path. Each initial context already stated control_evidence=false and expression scope version 2.",
    "Each first provider response batched list_evidence, candidate table_slice, and untargeted table_slice. The inventory and candidate slice completed; the unavailable contrast request failed. The list_evidence result was therefore not a later model observation before the same batched request was chosen.",
    "All requested tool names were allowed. The refused operation was an unavailable contrast of table_slice, not an unapproved tool and not a fabricated negative biological result.",
    "In H1, inspect_evidence failed before evidence_review could start; the new reviewer was upstream of downstream comparison but downstream of the failed inventory. No assessment or dossier was produced for either matched validation arm.",
    "The saved topology changed, but this observed matched case did not show the intended missing-control failure being avoided. This is a trace-level observation, not a rescore, promotion decision, or estimate of average performance.",
]
report["causal_limits"] = [
    "The proximate exception and dependency stop are recorded; these observations do not establish why the model selected the unavailable request.",
    "One paired validation scenario cannot isolate the causal effect of role splitting, instruction text, provider stochasticity, or tool-error policy.",
    "The literal shared-instruction markers were preserved in H1; this review does not attribute the failure to those markers.",
    "The model proposed unavailable-table retrieval in its first response; do not claim it ignored a previously returned inventory result in a later turn.",
    "Complete proposed-call batches and failed-call usage remain recorded; no actual successful result exists for the denied untargeted lookup.",
]
report["verdict"] = {"status": "terminal_observed_failure_repeated", "h1_behavior_change_avoided_targeted_failure": False, "final_answer_quality": "No final assessment or dossier exists in either matched arm; quality is not inferred from workflow topology.", "model_improvement_claim": False, "promotion_decision_made_by_this_review": False}
save("report.json", report)
print(json.dumps({"status": report["verdict"]["status"], "cases": len(report["runs"]), "matched_conditions": report["matched_case_conditions"], "new_model_calls": 0}))

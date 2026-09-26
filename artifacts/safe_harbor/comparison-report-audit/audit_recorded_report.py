"""Independent arithmetic/provenance audit of a completed API report.

Only standard-library GET/JSON/arithmetic is used. No scorer or production
module is imported, no score is recomputed, and no run/model is dispatched.
Exit 2 means the final report does not exist yet, never a successful audit.
"""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from urllib.request import urlopen

OUT = Path(__file__).resolve().parent
EXPERIMENT = "experiment-a879d0fa4f5e499b89a43ed8b7f7f400"
URL = "http://127.0.0.1:8016/experiments/" + EXPERIMENT


def write(name, value):
    content = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()
    (OUT / name).write_bytes(content)
    return {"path": name, "sha256": sha256(content).hexdigest()}


def valid_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def equal(left, right):
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-12)
    return left == right


def usage_arithmetic(rows):
    result = {"records": len(rows)}
    for field in ("tokens", "tool_calls", "model_calls", "cost_usd", "duration_seconds"):
        values = [row.get(field) for row in rows]
        result[field] = sum(values) if values and all(valid_number(v) for v in values) else None
        result["known_" + field] = sum(v for v in values if valid_number(v))
    result["usage_complete"] = bool(rows) and all(row.get("usage_complete") is True for row in rows) and result["tokens"] is not None and result["cost_usd"] is not None
    return result


with urlopen(URL, timeout=30) as response:
    experiment = json.load(response)
audit = {
    "schema_version": 1, "observed_at": datetime.now(timezone.utc).isoformat(),
    "experiment_id": EXPERIMENT, "source_url": URL,
    "experiment_status": experiment["status"], "comparison_manifest_hash": experiment["comparison_manifest_hash"],
    "method": "Read stored API case rows/report; independently sum stored scores and reported usage. No scorer imports/invocations, new model calls, or ledger writes.",
    "new_model_calls": 0, "ledger_writes": 0, "scoring_recomputed": False,
    "status": "pending", "checks": [], "failures": [],
    "limitations": ["Arithmetic agreement does not establish scientific correctness, support, or model improvement.", "Required-answer totals, scored completion, evidence support, and raw execution status are distinct fields; invalid or failed runs remain counted.", "Known partial usage is not a complete cost total. Summed run durations are not experiment wall time.", "Optimizer overhead is distinct from selected-arm inference costs. Evaluator overhead is explicitly separate."],
}
report = experiment.get("report")
if experiment["status"] != "complete" or not report:
    audit["pending_reason"] = "Final experiment/report is not complete; no arithmetic pass is asserted."
    audit["observed_case_statuses"] = dict(Counter(row["status"] for row in experiment["results"]))
    write("report.json", audit)
    print(json.dumps({"status": "pending", "experiment_status": experiment["status"]}))
    raise SystemExit(2)


def check(name, expected, actual):
    item = {"name": name, "passed": equal(expected, actual), "expected": expected, "actual": actual}
    audit["checks"].append(item)
    if not item["passed"]:
        audit["failures"].append(item)


def fields(prefix, expected, actual):
    for key, value in expected.items():
        check(prefix + "." + key, value, actual.get(key))


rows = experiment["results"]
expected_assignments = sorted((case["case_id"], arm) for case in experiment["cases"] for arm in (("H0", "R0") if case["split"] == "development" else ("H0", "R0", "H1")))
actual_assignments = sorted((row["case_id"], row["arm"]) for row in rows)
check("every_frozen_case_arm_retained_including_failures", expected_assignments, actual_assignments)
check("no_duplicate_case_arm_rows", len(set(actual_assignments)), len(actual_assignments))
check("completed_report_has_no_active_or_pending_assignments", [], [(r["case_id"], r["arm"], r["status"]) for r in rows if r["status"] in {"pending", "running", "awaiting_proposal", "pending_terminal_reconciliation"}])
check("report_case_rows_are_exact_experiment_rows", rows, report["case_results"])
check("all_case_rows_bind_same_manifest", True, all(row["comparison_manifest_hash"] == experiment["comparison_manifest_hash"] for row in rows))
check("report_promotion_is_exact_saved_decision", experiment["promotion"], report["promotion"])
check("report_model_is_exact_frozen_model", experiment["model_snapshot"], report["model_snapshot"])

groups = sorted({(r["split"], r["arm"]) for r in rows})
check("all_split_arm_summaries_present", groups, sorted((a["split"], a["arm"]) for a in report["arms"]))
for split, arm in groups:
    selected = [r for r in rows if r["split"] == split and r["arm"] == arm]
    scored = [r["score"] for r in selected if isinstance(r.get("score"), dict)]
    aggregate = next(a for a in report["arms"] if a["split"] == split and a["arm"] == arm)
    complete_scores = len(scored) == len(selected)
    correct = sum(s["required_correct"] for s in scored)
    total = sum(s["required_total"] for s in scored)
    expected = {
        "assigned_case_count": len(selected), "scored_case_count": len(scored), "unscored_case_count": len(selected)-len(scored),
        "required_correct": correct if complete_scores else None, "required_total": total if complete_scores else None,
        "known_required_correct": correct, "known_required_total": total,
        "required_accuracy": correct/total if complete_scores and total else None,
        "required_decisions_correct": sum(s["required_decisions_correct"] for s in scored),
        "required_decisions_total": sum(s["required_decisions_total"] for s in scored),
        "unsupported_count": sum(s["unsupported_count"] for s in scored) if complete_scores else None,
        "completed_case_count": sum(s["completed"] is True for s in scored),
        "mean_coverage": sum(s["coverage"] for s in scored)/len(scored) if scored else None,
        "failed_case_ids": [r["case_id"] for r in selected if isinstance(r.get("score"), dict) and r["score"]["completed"] is not True],
    }
    fields(split + "." + arm, expected, aggregate)
    fields(split + "." + arm + ".usage", usage_arithmetic([r["usage"] for r in selected]), aggregate["usage"])

fields("all_run_usage", usage_arithmetic([r["usage"] for r in rows]), report["run_resource_totals"])
optimizer = experiment["optimizer"]["usage"]
check("optimizer_overhead_is_exact_actual_usage", optimizer, report["optimizer_overhead"])
fields("run_plus_optimizer_usage", usage_arithmetic([r["usage"] for r in rows] + [optimizer]), report["combined_run_and_optimizer_usage"])
check("evaluator_overhead_is_exact_record", experiment["evaluation_overhead"], report["evaluation_overhead"])
check("evaluator_duration_sums_all_case_scoring_durations", sum(r.get("scoring_duration_seconds", 0) for r in rows), report["evaluation_overhead"]["duration_seconds"])

decision = experiment["promotion"]
for arm, field in (("H0", "parent_validation_usage"), ("H1", "candidate_validation_usage")):
    usage = usage_arithmetic([r["usage"] for r in rows if r["split"] == "validation" and r["arm"] == arm])
    fields(field, {"cost_usd": usage["cost_usd"] if usage["usage_complete"] else None, "known_cost_usd": usage["known_cost_usd"], "usage_complete": usage["usage_complete"]}, decision[field])
parent_cost, candidate_cost = decision["parent_validation_usage"]["cost_usd"], decision["candidate_validation_usage"]["cost_usd"]
if parent_cost and candidate_cost is not None:
    check("validation_cost_reduction_arithmetic", (parent_cost-candidate_cost)/parent_cost, decision["cost_reduction_fraction"])
check("rejected_candidate_does_not_claim_improvement", False if decision["status"] == "rejected" else bool(decision.get("model_improvement_demonstrated")), report["model_improvement_claim"])
check("rejected_candidate_does_not_claim_cost_win", False if decision["status"] == "rejected" else bool(decision.get("cost_win") and decision.get("promoted")), report["cost_win_claim"])

audit["case_status_counts"] = dict(Counter(r["status"] for r in rows))
audit["distinct_outcome_counts"] = {
    "assigned_case_rows": len(rows),
    "workflow_status_complete": sum(r["status"] == "complete" for r in rows),
    "scored_completed": sum((r.get("score") or {}).get("completed") is True for r in rows),
    "scored_support_ok": sum((r.get("score") or {}).get("support_ok") is True for r in rows),
    "scored_completed_and_support_ok": sum((r.get("score") or {}).get("completed") is True and (r.get("score") or {}).get("support_ok") is True for r in rows),
}
audit["failed_or_invalid_case_rows"] = [{k: r.get(k) for k in ("case_id", "split", "arm", "run_id", "status", "score", "usage")} for r in rows if r["status"] != "complete" or not (r.get("score") or {}).get("completed")]
audit["resource_totals"] = {k: report[k] for k in ("run_resource_totals", "optimizer_overhead", "evaluation_overhead", "combined_run_and_optimizer_usage")}
audit["inclusive_accounted_usage_calculated_by_this_audit"] = usage_arithmetic([r["usage"] for r in rows] + [optimizer, report["evaluation_overhead"]])
audit["inclusive_usage_note"] = "Adds recorded deterministic evaluator overhead to runs plus optimizer. This is an arithmetic audit total, not a new measurement or elapsed wall time; ingestion/engineering overhead is outside the recorded scope."
audit["assignment_count"] = len(rows)
audit["source"] = write("source-report.json", {"experiment_id": EXPERIMENT, "comparison_manifest_hash": experiment["comparison_manifest_hash"], "assigned_cases": experiment["cases"], "case_results": rows, "report": report})
audit["status"] = "passed" if not audit["failures"] else "failed"
write("report.json", audit)
print(json.dumps({"status": audit["status"], "checks": len(audit["checks"]), "failures": len(audit["failures"]), "case_rows": len(rows)}))
raise SystemExit(0 if audit["status"] == "passed" else 1)

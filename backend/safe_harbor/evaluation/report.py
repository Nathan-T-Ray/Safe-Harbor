"""Transparent per-case comparison, incomplete usage, and optimizer overhead."""
from __future__ import annotations

from copy import deepcopy
import math


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def usage_totals(records: list[dict]) -> dict:
    fields = ("tokens", "tool_calls", "model_calls", "cost_usd", "duration_seconds")
    result = {"records": len(records), "usage_complete": bool(records) and all(item.get("usage_complete") is True for item in records)}
    for field in fields:
        values = [item.get(field) for item in records]
        result[field] = sum(values) if values and all(_number(value) for value in values) else None
        result[f"known_{field}"] = sum(value for value in values if _number(value))
    if result["cost_usd"] is None or result["tokens"] is None:
        result["usage_complete"] = False
    return result


def build_comparison_report(experiment: dict, results: list[dict] | None = None, optimizer: dict | None = None, promotion: dict | None = None) -> dict:
    results = deepcopy(results if results is not None else experiment.get("case_results", experiment.get("results", [])))
    optimizer = deepcopy(optimizer if optimizer is not None else (experiment.get("optimizer") or {}))
    promotion = deepcopy(promotion if promotion is not None else (experiment.get("promotion") or {}))
    groups = sorted({(result.get("split", "unknown"), result.get("arm", "unknown")) for result in results})
    arms = []
    for split, arm in groups:
        cases = [result for result in results if result.get("split") == split and result.get("arm") == arm]
        scores = [case["score"] for case in cases if isinstance(case.get("score"), dict)]
        all_scored = len(scores) == len(cases)
        required = sum(score.get("required_total", 0) for score in scores)
        correct = sum(score.get("required_correct", 0) for score in scores)
        arms.append({"split": split, "arm": arm, "harness_hashes": sorted({case.get("harness_hash", "unavailable") for case in cases}), "assigned_case_count": len(cases), "scored_case_count": len(scores), "unscored_case_count": len(cases)-len(scores), "required_correct": correct if all_scored else None, "required_total": required if all_scored else None, "known_required_correct": correct, "known_required_total": required, "required_accuracy": correct / required if required and all_scored else None, "required_decisions_correct": sum(score.get("required_decisions_correct", 0) for score in scores), "required_decisions_total": sum(score.get("required_decisions_total", 0) for score in scores), "unsupported_count": sum(score.get("unsupported_count", 0) for score in scores) if all_scored else None, "completed_case_count": sum(score.get("completed") is True for score in scores), "mean_coverage": sum(score.get("coverage", 0) for score in scores) / len(scores) if scores else None, "usage": usage_totals([case.get("usage", {}) for case in cases]), "failed_case_ids": [case["case_id"] for case in cases if isinstance(case.get("score"), dict) and not case["score"].get("completed")]})
    run_usage = usage_totals([case.get("usage", {}) for case in results])
    optimizer_usage = optimizer.get("usage")
    overhead = experiment.get("evaluation_overhead")
    counted_usage = [case.get("usage", {}) for case in results]
    if optimizer_usage is not None:
        counted_usage.append(optimizer_usage)
    total = usage_totals(counted_usage)
    return {
        "schema_version": 1, "experiment_id": experiment.get("evaluation_id", experiment.get("experiment_id")), "status": experiment.get("status"), "mode": experiment.get("mode"), "model_snapshot": deepcopy(experiment.get("model_snapshot", experiment.get("comparison_manifest", {}).get("model"))), "comparison_manifest_hash": experiment.get("comparison_manifest_hash"), "arms": arms,
        "case_results": results, "optimizer": optimizer, "promotion": promotion,
        "run_resource_totals": run_usage, "optimizer_overhead": optimizer_usage,
        "evaluation_overhead": deepcopy(overhead), "combined_run_and_optimizer_usage": total,
        "case_coverage_note": "Every assigned arm/case, including failed or blocked executions, must appear in case_results. Unexecuted future splits remain explicitly pending in the experiment assignment.",
        "cost_win_claim": bool(promotion.get("cost_win") and promotion.get("promoted") and experiment.get("mode") == "real_model"),
        "model_improvement_claim": bool(promotion.get("model_improvement_demonstrated") and experiment.get("mode") == "real_model"),
        "limitations": ["Nine scenarios share three publication-derived loci; variants stay in the same split. There is one independent locus per development, validation, and final split.", "Reference answers have not been human-reviewed.", "A single paired stochastic cost result is provisional.", "Unknown usage remains unknown; known partial sums are not complete cost totals.", "Durations in arm totals sum run durations and are not the experiment's elapsed wall time.", "Optimizer and evaluator overhead must be considered separately and in total; promotion inference-cost percentage excludes this overhead.", "A rejected proposal demonstrates selection behavior, not successful self-improvement.", "No biological safety, causal attribution, novel-site discovery, whole-genome search, or billion-token performance is established."],
    }


def attach_report_to_run(ledger, run_id: str, experiment: dict, report: dict) -> dict:
    """Record a separate experiment report in a run's ordered event stream."""
    evaluation_id = f"{experiment['evaluation_id']}:comparison-report"
    record = {"evaluation_id": evaluation_id, "experiment_id": experiment["evaluation_id"], "run_id": run_id, "type": "harness_comparison_report", "report": deepcopy(report)}
    operation_id = f"experiment-report:{experiment['evaluation_id']}:{run_id}"
    def accepted(session):
        run = ledger.get_run(run_id, session)
        hashes = {value for value in (report.get("promotion", {}).get("parent_harness_hash"), report.get("promotion", {}).get("candidate_harness_hash")) if value}
        harnesses = list(ledger.db.harness_versions.find({"harness_hash": {"$in": sorted(hashes)}}, {"_id": 0}, session=session))
        event = ledger._write_event(session, run, operation_id, "experiment.reported", {"evaluations": [record], "harness_versions": harnesses})
        return {"run_id": run_id, "evaluation_id": evaluation_id, "sequence": event["sequence"]}
    return ledger.transact(operation_id, {"run_id": run_id, "evaluation": record}, accepted)

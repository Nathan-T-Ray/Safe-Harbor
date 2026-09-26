"""Frozen validation-only selection. No result is rewritten into an improvement."""
from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path

from safe_harbor.runtime.ledger import digest, now

ROOT = Path(__file__).resolve().parents[3]


def freeze_promotion_rule() -> dict:
    package = json.loads((ROOT / "data/safe_harbor/evaluator/splits.json").read_text())
    rule = {"schema_version": 1, **package["promotion_rule"], "split_hash": package["split_hash"], "comparison_scope": "paired assigned validation cases; no per-case accuracy, support, coverage, or completion regression", "candidate_completion_required": True, "benefit_scope": "required decision count, or complete actual provider-reported inference cost at equal quality; optimizer overhead reported separately"}
    rule["rule_hash"] = digest(rule)
    return rule


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _usage(results: list[dict]) -> dict:
    raw = [result.get("usage", {}) for result in results]
    complete = bool(raw) and all(item.get("usage_complete") is True and _number(item.get("cost_usd")) and item["cost_usd"] >= 0 for item in raw)
    return {"cost_usd": sum(item["cost_usd"] for item in raw) if complete else None, "usage_complete": complete, "known_cost_usd": sum(item["cost_usd"] for item in raw if _number(item.get("cost_usd")) and item["cost_usd"] >= 0)}


def decide_promotion(parent_validation: list[dict], candidate_validation: list[dict], rule: dict, mode: str = "real_model") -> dict:
    """Select from validation only; final-case results are never accepted here."""
    parent_hash = next((item.get("harness_hash") for item in parent_validation if item.get("harness_hash")), None)
    candidate_hash = next((item.get("harness_hash") for item in candidate_validation if item.get("harness_hash")), None)
    result = {"status": "blocked", "promoted": False, "parent_harness_hash": parent_hash, "candidate_harness_hash": candidate_hash, "selected_harness_hash": parent_hash, "selection_split": "validation", "rule": deepcopy(rule), "decided_at": now(), "reasons": [], "mode": mode, "model_improvement_demonstrated": False}
    if mode != "real_model":
        return {**result, "status": "operational_only", "reasons": ["Deterministic operational outcomes cannot establish model improvement or justify model promotion."]}
    if rule != freeze_promotion_rule():
        return {**result, "reasons": ["Promotion rule differs from the rule frozen before comparisons."]}
    if not parent_validation or not candidate_validation:
        return {**result, "reasons": ["Both validation arms must report every assigned case, including failures."]}
    combined = parent_validation + candidate_validation
    if any(item.get("split") != "validation" for item in combined):
        return {**result, "reasons": ["Only validation results may select a harness; development and final cases are excluded."]}
    left = {item.get("case_id"): item for item in parent_validation}
    right = {item.get("case_id"): item for item in candidate_validation}
    if len(left) != len(parent_validation) or len(right) != len(candidate_validation) or set(left) != set(right) or None in left:
        return {**result, "reasons": ["Validation case coverage is missing, duplicated, or differs between arms."]}
    from safe_harbor.evaluation.cases import load_cases
    assigned_ids = {case["case_id"] for case in load_cases("validation")}
    if set(left) != assigned_ids:
        return {**result, "reasons": ["Validation results do not cover the complete frozen assignment."]}
    experiment_ids = {item.get("experiment_id") for item in combined}
    manifest_hashes = {item.get("comparison_manifest_hash") for item in combined}
    if len(experiment_ids) != 1 or None in experiment_ids or len(manifest_hashes) != 1 or None in manifest_hashes or "" in manifest_hashes:
        return {**result, "reasons": ["Frozen experiment/model/evidence/budget comparability is not established."]}
    if len({item.get("harness_hash") for item in parent_validation}) != 1 or len({item.get("harness_hash") for item in candidate_validation}) != 1 or not parent_hash or not candidate_hash or parent_hash == candidate_hash:
        return {**result, "reasons": ["Each arm must use one distinct frozen harness version."]}
    result.update(experiment_id=next(iter(experiment_ids)), comparison_manifest_hash=next(iter(manifest_hashes)))
    regressions, per_case = [], []
    parent_decisions = candidate_decisions = 0
    all_complete = True
    equal_quality = True
    fields = ("required_correct", "required_total", "required_decisions_correct", "required_decisions_total", "unsupported_count", "coverage")
    for case_id in sorted(left):
        before, after = left[case_id].get("score") or {}, right[case_id].get("score") or {}
        if any(not _number(score.get(field)) or score[field] < 0 for score in (before, after) for field in fields):
            return {**result, "reasons": [f"Required scoring values are absent or invalid for {case_id}."]}
        if before["required_total"] <= 0 or before["required_total"] != after["required_total"] or before["required_decisions_total"] != after["required_decisions_total"]:
            return {**result, "reasons": [f"Assigned answer denominators differ for {case_id}."]}
        for score in (before, after):
            if score["required_correct"] > score["required_total"] or score["required_decisions_correct"] > score["required_decisions_total"] or score["coverage"] > 1 or not isinstance(score.get("completed"), bool) or not isinstance(score.get("support_ok"), bool):
                return {**result, "reasons": [f"Score bounds or support/completion flags are invalid for {case_id}."]}
        before_accuracy = before["required_correct"] / before["required_total"]
        after_accuracy = after["required_correct"] / after["required_total"]
        failures = []
        if after_accuracy < before_accuracy:
            failures.append("required-answer accuracy declined")
        if after["required_decisions_correct"] < before["required_decisions_correct"]:
            failures.append("correct required decisions declined")
        if after["unsupported_count"] > before["unsupported_count"] or before["support_ok"] and not after["support_ok"]:
            failures.append("evidence support declined")
        if after["coverage"] < before["coverage"]:
            failures.append("required-answer coverage declined")
        if before["completed"] and not after["completed"]:
            failures.append("completion declined")
        all_complete = all_complete and after["completed"]
        equal_quality = equal_quality and all(before[key] == after[key] for key in ("required_correct", "required_decisions_correct", "unsupported_count", "coverage", "completed", "support_ok"))
        parent_decisions += before["required_decisions_correct"]
        candidate_decisions += after["required_decisions_correct"]
        regressions.extend(f"{case_id}: {failure}" for failure in failures)
        per_case.append({"case_id": case_id, "parent_required_accuracy": before_accuracy, "candidate_required_accuracy": after_accuracy, "parent_coverage": before["coverage"], "candidate_coverage": after["coverage"], "regressions": failures})
    before_usage, after_usage = _usage(parent_validation), _usage(candidate_validation)
    reduction = None
    if before_usage["usage_complete"] and after_usage["usage_complete"] and before_usage["cost_usd"] > 0:
        reduction = (before_usage["cost_usd"] - after_usage["cost_usd"]) / before_usage["cost_usd"]
    decision_gain = candidate_decisions - parent_decisions
    cost_win = bool(equal_quality and reduction is not None and reduction >= rule["cost_reduction_fraction"])
    result.update(per_case=per_case, regressions=regressions, required_decision_gain=decision_gain, parent_validation_usage=before_usage, candidate_validation_usage=after_usage, cost_reduction_fraction=reduction, cost_win=cost_win, equal_quality=equal_quality, cost_conclusion_provisional=cost_win, cost_interpretation="One paired comparison is provisional; optimizer and full evaluation overhead are excluded from inference-cost reduction and reported separately.")
    if regressions:
        return {**result, "status": "rejected", "reasons": regressions}
    if not all_complete:
        return {**result, "status": "rejected", "reasons": ["The candidate did not complete all assigned validation cases."]}
    if decision_gain > 0 or cost_win:
        reason = "More correct required decisions without per-case quality regression." if decision_gain > 0 else "At least 15% measured provider-reported inference-cost reduction at equal quality; provisional single-pair result."
        return {**result, "status": "promoted", "promoted": True, "selected_harness_hash": candidate_hash, "model_improvement_demonstrated": True, "reasons": [reason]}
    reasons = ["No predefined measurable benefit was established at non-declining quality."]
    if not before_usage["usage_complete"] or not after_usage["usage_complete"]:
        reasons.append("Missing or uncertain provider usage prevents a cost-win claim.")
    return {**result, "status": "rejected", "reasons": reasons}


def save_promotion(ledger, experiment_id: str, decision: dict) -> dict:
    record = {"evaluation_id": f"promotion:{experiment_id}", "experiment_id": experiment_id, "type": "harness_selection", **deepcopy(decision)}
    existing = ledger.db.evaluations.find_one({"evaluation_id": record["evaluation_id"]}, {"_id": 0})
    if existing is not None:
        return existing
    ledger.db.evaluations.insert_one(deepcopy(record))
    return record

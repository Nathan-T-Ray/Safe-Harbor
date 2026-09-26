"""Evaluator-only required-output scoring. Never imported into worker tools.

All assigned required keys enter the denominator. Missing/failed cases cannot
improve accuracy by omitting difficult outputs. Biological interpretation rules
come from independently authored references, not from production calculations.
"""
from __future__ import annotations
import math
import re

from .baselines import LIMITATION_CODES, NUMERIC_KEYS


# Bounded textual guardrails, not a claim of complete semantic validation.
# Remove code strings first so copying a code alone never supplies an explanation.
LIMITATION_PATTERNS = {
    "significant_only_tables": (r"significan", r"only|filter|select|not.*(?:all|full)|incomplete"),
    "reference_not_personal_h1": (r"reference|grch38", r"h1|personal|individual", r"not|isn.t|rather|distinct"),
    "control_overlap_not_causality": (r"control|overlap", r"causal|causation", r"not|cannot|doesn.t|without|no "),
    "distance_not_safety": (r"distance|proximity", r"safe|safety", r"not|cannot|doesn.t|without|no "),
    "missing_cancer_regulatory_evidence": (r"cancer", r"regulatory|dhs|dnase|ultraconserv", r"missing|unavailable|incomplete|absent|not.*(?:available|ingest|establish)"),
    "unmapped_de_ids": (r"unmapped|not.*map|mapping.*incomplete|unresolved.*(?:ids|identif)", r"gene|identif|ids|ensembl|de "),
    "source_count_discrepancy": (r"count|139|119", r"discrepan|disagree|differ|mismatch|inconsisten"),
    "controls_unavailable": (r"control", r"unavailable|withheld|missing|withdrawn|not available"),
    "cell_context_not_transferable": (r"h1", r"h9", r"different|distinct|not|cannot|doesn.t|transfer|generaliz"),
}


def _limitation_explained(code: str, limitations) -> bool:
    if not isinstance(limitations, list):
        return False
    for item in limitations:
        if not isinstance(item, str):
            continue
        cleaned = item
        for known_code in LIMITATION_CODES:
            cleaned = cleaned.replace(known_code, "")
        if len(cleaned.strip()) >= 24 and all(re.search(pattern, cleaned, re.I) for pattern in LIMITATION_PATTERNS.get(code, ())):
            return True
    return False


def _screen_support(artifacts: list[dict], claimed) -> bool:
    required = {"outside_gene_body", "tss_distance", "mirna_distance", "lncrna_distance", "cancer_gene_distance", "outside_dhs_buffer", "outside_ultraconserved_regions"}
    for artifact in artifacts:
        data = artifact.get("data", {})
        if data.get("tool_name") != "screen_candidate":
            continue
        criteria = {item.get("criterion_id"): item.get("status") for item in data.get("calculation", {}).get("criterion_results", [])}
        statuses = [criteria.get(key, "incomplete") for key in required]
        aggregate = "incomplete" if "incomplete" in statuses else "fail" if "fail" in statuses else "pass"
        if claimed == aggregate and data.get("calculation", {}).get("screen_status") == aggregate:
            return True
    return False


def _number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _equal_number(value, expected, tolerance=0) -> bool:
    return _number(value) and _number(expected) and abs(value-expected) <= tolerance


def extract_run_output(snapshot: dict) -> dict:
    tasks = {t["task_id"]: t for t in snapshot.get("tasks", [])}
    traces = [a for a in snapshot.get("artifacts", []) if a.get("kind") == "worker_trace"]
    priorities = {"publish_shortlist": 3, "review_candidate": 2, "assess_candidate": 1}
    eligible = [a for a in traces if tasks.get(a.get("provenance", {}).get("task_id"), {}).get("kind") in priorities
                and tasks[a["provenance"]["task_id"]]["status"] == "complete"]
    eligible.sort(key=lambda a: (priorities[tasks[a["provenance"]["task_id"]]["kind"]], a.get("created_at", ""), a["artifact_id"]))
    selected = eligible[-1] if eligible else None
    return {"proposal": selected.get("data", {}).get("proposal", {}) if selected else {},
            "selected_trace_artifact_id": selected["artifact_id"] if selected else None,
            "selected_task_id": selected.get("provenance", {}).get("task_id") if selected else None,
            "snapshot": snapshot, "completed": snapshot.get("run", {}).get("status") == "complete"}


def _consumed_artifacts(trace: dict) -> list[dict]:
    snapshot = trace.get("snapshot", {})
    tasks = {t["task_id"]: t for t in snapshot.get("tasks", [])}
    versions = snapshot.get("run", {}).get("evidence_versions", {})
    frontier, visited, allowed = [trace.get("selected_task_id")], set(), set()
    while frontier:
        task_id = frontier.pop()
        task = tasks.get(task_id)
        if not task or task_id in visited or task.get("status") != "complete":
            continue
        visited.add(task_id)
        if any(versions.get(read["key"]) != read["version"] for read in task.get("input_read_set", [])):
            continue
        allowed.update(task.get("result_artifact_ids", []))
        frontier.extend(task.get("depends_on", []))
    return [a for a in snapshot.get("artifacts", []) if a.get("artifact_id") in allowed]


def _available_support(artifacts: list[dict]) -> tuple[set[str], dict[str, list[tuple[float, set[str]]]]]:
    ids, metrics = set(), {}
    def add(key, value, supporting_ids):
        if _number(value):
            metrics.setdefault(key, []).append((value, supporting_ids))
    for artifact in artifacts:
        if artifact.get("kind") != "scientific_tool_result":
            continue
        data = artifact.get("data", {})
        supporting_ids = {artifact["artifact_id"], *artifact.get("evidence_ids", []), *data.get("evidence_ids", [])}
        ids.update(supporting_ids)
        c = data.get("calculation", {})
        if c.get("cell_context", data.get("cell_context", "H1")) not in ("H1", "H1 human embryonic stem cells") or c.get("status") == "unavailable":
            continue
        name = data.get("tool_name")
        values = {}
        if name == "expression_comparison":
            values = {"de_count": c.get("targeted", {}).get("unique_versioned_gene_count"),
                      "control_de_count": c.get("independent_untargeted", {}).get("unique_versioned_gene_count")}
        elif name == "control_overlap":
            values = {key: c.get(field) for key, field in (("de_count", "targeted_de_count"), ("control_de_count", "independent_untargeted_de_count"),
                      ("shared_de_count", "shared_count"), ("targeted_only_count", "targeted_only_count"))}
            values["overlap_fraction"] = c.get("shared_fraction_of_targeted", {}).get("value")
        elif name == "screen_candidate":
            if c.get("nearest_gene_bodies"):
                values["min_gene_body_gap_bp"] = c["nearest_gene_bodies"][0].get("interval_gap_bp")
            if c.get("nearest_transcript_tss"):
                values["min_tss_base_distance_bp"] = c["nearest_transcript_tss"][0].get("nearest_reference_base_distance_bp")
        elif name == "gene_proximity":
            values["mapped_de_count"] = c.get("gencode_mapped_gene_count")
            if c.get("nearest_de_genes"):
                values["nearest_mapped_de_gene_gap_bp"] = c["nearest_de_genes"][0].get("interval_gap_bp")
        for key, value in values.items():
            add(key, value, supporting_ids)
    return ids, metrics


def score_case(case: dict, reference: dict, trace: dict) -> dict:
    proposal = trace.get("proposal", {})
    if not isinstance(proposal, dict):
        proposal = {}
    numbers = proposal.get("numerical_findings", {})
    numbers = numbers if isinstance(numbers, dict) else {}
    numeric_evidence = proposal.get("numerical_evidence", {})
    numeric_evidence = numeric_evidence if isinstance(numeric_evidence, dict) else {}
    actual_codes = proposal.get("limitation_codes", [])
    actual_codes = set(actual_codes) if isinstance(actual_codes, list) and all(isinstance(v, str) for v in actual_codes) else set()
    required_numbers = reference.get("required_numbers", {})
    required_decisions = reference.get("required_decisions", {})
    required_codes = reference.get("required_limitations", [])
    tolerances = reference.get("tolerances", {})
    consumed = _consumed_artifacts(trace)
    evidence_ids, tool_metrics = _available_support(consumed)
    details, unsupported = [], []
    for key, expected in required_numbers.items():
        value = numbers.get(key)
        correct = _equal_number(value, expected, tolerances.get(key, 0))
        citations = numeric_evidence.get(key, [])
        matching_ids = set().union(*(ids for measured, ids in tool_metrics.get(key, []) if _equal_number(value, measured, tolerances.get(key, 1e-9))))
        supported = isinstance(citations, list) and bool(citations) and all(isinstance(i, str) and i in matching_ids for i in citations)
        if key in numbers and value is not None and not supported:
            unsupported.append({"kind": "unsupported_numeric_finding", "key": key})
        details.append({"kind": "number", "key": key, "expected": expected, "actual": value,
                        "present": key in numbers and value is not None, "correct": correct, "supported": supported})
    for key, expected in required_decisions.items():
        permitted = expected if isinstance(expected, list) else [expected]
        value = proposal.get(key)
        if value is not None and value not in permitted:
            unsupported.append({"kind": "decision_contradicts_reference", "key": key})
        details.append({"kind": "decision", "key": key, "expected": permitted, "actual": value,
                        "present": value is not None, "correct": value in permitted})
        if key == "screen_status" and value is not None and not _screen_support(consumed, value):
            unsupported.append({"kind": "screen_aggregation_not_supported_by_required_criteria", "key": key})
    for code in required_codes:
        explained = _limitation_explained(code, proposal.get("limitations"))
        if code in actual_codes and not explained:
            unsupported.append({"kind": "limitation_code_without_concrete_explanation", "key": code})
        details.append({"kind": "limitation", "key": code, "present": code in actual_codes,
                        "correct": code in actual_codes and explained})
    for key in set(numbers)-set(NUMERIC_KEYS):
        unsupported.append({"kind": "unknown_numeric_metric", "key": key})
    validation_errors = []
    for artifact in consumed:
        if artifact.get("provenance", {}).get("task_id") != trace.get("selected_task_id"):
            continue
        data = artifact.get("data", {})
        validated = data.get("validated_summary", data.get("assessment", {}))
        validation_errors.extend(validated.get("validation_errors", []))
    unsupported.extend({"kind": "runtime_rejected_proposal", "reason": error} for error in validation_errors)
    controls_available = case.get("controls_available", True)
    if controls_available and "controls_unavailable" in actual_codes:
        unsupported.append({"kind": "contradictory_limit", "key": "controls_unavailable"})
    if not controls_available:
        for key in ("control_de_count", "shared_de_count", "targeted_only_count", "overlap_fraction"):
            if numbers.get(key) is not None:
                unsupported.append({"kind": "unavailable_evidence_claim", "key": key})
    for code in actual_codes-set(LIMITATION_CODES):
        unsupported.append({"kind": "unknown_limitation_code", "key": code})
    if proposal.get("screen_status") == "pass":
        unsupported.append({"kind": "missing_required_evidence_claimed_pass", "key": "screen_status"})
    if proposal.get("evidence_status") == "supported_for_endpoint":
        unsupported.append({"kind": "endpoint_support_not_established_by_rubric", "key": "evidence_status"})
    declared = proposal.get("evidence_ids", [])
    if isinstance(declared, list):
        unsupported.extend({"kind": "out_of_run_evidence", "key": str(i)} for i in declared if not isinstance(i,str) or i not in evidence_ids)
    decisions = [d for d in details if d["kind"] == "decision"]
    correct = sum(bool(d["correct"]) for d in details)
    total = len(details)
    numeric_support = all(d.get("supported", True) for d in details if d["kind"] == "number" and d["present"])
    completed = bool(trace.get("completed") and trace.get("selected_trace_artifact_id") and proposal.get("conclusion") and not validation_errors)
    return {"required_correct": correct, "required_total": total, "required_accuracy": correct/total if total else 0,
            "required_decisions_correct": sum(bool(d["correct"]) for d in decisions), "required_decisions_total": len(decisions),
            "unsupported_count": len(unsupported), "unsupported_findings": unsupported,
            "coverage": sum(bool(d["present"]) for d in details)/total if total else 0,
            "completed": completed, "support_ok": completed and not unsupported and numeric_support,
            "details": details, "reference_review_status": reference.get("review_status", "not_human_reviewed"),
            "limitations": ["Structured required outputs, trace-backed numerical support, required-criterion aggregation, and bounded textual limitation checks are applied. Text heuristics can miss valid paraphrases or misleading prose; independent semantic claim review remains required."]}

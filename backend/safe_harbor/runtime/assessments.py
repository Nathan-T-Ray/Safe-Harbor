"""Validate model proposals against consumed, context-correct numeric evidence."""
from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DECISIONS = ("not_justified_by_available_evidence", "justified_for_named_criterion", "unresolved")
METRICS = ("de_count", "control_de_count", "shared_de_count", "targeted_only_count", "overlap_fraction", "min_gene_body_gap_bp", "min_tss_base_distance_bp", "mapped_de_count", "nearest_mapped_de_gene_gap_bp")

OUTPUT_CONTRACT = (
    "Return one JSON object: conclusion (text); exclusion_decision ('not_justified_by_available_evidence', "
    "'justified_for_named_criterion', or 'unresolved'); numerical_findings (object with these keys: " + ", ".join(METRICS) + "); numerical_evidence (object mapping each non-null metric to a list of exact consumed artifact IDs or source evidence IDs); "
    "evidence_ids (list); unresolved_questions (list); limitations (list); limitation_codes (list); "
    "criterion_id (only when exclusion is justified for a named failed criterion); screen_status and evidence_status. "
    "Use null for missing numerical evidence, never zero. Screen status obeys the frozen required criteria. "
    "Expression-control overlap is shared_count/targeted_de_count. Distinguish interval gap from nearest reference base distance. "
    "Use evidence_status unknown unless an explicit named experimental endpoint result supports more. Overall suitability is not established."
    " limitation_codes vocabulary: significant_only_tables, reference_not_personal_h1, control_overlap_not_causality, "
    "distance_not_safety, missing_cancer_regulatory_evidence, unmapped_de_ids, source_count_discrepancy, controls_unavailable, cell_context_not_transferable."
)


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    conclusion: str = Field(min_length=1, max_length=6000)
    exclusion_decision: Literal["not_justified_by_available_evidence", "justified_for_named_criterion", "unresolved"]
    numerical_findings: dict[str, int | float | None]
    numerical_evidence: dict[str, list[str]] = Field(default_factory=dict)
    evidence_ids: list[str]
    unresolved_questions: list[str]
    limitations: list[str]
    limitation_codes: list[str] = Field(default_factory=list)
    criterion_id: str | None = None
    screen_status: Literal["pass", "fail", "incomplete"] = "incomplete"
    evidence_status: Literal["supported_for_endpoint", "conflicting", "unknown"] = "unknown"


def metric_values(data: dict) -> dict:
    c, tool = data.get("calculation", {}), data.get("tool_name")
    if c.get("cell_context", "H1") not in ("H1", "H1 human embryonic stem cells"):
        return {}
    if c.get("status") == "unavailable":
        return {}
    if tool == "expression_comparison":
        result = {"de_count": c.get("targeted", {}).get("unique_versioned_gene_count")}
        if "independent_untargeted" in c:
            result["control_de_count"] = c["independent_untargeted"].get("unique_versioned_gene_count")
        return result
    if tool == "control_overlap":
        return {"de_count": c.get("targeted_de_count"), "control_de_count": c.get("independent_untargeted_de_count"), "shared_de_count": c.get("shared_count"), "targeted_only_count": c.get("targeted_only_count"), "overlap_fraction": c.get("shared_fraction_of_targeted", {}).get("value")}
    if tool == "gene_proximity":
        nearest = c.get("nearest_de_genes", [])
        return {"mapped_de_count": c.get("gencode_mapped_gene_count"), "nearest_mapped_de_gene_gap_bp": nearest[0].get("interval_gap_bp") if nearest else None}
    if tool == "screen_candidate":
        bodies, starts = c.get("nearest_gene_bodies", []), c.get("nearest_transcript_tss", [])
        return {"min_gene_body_gap_bp": bodies[0].get("interval_gap_bp") if bodies else None, "min_tss_base_distance_bp": starts[0].get("nearest_reference_base_distance_bp") if starts else None}
    return {}


def validate_proposal(raw: dict, artifacts: list[dict], criterion_results: list[dict], screen_status: str, controls_available: bool) -> tuple[dict, list[str]]:
    errors = []
    try:
        proposal = Proposal.model_validate(raw).model_dump()
    except Exception as exc:
        return {}, [f"Structured assessment schema rejected: {exc}"]
    if set(proposal["numerical_findings"]) - set(METRICS):
        errors.append("Unknown numerical metric")
    allowed_ids, support = set(), {}
    for artifact in artifacts:
        ids = {artifact["artifact_id"], *artifact.get("evidence_ids", []), *artifact.get("data", {}).get("evidence_ids", [])}
        allowed_ids.update(ids)
        for metric, value in metric_values(artifact.get("data", {})).items():
            if value is not None:
                support.setdefault(metric, []).append((value, ids))
    if set(proposal["evidence_ids"]) - allowed_ids:
        errors.append("Proposal cites evidence outside its consumed manifest")
    for metric in METRICS:
        if metric not in proposal["numerical_findings"]:
            errors.append(f"Required numerical field omitted: {metric}")
            continue
        value = proposal["numerical_findings"][metric]
        if value is None:
            continue
        cited = set(proposal["numerical_evidence"].get(metric, []))
        if not math.isfinite(value) or not cited or cited - allowed_ids:
            errors.append(f"Unverifiable numerical evidence for {metric}")
            continue
        if not any(math.isclose(float(value), float(expected), rel_tol=1e-8, abs_tol=1e-9) and cited & ids for expected, ids in support.get(metric, [])):
            errors.append(f"Numerical value is not supported by consumed evidence: {metric}")
    if proposal["screen_status"] != screen_status:
        errors.append("Proposed screen status contradicts the frozen required-criteria aggregation")
    if proposal["evidence_status"] != "unknown":
        errors.append("A general expression concern does not establish a validated experimental suitability endpoint")
    if re.search(r"\b(?:is|are|proven|established|demonstrated)\s+(?:a\s+)?safe\b", proposal["conclusion"], re.I):
        errors.append("Global safety conclusion is not permitted")
    if proposal["exclusion_decision"] == "justified_for_named_criterion":
        if not any(item["criterion_id"] == proposal.get("criterion_id") and item["status"] == "fail" for item in criterion_results):
            errors.append("Named exclusion requires an actually failed frozen criterion")
    if proposal["exclusion_decision"] == "not_justified_by_available_evidence":
        if not controls_available or any(proposal["numerical_findings"].get(key) is None for key in ("de_count", "control_de_count", "shared_de_count")):
            errors.append("Resolving the expression exclusion concern requires available targeted and control evidence")
    if not proposal["limitations"]:
        errors.append("Assessment must retain limitations")
    return proposal, errors

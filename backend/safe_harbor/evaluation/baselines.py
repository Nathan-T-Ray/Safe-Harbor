"""Competent frozen comparison arms and a common answer contract, never gold values."""
from __future__ import annotations
from copy import deepcopy

from safe_harbor.harness import get_harness, save_harness
from safe_harbor.harness.specification import IMMUTABLE_CONSTRAINTS, SCIENTIFIC_INSTRUCTIONS, canonical_hash, validate_harness

NUMERIC_KEYS = (
    "de_count", "control_de_count", "shared_de_count", "targeted_only_count", "overlap_fraction",
    "min_gene_body_gap_bp", "min_tss_base_distance_bp", "mapped_de_count", "nearest_mapped_de_gene_gap_bp",
)
LIMITATION_CODES = (
    "significant_only_tables", "reference_not_personal_h1", "control_overlap_not_causality",
    "distance_not_safety", "missing_cancer_regulatory_evidence", "unmapped_de_ids",
    "source_count_discrepancy", "controls_unavailable", "cell_context_not_transferable",
)
OUTPUT_CONTRACT = (
    "Return numerical_findings as an object with applicable keys " + ", ".join(NUMERIC_KEYS) + ". "
    "Include all nine keys. Values must be numbers copied from deterministic tool results; use null for unavailable values, never invent zero. "
    "de_count is targeted unique versioned Ensembl DE IDs; control_de_count is the independent untargeted count; "
    "shared_de_count and targeted_only_count use the control-overlap sets; overlap_fraction is shared/targeted. "
    "min_gene_body_gap_bp is the nearest gene-body Bioframe gap; min_tss_base_distance_bp uses the explicitly frozen "
    "nearest-reference-base distance; mapped_de_count and nearest_mapped_de_gene_gap_bp refer to GENCODE-mapped DE genes. "
    "Provide numerical_evidence as an object mapping each reported numeric key to exact consumed source/artifact IDs. "
    "Provide exclusion_decision ('justified_for_named_criterion', 'not_justified_by_available_evidence', or 'unresolved'), "
    "screen_status ('pass','fail','incomplete'), evidence_status ('supported_for_endpoint','conflicting','unknown'), "
    "conclusion, evidence_ids, unresolved_questions, and plain-text limitations. "
    "Also provide limitation_codes using only applicable entries from " + ", ".join(LIMITATION_CODES) + ". "
    "Explain each selected code in limitations. Do not claim controls_unavailable when control evidence is present. "
    "These are output names and scientific guardrails, not reference answers. Every assigned required output is evaluated, "
    "including missing answers. Reference answers and evaluator files are inaccessible through approved tools."
)

DEFAULT_BUDGET = {"token_limit": 200000, "tool_limit": 40, "cost_limit_usd": 5.0}


def _r0_role(role_id: str, kind: str, dependencies: list[str], tools: list[str], instructions: str) -> dict:
    return {"role_id": role_id, "kind": kind,
            "question": "Do these measured expression changes justify excluding this candidate region?",
            "depends_on": dependencies, "allowed_tools": tools, "context_policy": "numerical_first",
            "instructions": SCIENTIFIC_INSTRUCTIONS + instructions + " " + OUTPUT_CONTRACT,
            "decision_target": "expression_exclusion_concern",
            "completion_condition": "Persist exact source-backed calculations and a scoped synthesis with unresolved requirements.",
            "max_tool_calls": len(tools), "max_model_calls": 1}


def frozen_baselines(database=None) -> dict[str, dict]:
    h0 = deepcopy(get_harness())
    # Strong, output-complete instructions shared with revised harnesses. No
    # missing tools, intentionally weak prompt, or hidden control evidence.
    for role in h0["roles"]:
        if role["kind"] in ("assess_candidate", "review_candidate", "publish_shortlist"):
            role["instructions"] += " " + OUTPUT_CONTRACT
    h0["description"] = "Frozen competent control-aware H0; same complete source/tool access and answer contract as every comparison arm."
    h0["harness_hash"] = canonical_hash(h0)
    h0 = validate_harness(h0)
    synthesis_tools = []  # Retrieval is a uniform runtime capability, never a mutable science tool.
    r0 = {"schema_version": 1, "name": "R0 · all checks plus one synthesis", "parent_hash": None,
          "patch": None, "proposal_mode": "developer_authored_fixed_baseline", "baseline_arm": "R0",
          "immutable_constraints": deepcopy(IMMUTABLE_CONSTRAINTS),
          "description": "Every relevant approved deterministic check executes once, followed by one call to the same model; no agent planning or extra model review calls.",
          "roles": [
              _r0_role("fixed_screen", "screen_regions", [], ["inspect_candidate", "screen_candidate", "list_evidence", "reference_sequence"],
                       "The runtime runs each listed check deterministically. No model call belongs to this fixed analysis stage."),
              _r0_role("fixed_compare", "compute_features", [], ["table_slice", "expression_comparison", "control_overlap", "gene_proximity"],
                       "The runtime runs all expression, control and proximity calculations once. Preserve missing evidence and source discrepancies."),
              _r0_role("synthesize", "assess_candidate", ["fixed_screen", "fixed_compare"], synthesis_tools,
                       "Synthesize all available relevant computed outputs in one model call. Consider control variation, thresholds, identifier mapping, distances, source discrepancies and uncertainty. Do not infer causality or global safety.")],
    }
    r0["harness_hash"] = canonical_hash(r0)
    r0 = validate_harness(r0)
    if database is not None:
        save_harness(h0, database=database)
        save_harness(r0, database=database)
    return {"H0": h0, "R0": r0}

"""Recompute counts and set overlaps from preserved significant-only tables."""
from __future__ import annotations

from collections import Counter
from statistics import mean

from .catalog import _load
from .calculations import candidate_record

THRESHOLDS = {"abs_log2_fold_change_gte": 1, "fdr_lte": 0.01}


def expression_rows(candidate_id: str, cell_context: str = "H1", contrast: str = "candidate") -> list[dict]:
    candidate_record(candidate_id)
    if cell_context not in ("H1", "H9"):
        raise ValueError("Unknown cell context; only H1 and separately labeled H9 are available")
    if contrast not in ("candidate", "untargeted"):
        raise ValueError("Unknown contrast")
    return _load("expression")[cell_context][candidate_id if contrast == "candidate" else "untargeted"]


def _qualifies(row: dict) -> bool:
    return abs(row["log2_fold_change"]) >= 1 and row["fdr"] <= 0.01


def _counts(rows: list[dict]) -> dict:
    selected = [row for row in rows if _qualifies(row)]
    ids = Counter(row["gene_id_version"] for row in selected)
    stable = Counter(row["gene_id"] for row in selected)
    return {"input_rows": len(rows), "qualifying_rows": len(selected), "unique_versioned_gene_count": len(ids),
            "unique_stable_gene_count": len(stable), "upregulated_gene_count": len({r["gene_id_version"] for r in selected if r["log2_fold_change"] > 0}),
            "downregulated_gene_count": len({r["gene_id_version"] for r in selected if r["log2_fold_change"] < 0}),
            "duplicate_versioned_ids": sorted(k for k,v in ids.items() if v > 1),
            "duplicate_stable_ids": sorted(k for k,v in stable.items() if v > 1),
            "nonqualifying_row_numbers": [r["source"]["row"] for r in rows if not _qualifies(r)]}


def numeric_row(row: dict) -> dict:
    """Original numerical inputs; source's interpretive/shared flags excluded."""
    return {key: row[key] for key in ("gene_id_version", "gene_id", "gene_name", "log2_fold_change", "p_value",
                                      "fdr", "source_chromosome", "source_start", "source_end", "source")}


def expression_comparison(candidate_id: str, cell_context: str = "H1", controls_available: bool = True) -> dict:
    rows = expression_rows(candidate_id, cell_context)
    result = {"status": "computed", "cell_context": cell_context, "assay": "RNA-seq, DEseq2",
              "thresholds": THRESHOLDS, "count_unit": "unique versioned Ensembl gene identifier",
              "targeted_contrast": f"{candidate_record(candidate_id)['name']} targeted {cell_context} clone versus reference untargeted {cell_context}",
              "targeted": _counts(rows), "table_coverage": "significant-only",
              "all_measured_genes_denominator": None,
              "source_rows_preview": [numeric_row(row) for row in rows[:3]],
              "source_discrepancies": [],
              "limitations": ["These tables contain significant results only, not raw counts or the full measured-gene universe.",
                              "No DE-count threshold here establishes whether this candidate should be excluded.",
                              "The analysis recomputes counts from published tables; it does not rerun DEseq2 from sequencing reads."]}
    if controls_available:
        control = expression_rows(candidate_id, cell_context, "untargeted")
        result["independent_untargeted_contrast"] = f"Independent untargeted {cell_context} culture versus the same reference untargeted {cell_context}"
        result["independent_untargeted"] = _counts(control)
        result["count_difference_targeted_minus_control"] = result["targeted"]["unique_versioned_gene_count"] - result["independent_untargeted"]["unique_versioned_gene_count"]
    else:
        result["independent_untargeted"] = {"status": "unavailable", "reason": "Prepared operational revision withdraws control evidence."}
        result["limitations"].append("Missing control evidence cannot be treated as zero control expression changes.")
    if candidate_id == "keppel-19" and cell_context == "H1":
        result["source_discrepancies"].append({"calculated_workbook_count": result["targeted"]["unique_versioned_gene_count"],
                                               "article_reported_count": 119, "status": "unresolved",
                                               "reason": "139 unique populated source rows satisfy the stated thresholds. No rows were removed to force agreement with article prose."})
    return result


def control_overlap(candidate_id: str, cell_context: str = "H1", controls_available: bool = True) -> dict:
    candidate_record(candidate_id)
    if not controls_available:
        return {"status": "unavailable", "cell_context": cell_context,
                "reason": "Control evidence is withdrawn by a prepared operational revision.",
                "limitations": ["Missing evidence is not an empty gene set or a negative biological result."]}
    target_rows = [r for r in expression_rows(candidate_id, cell_context) if _qualifies(r)]
    control_rows = [r for r in expression_rows(candidate_id, cell_context, "untargeted") if _qualifies(r)]
    target = {r["gene_id_version"]: r for r in target_rows}
    controls = {r["gene_id_version"]: r for r in control_rows}
    intersection = sorted(target.keys() & controls.keys())
    union = target.keys() | controls.keys()
    same_direction = [gene for gene in intersection if (target[gene]["log2_fold_change"] > 0) == (controls[gene]["log2_fold_change"] > 0)]
    stable_target = {r["gene_id"] for r in target_rows}
    stable_controls = {r["gene_id"] for r in control_rows}
    # Diagnose source precomputed flags instead of relying on them.
    flag_name = f"shared_with_WT_{cell_context}"
    mismatches = [r["source"]["row"] for r in target_rows if bool(r["source_overlap_flags"].get(flag_name)) != (r["gene_id_version"] in controls)]
    return {"status": "computed", "cell_context": cell_context, "assay": "RNA-seq, DEseq2",
            "thresholds": THRESHOLDS, "set_unit": "unique versioned Ensembl gene identifier",
            "targeted_de_count": len(target), "independent_untargeted_de_count": len(controls),
            "shared_count": len(intersection), "targeted_only_count": len(target.keys()-controls.keys()),
            "control_only_count": len(controls.keys()-target.keys()), "union_count": len(union),
            "shared_fraction_of_targeted": {"numerator": len(intersection), "denominator": len(target), "value": len(intersection)/len(target) if target else None},
            "shared_fraction_of_control": {"numerator": len(intersection), "denominator": len(controls), "value": len(intersection)/len(controls) if controls else None},
            "jaccard": {"numerator": len(intersection), "denominator": len(union), "value": len(intersection)/len(union) if union else None},
            "shared_same_direction_count": len(same_direction), "shared_opposite_direction_count": len(intersection)-len(same_direction),
            "stable_id_intersection_count": len(stable_target & stable_controls),
            "shared_gene_ids": intersection, "source_overlap_flag_mismatch_rows": mismatches,
            "shared_rows_preview": [{"gene_id_version": gene, "gene_name": target[gene]["gene_name"],
                                     "targeted_log2_fold_change": target[gene]["log2_fold_change"],
                                     "control_log2_fold_change": controls[gene]["log2_fold_change"],
                                     "targeted_source": target[gene]["source"], "control_source": controls[gene]["source"]}
                                    for gene in intersection[:6]],
            "limitations": ["Set overlap was recomputed from gene identifiers; precomputed source flags did not determine this result.",
                            "Independent untargeted variation contextualizes changes but does not establish their cause.",
                            "Overlap cannot prove biological safety or automatically justify excluding or retaining a candidate."]}


def qpcr_summary(candidate_id: str, cell_context: str = "H1") -> dict:
    c = candidate_record(candidate_id)
    study = next(w for w in _load("workbook_inventory") if w["source_id"] == "elife-79592-supp4.xlsx")
    sheet = next(s for s in study["sheets"] if s["sheet"] == f"{cell_context} qPCR data")
    label = {"pansio-1": "Pansio", "olonne-18": "Olonne", "keppel-19": "Keppel"}[candidate_id]
    rows = [r for r in sheet["rows"] if 5 <= r["source_row"] <= 24 and r["values"][0] == label
            and type(r["values"][1]) is int and 1 <= r["values"][1] <= 5]
    if len(rows) != 5:
        raise ValueError("Unexpected qPCR replicate block; re-inspect source sheet before analysis")
    return {"status": "computed", "candidate_name": c["name"], "cell_context": cell_context,
            "endpoint": "nearest-gene expression", "assay": "qPCR", "replicate_count": len(rows),
            "means_log2_fold_change": {gene: mean(r["values"][index] for r in rows) for index,gene in enumerate(("MAGI3","TXNL1","ZNRF4"),2)},
            "source": {"source_id": study["source_id"], "sheet": sheet["sheet"], "rows": [r["source_row"] for r in rows], "sha256": study["sha256"]},
            "limitations": ["Means describe published replicate log2 fold changes; no new significance or causal claim is inferred."]}

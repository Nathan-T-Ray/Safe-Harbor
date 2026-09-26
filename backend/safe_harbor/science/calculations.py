"""Deterministic genomic calculations against the frozen GENCODE v36 pack.

Bioframe performs all overlap and nearest-interval operations. Both its interval
gap and nearest included reference-base distance are returned to expose the
otherwise easy-to-miss one-base convention at exact criterion boundaries.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from typing import Any

import bioframe
import pandas as pd

from .catalog import _load

INTERVAL_COLUMNS = ("chrom", "start", "end")


def candidate_record(candidate_id: str) -> dict:
    record = next((x for x in _load("candidates") if x["candidate_id"] == candidate_id), None)
    if record is None:
        raise ValueError("Unknown candidate ID")
    return record


def _candidate_frame(candidate: dict) -> pd.DataFrame:
    return pd.DataFrame([{"chrom": candidate["chromosome"], "start": candidate["start"], "end": candidate["end"]}])


def _feature_frame(features: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{"chrom": f["chromosome"], "start": f["start"], "end": f["end"],
                          "feature_index": index} for index, f in enumerate(features)],
                        columns=["chrom", "start", "end", "feature_index"])


def closest_features(candidate: dict, features: list[dict], limit: int = 3) -> list[dict]:
    """Nearest same-chromosome features; deterministic genomic/ID tie ordering."""
    selected = sorted((f for f in features if f["chromosome"] == candidate["chromosome"]),
                      key=lambda f: (f["start"], f["end"], f.get("gene_id", ""), f.get("transcript_id", "")))
    if not selected:
        return []
    pairs = bioframe.closest(_candidate_frame(candidate), _feature_frame(selected), k=min(limit, len(selected)))
    results = []
    for pair in pairs.to_dict("records"):
        if pd.isna(pair["feature_index_"]):
            continue
        feature = selected[int(pair["feature_index_"])]
        overlap = feature["start"] < candidate["end"] and candidate["start"] < feature["end"]
        gap = int(pair["distance"])
        results.append({"gene_id": feature.get("gene_id"), "gene_id_version": feature.get("gene_id_version"),
                        "name": feature.get("name"), "gene_type": feature.get("gene_type"),
                        "transcript_id": feature.get("transcript_id"), "chromosome": feature["chromosome"],
                        "start": feature["start"], "end": feature["end"], "strand": feature.get("strand"),
                        "interval_gap_bp": gap, "nearest_reference_base_distance_bp": 0 if overlap else gap+1,
                        "overlap": overlap, "source_row": feature.get("source_row"), "source_table": feature.get("source_table"),
                        **({"tss": feature["tss"]} if "tss" in feature else {})})
    return results


def overlapping_features(candidate: dict, features: list[dict]) -> list[dict]:
    if not features:
        return []
    pairs = bioframe.overlap(_candidate_frame(candidate), _feature_frame(features), how="inner")
    return [features[int(index)] for index in pairs["feature_index_"].tolist()]


@lru_cache(maxsize=3)
def _screen_cached(candidate_id: str) -> dict:
    c = candidate_record(candidate_id)
    annotation = _load("reference_assets")[candidate_id]["annotation"]
    transcripts = annotation["features"]
    coverage = annotation["coverage"]
    all_genes = _load("genes")
    overlaps = overlapping_features(c, transcripts)
    tss = [{**t, "start": t["tss"], "end": t["tss"]+1} for t in transcripts]
    nearest_body = closest_features(c, all_genes, 3)
    nearest_tss = closest_features(c, tss, 3)
    nearest_mirna = closest_features(c, [g for g in all_genes if g["gene_type"] == "miRNA"], 1)
    nearest_lncrna = closest_features(c, [g for g in all_genes if g["gene_type"] == "lncRNA"], 1)
    evidence_id = f"source:gencode-v36:{candidate_id}"
    criterion_results = []
    for criterion in _load("criteria")["criteria"]:
        criterion_id = criterion["criterion_id"]
        result: dict[str, Any] = {"criterion_id": criterion_id, "criterion_version": "safe-harbor-criteria-v1",
                                  "status": "incomplete", "evidence_ids": [], "source": "GENCODE v36"}
        if criterion_id == "outside_gene_body":
            result.update(status="fail" if overlaps else "pass", overlap_count=len(overlaps),
                          distinct_overlapping_gene_count=len({t["gene_id"] for t in overlaps}),
                          overlap_gene_ids=sorted({t["gene_id"] for t in overlaps}),
                          coverage=coverage, evidence_ids=[evidence_id])
        elif criterion_id in ("tss_distance", "mirna_distance", "lncrna_distance"):
            nearest = {"tss_distance": nearest_tss, "mirna_distance": nearest_mirna,
                       "lncrna_distance": nearest_lncrna}[criterion_id]
            result.update(threshold_bp=criterion["threshold_bp"], operator=">",
                          distance_metric="nearest_reference_base_distance_bp", nearest_features=nearest[:1])
            # TSS is neighborhood-scoped: the comparison is certified only if
            # the neighborhood exceeds the criterion radius on both sides.
            radius = criterion["threshold_bp"]
            sufficient = coverage["complete"] and coverage["start"] <= c["start"]-radius and coverage["end"] >= c["end"]+radius
            if nearest and sufficient:
                measured = nearest[0]["nearest_reference_base_distance_bp"]
                result.update(status="pass" if measured > radius else "fail", distance_bp=measured,
                              interval_gap_bp=nearest[0]["interval_gap_bp"], evidence_ids=[evidence_id])
            else:
                result["reason"] = "No mapped feature or insufficient complete coverage for required radius."
        else:
            result.update(source="unavailable", reason=criterion.get("description", "Required evidence unavailable."))
        criterion_results.append(result)
    statuses = {r["status"] for r in criterion_results}
    aggregate = "incomplete" if "incomplete" in statuses else "fail" if "fail" in statuses else "pass"
    return {"screen_status": aggregate, "criterion_results": criterion_results,
            "nearest_gene_bodies": nearest_body, "nearest_transcript_tss": nearest_tss,
            "gene_body_overlap_count": len(overlaps), "annotation_coverage": coverage,
            "reference": "GRCh38", "annotation_release": "GENCODE v36",
            "distance_convention": _load("criteria")["distance_convention"],
            "tool_versions": {"bioframe": bioframe.__version__, "pandas": pd.__version__},
            "parameters": {"coordinate_system": "zero_based_half_open", "tss_plus": "txStart", "tss_minus": "txEnd - 1",
                           "candidate_interval": {k: c[k] for k in ("chromosome", "start", "end")}},
            "limitations": ["Missing required cancer-gene, DHS and ultraconserved-region evidence keeps this screen incomplete.",
                            "Named criteria and GENCODE v36 only; no biological safety conclusion.",
                            "GENCODE v36 analysis is not an exact reproduction of publication filtering."]}


def screen_candidate(candidate_id: str) -> dict:
    return deepcopy(_screen_cached(candidate_id))


def differential_gene_proximity(candidate_id: str, cell_context: str = "H1") -> dict:
    c = candidate_record(candidate_id)
    rows = _load("expression")[cell_context][candidate_id]
    de_ids = {r["gene_id"] for r in rows if abs(r["log2_fold_change"]) >= 1 and r["fdr"] <= .01}
    features = [g for g in _load("genes") if g["gene_id"] in de_ids]
    mapped = {g["gene_id"] for g in features}
    same_chromosome = {g["gene_id"] for g in features if g["chromosome"] == c["chromosome"]}
    nearest = closest_features(c, features, 5)
    source_rows = {r["gene_id"]: r for r in rows}
    for hit in nearest:
        hit["expression_source"] = source_rows[hit["gene_id"]]["source"]
        hit["log2_fold_change"] = source_rows[hit["gene_id"]]["log2_fold_change"]
    unmapped = [{"gene_id": gene_id, "gene_name": source_rows[gene_id]["gene_name"],
                 "source": source_rows[gene_id]["source"], "source_chromosome": source_rows[gene_id]["source_chromosome"]}
                for gene_id in sorted(de_ids-mapped)]
    # Preserve publication table coordinates as a separate analysis, never
    # silently substitute them for the frozen GENCODE v36 mapping.
    table_features = [{"gene_id": r["gene_id"], "gene_id_version": r["gene_id_version"], "name": r["gene_name"],
                       "chromosome": "chr"+r["source_chromosome"], "start": int(r["source_start"])-1,
                       "end": int(r["source_end"]), "source_row": r["source"]["row"]}
                      for r in rows if r["source_chromosome"] in [str(i) for i in range(1,23)]+["X","Y","MT"]
                      and r["source_start"] and r["source_end"]]
    return {"status": "computed", "cell_context": cell_context, "de_gene_count": len(de_ids),
            "gencode_mapped_gene_count": len(mapped), "same_chromosome_gene_count": len(same_chromosome),
            "nearest_de_genes": nearest, "nearest_scope": "Mapped DE identifiers only; unmapped IDs prevent a claim about all DE genes.",
            "unmapped_gene_count": len(unmapped), "unmapped_genes": [{k: x[k] for k in ("gene_id", "gene_name", "source_chromosome")} for x in unmapped],
            "unmapped_source_rows_preview": unmapped[:3],
            "mapping_unit": "stable Ensembl gene ID (version suffix removed for GENCODE join)",
            "annotation_release": "GENCODE v36", "annotation_coverage": "Complete canonical-chromosome gene table",
            "source_table_nearest_de_genes": closest_features(c, table_features, 3),
            "source_table_coordinate_conversion": "Ensembl one-based closed gene spans: start minus one, end unchanged; kept separate from GENCODE v36.",
            "distance_convention": _load("criteria")["distance_convention"],
            "tool_versions": {"bioframe": bioframe.__version__, "pandas": pd.__version__},
            "limitations": ["Unmapped and noncanonical source identifiers remain visible and may limit proximity claims.",
                            "Distance from DE genes cannot establish or exclude cis regulation, causality or biological safety.",
                            "CASP9 is included in the targeting construct; RNA-seq counts do not distinguish construct from endogenous transcription."]}

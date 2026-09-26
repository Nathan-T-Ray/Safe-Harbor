"""Read-only scientific source catalog. No database access or arbitrary paths."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[3] / "data" / "safe_harbor" / "normalized"


@lru_cache(maxsize=8)
def _load(name: str):
    if name not in {"manifest", "candidates", "chromosomes", "reference_assets", "expression", "genes", "workbook_inventory", "criteria"}:
        raise ValueError("Unknown scientific dataset")
    return json.loads((DATA / f"{name}.json").read_text())


def get_catalog() -> dict:
    manifest = _load("manifest")
    return deepcopy({"schema_version": 1, "assembly": "GRCh38",
                     "cell_context": "H1 human embryonic stem cells", "mode": "real_data",
                     "data_version": manifest["data_version"], "candidates": _load("candidates"),
                     "chromosomes": _load("chromosomes"), "reference_assets": _load("reference_assets"),
                     "provenance": manifest, "criteria": _load("criteria"),
                     "limitations": ["Publication-derived shortlist; no new whole-genome search.",
                                     "GRCh38 reference is not a personalized H1 genome.",
                                     "GENCODE v36 is a new versioned annotation analysis.",
                                     "Required cancer-gene and regulatory exclusion evidence is unavailable."]})


def inspect_candidate(candidate_id: str) -> dict:
    found = next((c for c in _load("candidates") if c["candidate_id"] == candidate_id), None)
    if found is None:
        raise ValueError("Unknown candidate ID")
    return deepcopy({"candidate": found, "reference_assets": _load("reference_assets")[candidate_id],
                     "criteria": _load("criteria"), "data_version": found["data_version"],
                     "evidence_ids": found["evidence_ids"],
                     "limitations": ["The candidate region is not the exact insertion nucleotide.",
                                     "Reference sequence orientation is plus; no H1 variants are inferred."]})

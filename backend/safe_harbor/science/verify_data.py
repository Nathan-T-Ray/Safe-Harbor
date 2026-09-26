"""Source/schema/data integrity checks, not unit or component tests."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .catalog import _load, get_catalog


def verify() -> dict:
    root = Path(__file__).resolve().parents[3]
    catalog = get_catalog()
    manifest = catalog["provenance"]
    assert hashlib.sha256((root / "data/safe_harbor/normalized/criteria.json").read_bytes()).hexdigest() == manifest["criteria_sha256"]
    for source in manifest["sources"]:
        data = (root / source["path"]).read_bytes()
        assert len(data) == source["bytes"]
        assert hashlib.sha256(data).hexdigest() == source["sha256"], source["source_id"]
    for c in catalog["candidates"]:
        src = c["source_coordinates"]
        assert c["start"] == src["start"]-1
        assert c["end"]-c["start"] == src["width"]
        seq = catalog["reference_assets"][c["candidate_id"]]["sequence"]
        assert len(seq["sequence"]) == seq["end"]-seq["start"]
        assert set(seq["sequence"].upper()) <= set("ACGTN")
        assert hashlib.sha256(seq["sequence"].encode()).hexdigest() == seq["sha256"]
        annotation = catalog["reference_assets"][c["candidate_id"]]["annotation"]
        assert annotation["coverage"]["complete"]
        for feature in annotation["features"]:
            assert feature["start"] < feature["end"]
            assert feature["tss"] == (feature["start"] if feature["strand"] == "+" else feature["end"]-1)
    expression = _load("expression")
    counts = {}
    for context, contrasts in expression.items():
        counts[context] = {}
        for candidate_id, rows in contrasts.items():
            ids = [r["gene_id_version"] for r in rows]
            assert len(ids) == len(set(ids)), (context, candidate_id, "duplicate IDs")
            assert all(abs(r["log2_fold_change"]) >= 1 and r["fdr"] <= .01 for r in rows)
            assert all(r["source"]["row"] >= 2 and r["source"]["sha256"] for r in rows)
            counts[context][candidate_id] = len(ids)
    genes = _load("genes")
    assert len(genes) == 60660, "Combined v36 canonical gene count differs from official GENCODE release36 statistics; re-inspect before use"
    return {"check_type": "data_integrity", "status": "passed", "sources_verified": len(manifest["sources"]),
            "criteria_sha256": manifest["criteria_sha256"], "canonical_gencode_gene_count": len(genes),
            "candidate_count": len(catalog["candidates"]), "canonical_chromosomes": len(catalog["chromosomes"]),
            "expression_counts": counts,
            "discrepancies": [{"candidate_id": "keppel-19", "context": "H1", "workbook_count": counts["H1"]["keppel-19"],
                               "article_reported_count": 119, "status": "unresolved",
                               "diagnosis": "139 nonempty unique versioned Ensembl gene IDs; all satisfy abs(log2FC)>=1 and FDR<=0.01. No rows removed to match article text."}]}


if __name__ == "__main__":
    result = verify()
    destination = Path(__file__).resolve().parents[3] / "data/safe_harbor/normalized/integrity_report.json"
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))

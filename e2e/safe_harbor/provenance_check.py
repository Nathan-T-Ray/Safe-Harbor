"""SH-D10 read-only provenance data-integrity check (not a unit or component test).

Compares the committed manifest (data/safe_harbor/normalized/manifest.json) with the
local raw cache (data/safe_harbor/raw) and the normalized outputs derived from it.
Nothing under data/ is modified and nothing is downloaded.

For the UCSC sequence-API JSON responses the check separates two questions:
  1. Are the raw response bytes identical to the committed bytes?  (sha256 of file)
  2. Are the reference bases identical?  (sha256 of the extracted "dna" string, which
     is what normalized/reference_assets.json records as sequence.sha256)
When (1) fails it tries to reproduce the committed byte hash by changing only the
"downloadTime"/"downloadTimeStamp" wrapper fields, which demonstrates whether the
mismatch is caused by response metadata rather than sequence.

Usage (from the checkout root):
  .venv/bin/python e2e/safe_harbor/provenance_check.py [--out PATH]
Exit status is 0 when every displayed/computed dataset has a provenance chain and the
bases/annotations match; byte-level wrapper drift is reported, not hidden.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NORMALIZED = ROOT / "data" / "safe_harbor" / "normalized"
RAW = ROOT / "data" / "safe_harbor" / "raw"
OPTIONAL_TRACK_IDS = ("ENCSR597SZL", "ENCFF503GCK")
WRAPPER = re.compile(r'"downloadTime": "[^"]+", "downloadTimeStamp": (\d+)')


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(name: str):
    return json.loads((NORMALIZED / f"{name}.json").read_text())


def reproduce_with_timestamp(text: str, target: str, search_seconds: int) -> dict | None:
    """Search earlier download timestamps; only the wrapper fields are rewritten."""
    match = WRAPPER.search(text)
    if not match:
        return None
    current = int(match.group(1))
    for delta in range(0, search_seconds + 1):
        for stamp in (current - delta, current + delta):
            when = datetime.datetime.fromtimestamp(stamp, datetime.timezone.utc).strftime("%Y:%m:%dT%H:%M:%SZ")
            candidate = WRAPPER.sub(f'"downloadTime": "{when}", "downloadTimeStamp": {stamp}', text, count=1)
            if sha256(candidate.encode()) == target:
                return {"downloadTime": when, "downloadTimeStamp": stamp}
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", help="Optional path for the JSON report")
    parser.add_argument("--search-days", type=int, default=30, help="Timestamp search window for wrapper diagnosis")
    args = parser.parse_args()

    manifest = load("manifest")
    by_id = {s["source_id"]: s for s in manifest["sources"]}
    assets = load("reference_assets")
    problems: list[str] = []
    notes: list[str] = []

    # 1. Raw cache versus committed manifest.
    sources = []
    for source in manifest["sources"]:
        path = ROOT / source["path"]
        row = {"source_id": source["source_id"], "committed_sha256": source["sha256"], "committed_bytes": source["bytes"],
               "license": source.get("license"), "license_url": source.get("license_url"),
               "attribution": source.get("attribution")}
        if not path.exists():
            row["status"] = "raw_file_missing"
            notes.append(f"{source['source_id']}: raw cache absent; normalized outputs still carry the committed hash")
            sources.append(row)
            continue
        data = path.read_bytes()
        row.update(local_sha256=sha256(data), local_bytes=len(data))
        row["status"] = "byte_identical" if row["local_sha256"] == source["sha256"] else "byte_mismatch"
        if not row["license"] and not row["license_url"]:
            notes.append(f"{source['source_id']}: manifest records no license or attribution field")
        if source["source_id"].endswith("-hg38-sequence.json"):
            candidate_id = source["source_id"].removesuffix("-hg38-sequence.json")
            response = json.loads(data)
            frozen = assets[candidate_id]["sequence"]
            bases_hash = sha256(response["dna"].encode())
            row["response_keys"] = sorted(response)
            row["bases_sha256_local"] = bases_hash
            row["bases_sha256_normalized"] = frozen["sha256"]
            row["bases_identical"] = bases_hash == frozen["sha256"] and response["dna"] == frozen["sequence"]
            row["window_identical"] = (response["chrom"], response["start"], response["end"]) == (frozen["chromosome"], frozen["start"], frozen["end"])
            row["normalized_source_hash_equals_manifest"] = frozen["source_hash"] == source["sha256"]
            if not row["bases_identical"] or not row["window_identical"]:
                problems.append(f"{candidate_id}: reference bases or window differ from normalized asset")
            if row["status"] == "byte_mismatch":
                found = reproduce_with_timestamp(data.decode(), source["sha256"], args.search_days * 86400)
                row["committed_bytes_reproduced_by_changing_only"] = ["downloadTime", "downloadTimeStamp"] if found else None
                row["committed_download_time"] = found
                row["status"] = "wrapper_metadata_only" if found else "byte_mismatch_unexplained"
                if not found:
                    problems.append(f"{candidate_id}: raw bytes differ and the difference is not explained by download-time fields")
        elif row["status"] == "byte_mismatch":
            problems.append(f"{source['source_id']}: raw bytes differ from committed manifest")
        sources.append(row)

    # 2. Normalized datasets must cite hashes that exist in the manifest.
    manifest_hashes = {s["sha256"] for s in manifest["sources"]}
    chains = {}
    candidates = load("candidates")
    chains["candidates"] = all(c["source_coordinates"]["sha256"] == by_id["elife-79592-supp1.xlsx"]["sha256"] for c in candidates)
    expression = load("expression")
    expression_hashes = {r["source"]["sha256"] for context in expression.values() for rows in context.values() for r in rows}
    chains["expression_rows"] = expression_hashes <= manifest_hashes and {
        by_id["elife-79592-supp5.xlsx"]["sha256"], by_id["elife-79592-supp6.xlsx"]["sha256"]} == expression_hashes
    chains["annotation_neighborhoods"] = all(
        all(by_id[k]["sha256"] == v for k, v in a["annotation"]["source_hashes"].items()) and a["annotation"]["release"] == "GENCODE v36"
        for a in assets.values())
    chains["reference_sequence_windows"] = all(a["sequence"]["source_hash"] == by_id[f"{k}-hg38-sequence.json"]["sha256"] for k, a in assets.items())
    inventory = load("workbook_inventory")
    chains["workbook_inventory"] = all(w["sha256"] == by_id[w["source_id"]]["sha256"] for w in inventory)
    chromosomes = load("chromosomes")
    chains["chromosome_lengths"] = len(chromosomes) == 25 and "chromInfo.txt.gz" in by_id
    genes = load("genes")
    chains["genes_have_source_rows"] = all("source_row" in g for g in genes)
    for key, ok in chains.items():
        if not ok:
            problems.append(f"provenance chain broken: {key}")

    # 3. Optional large tracks: must not be present or referenced as available.
    criteria = load("criteria")
    raw_names = sorted(p.name for p in RAW.iterdir()) if RAW.exists() else []
    optional = {
        "raw_files_matching_optional_ids": [n for n in raw_names if any(t in n for t in OPTIONAL_TRACK_IDS)],
        "manifest_unavailable": manifest.get("unavailable", []),
        "criteria_unavailable": [c["criterion_id"] for c in criteria["criteria"] if c.get("availability") == "unavailable"],
        "status": "not_included",
    }
    if optional["raw_files_matching_optional_ids"]:
        problems.append("optional track files present in raw cache without manifest entries")

    # 4. Core execution footprint: normalized files read by the catalog/tools only.
    catalog_src = (ROOT / "backend/safe_harbor/science/catalog.py").read_text()
    reads_raw = '"raw"' in catalog_src or "RAW" in catalog_src
    normalized_sizes = {p.name: p.stat().st_size for p in sorted(NORMALIZED.glob("*.json"))}
    normalized_hashes = {p.name: sha256(p.read_bytes()) for p in sorted(NORMALIZED.glob("*.json"))}
    core = {"catalog_reads_raw_cache": reads_raw, "normalized_total_bytes": sum(normalized_sizes.values()),
            "normalized_file_bytes": normalized_sizes, "normalized_file_sha256": normalized_hashes,
            "raw_cache_total_bytes": sum(s.get("local_bytes", 0) for s in sources)}
    if reads_raw:
        problems.append("catalog appears to read the raw cache at runtime")

    report = {"check_type": "data_integrity/provenance", "ticket": "SH-D10",
              "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
              "data_version": manifest["data_version"], "assembly": manifest["assembly"],
              "status": "passed" if not problems else "failed", "problems": problems, "notes": notes,
              "sources": sources, "provenance_chains": chains, "optional_tracks": optional, "core_footprint": core}
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text)
    print(text)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())

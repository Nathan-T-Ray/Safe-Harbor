# Safe Harbor provenance, attribution and optional tracks (SH-D10)

Review date: 2026-09-26. Data version: `autio-79592-v2-gencode36-2026-09-26`. Assembly: GRCh38 (UCSC `hg38`). Cell context: H1 human embryonic stem cells, with H9 kept as a separate context.

This document covers every dataset the application displays or computes from. It also records what is *not* known. The committed manifest is `data/safe_harbor/normalized/manifest.json`, owned by codex-data. This ticket did not modify it; the proposed changes are at the end of this document. To check the statements here, run:

```sh
.venv/bin/python e2e/safe_harbor/provenance_check.py --out artifacts/safe_harbor/provenance/<timestamp>/report.json
```

This is a read-only data-integrity check, not a unit test. It compares the committed manifest with the local raw cache and with every normalized file that cites a source hash. It also checks the optional-track status and the core runtime footprint. Committed evidence: `artifacts/safe_harbor/provenance/20260926T185551Z/report.json` (status `passed`, 0 problems, 3 notes).

## 1. Raw sources

In the tables below, "sha256" is the committed manifest value. "Local" is the SHA-256 of the file currently in `data/safe_harbor/raw/` (a gitignored cache, not committed).

### 1a. Publication supplements: Autio et al., eLife 2024;13:e79592

Citation: Autio MI *et al.* "Computationally defined and in vitro validated putative genomic safe harbour loci for transgene expression in human cells." *eLife* 2024;13:e79592. doi:10.7554/eLife.79592. Article: <https://elifesciences.org/articles/79592>. Methods: <https://pmc.ncbi.nlm.nih.gov/articles/PMC10836832/>.

**License.** The PMC copy states "distributed under the terms of the Creative Commons Attribution License, which permits unrestricted use and redistribution provided that the original author and source are credited" (© 2024 Autio et al.). The manifest records **CC BY 4.0**. The eLife page did not load during this review, and the PMC statement retrieved did not name a version. The *version number* "4.0" is therefore carried over from the manifest, not re-confirmed. The obligation is attribution: cite the article wherever values from the supplements are shown or exported.

| File (source_id) | URL | Bytes | sha256 (committed = local) | Used for |
|---|---|---|---|---|
| `elife-79592-supp1.xlsx` | https://cdn.elifesciences.org/articles/79592/elife-79592-supp1-v2.xlsx | 480,763 | `faa4ed0a0dfd246368ada4013c0fcf61166b9d8c9c14e42eef055f0bede596dc` | Candidate intervals (sheet `overlap safe-active`), widths, group key, publication BLAT ratio |
| `elife-79592-supp3.xlsx` | …/elife-79592-supp3-v2.xlsx | 30,243 | `69255bad50a51039ad97e5111fcd4c9a80e6a3f87e78f24160e71b0e14419db1` | Inventoried only (`workbook_inventory.json`). **No current tool or UI view reads it.** |
| `elife-79592-supp4.xlsx` | …/elife-79592-supp4-v2.xlsx | 16,676 | `641891f65518c735b553e1d28e36dd4fdd15a139b7d8177df01775274e6c538e` | qPCR replicate values for MAGI3/TXNL1/ZNRF4 (`qpcr_summary`, H1 and H9 sheets) |
| `elife-79592-supp5.xlsx` | …/elife-79592-supp5-v2.xlsx | 84,692 | `9811bae46bc42699b42751ef9c54c0a1b75b403154bb31026645fb719e335667` | H1 significant-only DESeq2 tables; candidate sheet-title coordinates (cross-check) |
| `elife-79592-supp6.xlsx` | …/elife-79592-supp6-v2.xlsx | 42,421 | `821d20d8b48f14ed1aa3686570d985d4a250614a2caa50b047e43384f4a168d1` | H9 significant-only DESeq2 tables (separate context) |

All five are `source_version` v2. Supplement 2 is not ingested; its contents were not reviewed here.

### 1b. UCSC hg38 database tables (GENCODE v36 and chromosome sizes)

Directory: <https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/>.

**Terms.** The directory's `README.txt` (retrieved 2026-09-26) states "All the files and tables in this directory are freely usable for any purpose." GENCODE's data access page (<https://www.gencodegenes.org/pages/data_access.html>) says "All the GENCODE project data is open access". It names no formal license and no citation requirement. **The formal license name for UCSC/GENCODE tables is therefore unverified.** "Freely usable" and "open access" are the documented terms. Attribution to the UCSC Genome Browser and GENCODE is still expected scholarly practice and is kept in the manifest.

| File | Bytes | sha256 (committed = local) | Used for |
|---|---|---|---|
| `wgEncodeGencodeCompV36.txt.gz` | 9,723,332 | `843c434ede93314d09d78cfe498784942122bfa3e0c8d7a8bd096f1fd880be9a` | Transcript spans, exons, strand-aware TSS; source rows in `genes.json` / `reference_assets.json` |
| `wgEncodeGencodeAttrsV36.txt.gz` | 5,504,036 | `2098b0e7cd1ae412b1edfe93d267405175eadb63f63b9e8315b6bddda0a7c6be` | Gene ID/version, gene name, `gene_type` (miRNA / lncRNA criteria) |
| `wgEncodeGencodeCompV36.sql` | 2,030 | `7164106eb072b95e7a9499a4b153f9c7b0bb0e0b1bbbe00a79723707d5bf3256` | Schema; field count (16) validated during parsing |
| `wgEncodeGencodeAttrsV36.sql` | 2,119 | `5c238ca6074985eabebe572b0f182382c965221439108c727c9668c3ca3dac22` | Schema; field count (14) validated during parsing |
| `chromInfo.txt.gz` | 6,159 | `6788b62a18f994c9357b1afb132a832a7377106e4f542f9e84b4f6d63b131d97` | Chromosome lengths (chr1–22, X, Y, M) |

The manifest's `license_url` for `chromInfo.txt.gz` points to the GENCODE page, which is wrong because chromInfo is a UCSC assembly table. See the proposed diff.

### 1c. UCSC sequence API windows

Service: <https://genome.ucsc.edu/goldenPath/help/api.html>. **Terms: unverified.** The hgdownload README quoted above covers the download directory, not the REST API. The manifest records no license or attribution for these three sources; the check reports this as a note.

| File | Request (zero-based, half-open) | Bytes | Committed file sha256 | Local file sha256 | Bases sha256 (matches `reference_assets.json`) |
|---|---|---|---|---|---|
| `pansio-1-hg38-sequence.json` | chr1:113339860–113340614 (754 bp) | 914 | `c8808f77…0ff0f2e` | `d4c3a561…a0bf0a65b4` | `3aa07aefbc467788e84ae19b85cc49021328cc2ad5255acfb32f5350fd322cd2` |
| `olonne-18-hg38-sequence.json` | chr18:56534674–56536539 (1,865 bp) | 2,024 | `a2a2a1c7…b94c83c` | `29e4aef4…0982e` | `c817d920af90283abf276de7d3fbfc52eaa893f267004bd5d266c9916638f2d9` |
| `keppel-19-hg38-sequence.json` | chr19:5400660–5402239 (1,579 bp) | 1,736 | `89070a66…a149e1` | `9f4b6b31…ecf5a` | `43c18394936646627639f881df36ca85fff84d1d69205ba98e0a008e26d1ec79` |

Each window is the candidate interval plus 100 bp on each side, on the plus-strand reference. It is not a personalized H1 genome.

#### Why the committed and fresh sha256 differ (investigated)

A UCSC `getData/sequence` response wraps the bases in metadata:

```json
{ "downloadTime": "2026:09:26T18:48:07Z", "downloadTimeStamp": 1790448487, "genome": "hg38", "chrom": "chr1", "start": 113339860, "end": 113340614, "dna": "…" }
```

`download()` in `ingest.py` hashes the **whole response body**, so `downloadTime` and `downloadTimeStamp` go into the manifest's `sha256`. The local cache was re-fetched at 18:48:07–10Z. `provenance_check.py` found the following for all three files:

- The byte lengths match the manifest exactly (914 / 2,024 / 1,736).
- `chrom`, `start` and `end` match the frozen window. The `dna` string is identical to `reference_assets.json`, and its SHA-256 equals the committed `sequence.sha256`.
- Rewriting **only** the two download-time fields reproduces the committed file hash exactly. The committed downloads were at `2026:09:26T18:26:11Z` (pansio-1), `18:26:13Z` (olonne-18) and `18:26:14Z` (keppel-19).

**Conclusion:** the mismatch comes entirely from response wrapper metadata. The reference bases are unchanged. One consequence: `python -m backend.safe_harbor.science.verify_data` currently fails its raw-byte assertion (`pansio-1-hg38-sequence.json`) whenever the cache has been re-fetched, even though no sequence changed.

**Recommendation (for codex-data, owner of `science/` and `data/safe_harbor/`):**

1. Treat the extracted bases as the identity of the reference window. Record `content_sha256` (SHA-256 of `dna`, already stored as `reference_assets[*].sequence.sha256`) in the manifest source entry, and have `verify_data` compare that value for API responses.
2. Keep the raw-body hash, but label it (`sha256_scope: "raw_response_body_including_downloadTime"`) and record `downloaded_at` taken from `downloadTime`. A raw-body mismatch then counts as expected drift, not an integrity failure.
3. Alternatively, write a canonical file on download (for example, strip `downloadTime`/`downloadTimeStamp` and serialize with sorted keys), so that a re-fetch is byte-stable.

## 2. Normalized datasets (committed, read at runtime)

The runtime (`catalog.py`, `calculations.py`, `tools.py`, `expression_tools.py`) reads only `data/safe_harbor/normalized/*.json`. It never reads `data/safe_harbor/raw/`; `provenance_check.py` confirms this for `catalog.py`, which all other modules load through.

| Normalized file | Bytes | sha256 | Derived from | Provenance carried in records |
|---|---|---|---|---|
| `candidates.json` | 3,415 | `42736026…d57444` | supp1 `overlap safe-active` + supp5 sheet titles | `source_coordinates` {source_id, sheet, one-based row, sha256, conversion rule} |
| `chromosomes.json` | 1,479 | `2e149cb2…b3946e` | `chromInfo.txt.gz` | none per row; manifest source only |
| `criteria.json` | 6,278 | `33a2f4e9…b6b7fd`* | PMC methods section "In silico search for putative GSH" (`source_url`, `source_section`) | Authored encoding of published thresholds; immutable to harness |
| `expression.json` | 596,762 | `da65fb47…230533` | supp5 (H1), supp6 (H9) | every row: {source_id, sheet, row, sha256} |
| `genes.json` | 11,623,183 | `bb106ae5…4ac6895` | GENCODE v36 Comp + Attrs | `source_row` (Comp table line); aggregated per gene_id+chromosome |
| `reference_assets.json` | 811,999 | `d7c815ee…f14e0` | GENCODE v36 (±1 Mb transcripts) + UCSC sequence windows | annotation `source_hashes`, `coverage`, `release`; sequence `sha256` (bases), `source_hash` (raw body), `source_url` |
| `workbook_inventory.json` | 3,190,545 | `f01ff2c6…2d82d7d` | supp1, 3, 4, 5, 6 (all sheets, merged ranges) | per workbook `sha256`; one-based `source_row` |
| `manifest.json` | 6,662 | `5d3e98f3…b4ec4e` | ingestion | — |
| `integrity_report.json` | 734 | `e07dc4ed…020747` | `verify_data` | — |

\* Full hashes are in the committed provenance report (`core_footprint.normalized_file_sha256`). `criteria.json` full sha256: `33a2f4e97e7a1b2f90f45c77dfbc26598ce4c1a6df2871a119c0a3b489b6b7fd`.

The check found an intact provenance chain for each dataset. Every hash cited in a normalized record equals a committed manifest hash (`provenance_chains`: all `true`).

## 3. Feature-by-feature provenance

| Displayed / computed feature | Where | Source → normalized | Assembly / coordinates | Limitations |
|---|---|---|---|---|
| Candidate list, names, intervals, coordinate footer | Candidate rail, genome views, `inspect_candidate` | supp1 row + supp5 sheet title → `candidates.json` | GRCh38; source one-based closed → internal zero-based half-open (start−1); no lift-over | Publication shortlist, not a new discovery; region, not insertion nucleotide |
| Chromosome bars and lengths | Genome and chromosome zoom | `chromInfo.txt.gz` → `chromosomes.json` | hg38 canonical 25 | chrM is excluded from the genome drawing |
| Candidate markers | Genome / chromosome SVG | `candidates.json` start ÷ chromosome length | GRCh38 | Marker position is proportional; not base-resolution |
| Locus gene spans, names, strand arrows | Locus zoom | GENCODE v36 Comp+Attrs → `reference_assets[*].annotation.features` | GRCh38 zero-based half-open; window ±100 kb displayed, ±1 Mb stored | Spans are merged per gene, not exon models; at most 12 nearest shown; GENCODE v36 is a new analysis, not the paper's Ensembl 103 / GENCODE v35 pipeline |
| Reference bases, highlight, SHA-256 line | Sequence zoom, `reference_sequence` tool | UCSC sequence API → `reference_assets[*].sequence` | GRCh38 plus strand; window candidate ±100 bp | Cropped window; must keep recorded offsets; not a personalized H1 genome |
| Genomic criteria (gene body, TSS 50 kb, miRNA 300 kb, lncRNA 100 kb) | `screen_candidate`, assessment criteria list | `genes.json`, `reference_assets` coverage, `criteria.json` | GRCh38 | New GENCODE v36 calculation; the publication's claims are not substituted |
| Cancer-gene, DHS buffer and ultraconserved criteria | Assessment criteria (status `incomplete`) | none: `availability: unavailable` | — | Missing required evidence → screen `incomplete`, never a pass or negative result |
| DE gene counts, control overlap, direction concordance | `expression_comparison`, `control_overlap`, evidence inspector | supp5/supp6 → `expression.json` | Ensembl versioned IDs; supplement-reported gene coordinates | Significant-only tables (abs(log2FC) ≥ 1, FDR ≤ 0.01); no raw counts; H1 Keppel 139 vs article 119 unresolved |
| Nearest DE genes (gene proximity) | `gene_proximity` | `expression.json` IDs mapped to `genes.json` | GRCh38 GENCODE v36 | Unmapped IDs reported; distance does not establish cis regulation |
| qPCR replicate values | `expression_comparison.qpcr` | supp4 → `workbook_inventory.json` (rows cited) | n/a | Significance is not a safety claim |
| H9 expression | `cell_context: "H9"` arguments | supp6 → `expression.json.H9` | — | Different biological context; never generalized to H1 |
| Data version, GRCh38, H1 context bar | Context bar | `manifest.json` / catalog constants | — | — |
| Assessments, statuses, task graph, replay | Conclusion panel, graph, timeline | Runtime ledger (MongoDB) events built from the tool outputs above | — | Deterministic operational mode does not measure model reasoning |

## 4. Optional tracks

| Track | Accession | Status | What is verified |
|---|---|---|---|
| H1 candidate cis-regulatory elements | ENCODE `ENCSR597SZL` | **Not included** | Nothing verified here. The ENCODE portal timed out (60 s) on 2026-09-26 for both JSON metadata requests. Child file accession, assembly, format, size, md5 and coverage are **unknown**. |
| DNase hypersensitivity clusters (DHS exclusion ±2 kb) | ENCODE `ENCFF503GCK` | **Not included** | Same as above: assembly (GRCh38 vs hg19), file size and md5 are unknown. `criteria.json` `outside_dhs_buffer` is `availability: unavailable`. |
| Ultraconserved regions | — | Not included | Source and the original hg19→hg38 lift-over are not reproduced. |
| COSMIC Cancer Gene Census v92 | — | Not included | Source and licensing unresolved; terms not assessed in this review. |

`provenance_check.py` confirms that no file matching either ENCODE accession exists in the raw cache. The manifest lists all four as `unavailable`, and each dependent criterion is marked `unavailable` so it resolves to `incomplete`. Before any of these tracks is included, the ingestion owner must record the child file accession, URL, assembly, byte length, sha256 (and the portal md5), coverage over each candidate ±buffer, and license. A track in a different assembly must never be silently lifted over.

## 5. Core execution without large downloads

- The runtime reads only the committed normalized pack: 9 files, 16,241,057 bytes, the largest being `genes.json` at 11.6 MB. No network access is needed at runtime.
- The raw cache (13 files, 15,897,145 bytes) is needed only to **re-run ingestion**; it is gitignored.
- No optional track is downloaded, referenced or required. Evidence: `optional_tracks.status = not_included` and `core_footprint.catalog_reads_raw_cache = false` in the provenance report. The SH-U14 browser journey (a full deterministic run through API and MongoDB) ran against this pack with no optional track present.

## 6. Proposed manifest changes (for codex-data; not applied)

```diff
@@ top level
   "data_version": "autio-79592-v2-gencode36-2026-09-26",
   "mode": "real_data",
   "assembly": "GRCh38",
+  "criteria_sha256": "33a2f4e97e7a1b2f90f45c77dfbc26598ce4c1a6df2871a119c0a3b489b6b7fd",
@@ UCSC database sources (CompV36/AttrsV36 .sql/.txt.gz)
       "attribution": "UCSC Genome Browser; GENCODE v36 (where applicable)",
-      "license_url": "https://www.gencodegenes.org/pages/data_access.html"
+      "license_url": "https://www.gencodegenes.org/pages/data_access.html",
+      "terms": "UCSC hg38 database README: 'freely usable for any purpose'; GENCODE: 'open access'. No formal license name documented.",
+      "terms_url": "https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/README.txt"
@@ chromInfo.txt.gz
-      "attribution": "UCSC Genome Browser; GENCODE v36 (where applicable)",
-      "license_url": "https://www.gencodegenes.org/pages/data_access.html"
+      "attribution": "UCSC Genome Browser hg38 chromInfo",
+      "terms": "UCSC hg38 database README: 'freely usable for any purpose'",
+      "terms_url": "https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/README.txt"
@@ pansio-1-hg38-sequence.json (same pattern for olonne-18 and keppel-19)
       "sha256": "c8808f778839f10ffec55b22a2700a93bf5a2e9e2d921b70a2a17e04e7ff0f2e",
-      "bytes": 914
+      "bytes": 914,
+      "sha256_scope": "raw_response_body_including_downloadTime",
+      "downloaded_at": "2026-09-26T18:26:11Z",
+      "content_sha256": "3aa07aefbc467788e84ae19b85cc49021328cc2ad5255acfb32f5350fd322cd2",
+      "content_sha256_scope": "dna field (reference bases, plus strand)",
+      "attribution": "UCSC Genome Browser REST API, hg38",
+      "license": "unverified"
@@ olonne-18: downloaded_at "2026-09-26T18:26:13Z", content_sha256 "c817d920af90283abf276de7d3fbfc52eaa893f267004bd5d266c9916638f2d9"
@@ keppel-19: downloaded_at "2026-09-26T18:26:14Z", content_sha256 "43c18394936646627639f881df36ca85fff84d1d69205ba98e0a008e26d1ec79"
@@ unavailable
-  "unavailable": ["COSMIC cancer-gene data/licensing", "DHS exclusion track", "ultraconserved interval track", "H1 cCRE child asset"]
+  "unavailable": [...unchanged...],
+  "optional_tracks": [
+    {"accession": "ENCSR597SZL", "kind": "H1 cCRE", "status": "not_included", "child_file": null, "assembly": null, "coverage": null, "license": null},
+    {"accession": "ENCFF503GCK", "kind": "DHS clusters", "status": "not_included", "assembly": null, "bytes": null, "sha256": null, "license": null}
+  ]
```

The `criteria_sha256` line is already written by the current `ingest.py:main()`, but the committed manifest does not contain it. This means the committed manifest was produced by an earlier version of `ingest.py`. Regenerating with the current code will also change `sources[*].sha256` for the three sequence files unless recommendation 1–3 in §1c is applied first.

## 7. Remaining limitations and unverified claims

- The CC BY *version* (4.0) is carried over from the manifest and was not re-confirmed from the eLife page, which did not load.
- UCSC REST API terms, a formal UCSC/GENCODE license name, and COSMIC terms are unverified.
- ENCODE metadata for `ENCSR597SZL` / `ENCFF503GCK` could not be retrieved, so assembly, size and coverage are unknown.
- `chromosomes.json` and `genes.json` carry no per-record source hash; the link to the source is file-level through the manifest.
- Supplement 3 (clone screening and ddPCR) is inventoried but not surfaced by any tool or view. Supplement 2 is not ingested.
- The Keppel-19 H1 DE count (workbook 139 vs article text 119) remains unresolved.

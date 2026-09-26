# Safe Harbor source provenance and attribution

Current integrated version: **autio-79592-v2-gencode36-comp-pseudo-2026-09-26**. Human GRCh38 reference, H1 human embryonic stem-cell experimental context. H9 tables remain a different context. This publication-derived shortlist is not a new whole-genome discovery.

The read-only integrity check against the integrator's original raw cache passed for **15 source files**, with no hash/chain problems and three explicit missing sequence-license metadata notes. Evidence: `artifacts/safe_harbor/pr64-review/provenance-current.json`. The prior author's fresh-download review is retained in Git history and `artifacts/safe_harbor/provenance/20260926T185551Z/report.json`; its old 13-file inventory predates the PseudoGene integration.

## Sources and frozen bytes

| Original source | Bytes | SHA-256 |
|---|---:|---|
| [elife-79592-supp1.xlsx](https://cdn.elifesciences.org/articles/79592/elife-79592-supp1-v2.xlsx) | 480,763 | `faa4ed0a0dfd246368ada4013c0fcf61166b9d8c9c14e42eef055f0bede596dc` |
| [elife-79592-supp3.xlsx](https://cdn.elifesciences.org/articles/79592/elife-79592-supp3-v2.xlsx) | 30,243 | `69255bad50a51039ad97e5111fcd4c9a80e6a3f87e78f24160e71b0e14419db1` |
| [elife-79592-supp4.xlsx](https://cdn.elifesciences.org/articles/79592/elife-79592-supp4-v2.xlsx) | 16,676 | `641891f65518c735b553e1d28e36dd4fdd15a139b7d8177df01775274e6c538e` |
| [elife-79592-supp5.xlsx](https://cdn.elifesciences.org/articles/79592/elife-79592-supp5-v2.xlsx) | 84,692 | `9811bae46bc42699b42751ef9c54c0a1b75b403154bb31026645fb719e335667` |
| [elife-79592-supp6.xlsx](https://cdn.elifesciences.org/articles/79592/elife-79592-supp6-v2.xlsx) | 42,421 | `821d20d8b48f14ed1aa3686570d985d4a250614a2caa50b047e43384f4a168d1` |
| [wgEncodeGencodeCompV36.sql](https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/wgEncodeGencodeCompV36.sql) | 2,030 | `7164106eb072b95e7a9499a4b153f9c7b0bb0e0b1bbbe00a79723707d5bf3256` |
| [wgEncodeGencodeAttrsV36.sql](https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/wgEncodeGencodeAttrsV36.sql) | 2,119 | `5c238ca6074985eabebe572b0f182382c965221439108c727c9668c3ca3dac22` |
| [wgEncodeGencodePseudoGeneV36.sql](https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/wgEncodeGencodePseudoGeneV36.sql) | 2,048 | `f9989b977626f808454082b78d852dc5a6f91055d1aca9d2998f0998b7c63704` |
| [wgEncodeGencodeCompV36.txt.gz](https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/wgEncodeGencodeCompV36.txt.gz) | 9,723,332 | `843c434ede93314d09d78cfe498784942122bfa3e0c8d7a8bd096f1fd880be9a` |
| [wgEncodeGencodeAttrsV36.txt.gz](https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/wgEncodeGencodeAttrsV36.txt.gz) | 5,504,036 | `2098b0e7cd1ae412b1edfe93d267405175eadb63f63b9e8315b6bddda0a7c6be` |
| [wgEncodeGencodePseudoGeneV36.txt.gz](https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/wgEncodeGencodePseudoGeneV36.txt.gz) | 781,311 | `67a06659d5836a49abfd64498a45e25de55c82fbbf5223ae410412f71ba92739` |
| [chromInfo.txt.gz](https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/chromInfo.txt.gz) | 6,159 | `6788b62a18f994c9357b1afb132a832a7377106e4f542f9e84b4f6d63b131d97` |
| [pansio-1-hg38-sequence.json](https://api.genome.ucsc.edu/getData/sequence?genome=hg38;chrom=chr1;start=113339860;end=113340614) | 914 | `c8808f778839f10ffec55b22a2700a93bf5a2e9e2d921b70a2a17e04e7ff0f2e` |
| [olonne-18-hg38-sequence.json](https://api.genome.ucsc.edu/getData/sequence?genome=hg38;chrom=chr18;start=56534674;end=56536539) | 2,024 | `a2a2a1c7224c190ac38a8fef4e77d744dc098b7b05d23f1df1d99d368c94b83c` |
| [keppel-19-hg38-sequence.json](https://api.genome.ucsc.edu/getData/sequence?genome=hg38;chrom=chr19;start=5400660;end=5402239) | 1,736 | `89070a660f36dbf70dadf7996d08c55c3e65aaaf031804b75451af0967a149e1` |

The five publication supplements are v2 from Autio et al., *Computationally defined and in vitro validated putative genomic safe harbour loci for transgene expression in human cells*, eLife2024;13:e79592, DOI10.7554/eLife.79592. Cite [the study](https://elifesciences.org/articles/79592) and preserve file/sheet/row references when displaying or exporting derived values.

The annotation analysis uses **GENCODE v36 Comp + PseudoGene + Attrs and their SQL schemas**, with UCSC hg38 chromosome lengths. It is a new versioned analysis, not an exact reproduction of the study's original annotation pipeline. SQL field counts and input byte hashes are checked during ingestion. Frozen criteria SHA-256 is `33a2f4e97e7a1b2f90f45c77dfbc26598ce4c1a6df2871a119c0a3b489b6b7fd` and is already present in the manifest.

## What each source supplies

| Feature | Evidence and limitation |
|---|---|
| Published candidates | Supplement1 original rows plus supplement5 title-coordinate cross-checks; preserve source one-based closed notation and explicit internal zero-based half-open conversion |
| Screening outcomes | Supplement3 sheets/columns inventoried; current scientific tools do not surface its outcome rows as endpoint support |
| qPCR | Supplement4 replicate values, assay/gene/cell-context metadata; no general safety inference |
| Expression/control calculations | Supplements5(H1) and6(H9), significant-only DESeq2 tables; abs(log2FC)≥1 and FDR≤0.01; no all-measured-gene denominator |
| Gene spans, strand-aware TSS and proximity | GENCODEv36 canonical gene records with source rows, covered annotation neighborhoods and explicit unmapped-ID reporting |
| Genome overview | Actual UCSC chromosome lengths and published candidate intervals |
| Reference bases | Three frozen UCSC sequence windows, candidate±100bp, plus-strand reference orientation and original genomic offsets |
| Assessments/replay | MongoDB authoritative application events, immutable artifacts and versioned assessments, not browser-derived verdicts |

The H1 Keppel table contains139 gene rows versus119 in the article's prose; the discrepancy is retained. No calculated result is overwritten to match the paper. Missing experimental results are not treated as negative biological evidence.

## Byte identity versus reference-base identity

UCSC sequence JSON includes download-time metadata. The integrator's original JSON bytes match all three manifest hashes. A later fresh API response can have different wrapper bytes while containing identical bases. Preserve that new response as a distinct raw artifact/version; do not exempt it from frozen raw-byte verification or rewrite historical source hashes. Independently compare chromosome/start/end and the base-string SHA-256 already stored in `reference_assets.json`. A missing raw cache means raw-byte verification is unavailable; normalized provenance-chain checks alone do not prove that missing bytes match.

## Attribution and unresolved terms

Publication manifest entries declare **CC BY4.0**, attributed to Autio et al. The earlier independent review confirmed a CC-BY statement in PMC but did not independently reconfirm the version number; this distinction remains explicit. UCSC/GENCODE entries record attribution and a GENCODE data-access URL; the original review found open-access/free-use statements but no named formal license. The chromInfo license URL points to GENCODE even though it is a UCSC assembly table; correct this metadata in a future source-manifest version, not by altering the frozen comparison pack.

The three sequence-source manifest entries currently omit license/attribution fields. Source URLs and base hashes remain available; **REST API terms are unverified**. No copied third-party implementation is licensed merely by being publicly accessible.

## Optional tracks and runtime footprint

H1 cCRE experimentENCSR597SZL child asset, DHS fileENCFF503GCK assembly/coverage, ultraconserved intervals, and cancer-gene data/licensing are unavailable. No optional regulatory track is used or displayed as measured evidence. Required unavailable criteria remain incomplete. Optional future ingestion must identify exact file, assembly, byte hash, coverage and terms; no silent lift-over.

The current nine normalized files total **23,679,030 bytes**, including Comp/PseudoGene annotations; the original15-file raw cache totals **16,680,504 bytes**. Core tools read the committed normalized pack and do not depend on optional large downloads. Raw sources are an ignored ingestion cache; immutable run exports contain the selected demonstration windows and evidence provenance.

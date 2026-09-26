# Safe Harbor source pack and scientific boundary

Source: Autio et al., *Computationally defined and in vitro validated putative genomic safe harbour loci for transgene expression in human cells*, eLife 2024;13:e79592. [Primary article](https://elifesciences.org/articles/79592), [PMC copy and methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC10836832/). Article and supplements are attributed to the authors under CC BY 4.0. No third-party analysis code was copied.

This catalog is a **publication-derived shortlist**, beginning with Pansio-1, Olônne-18 and Keppel-19. It is not a new whole-genome discovery result. The experimental context is H1 human embryonic stem cells. H9 is retained separately. Sequence is the UCSC hg38 / GRCh38 reference, not a personalized H1 genome.

## Reproduce and inspect

From the checkout root, with dependencies installed:

```sh
.venv/bin/python -m backend.safe_harbor.science.ingest
.venv/bin/python -m backend.safe_harbor.science.verify_data
```

The ingestion command preserves cached raw files and regenerates normalized outputs. Delete a specific cached input only when intentionally fetching a different source version. `manifest.json` records source URLs, original byte lengths, SHA-256 hashes, attribution and limitations. Workbook normalization uses original file, sheet and one-based Excel row numbers; `workbook_inventory.json` retains all sheet cells and merged-range metadata. Reading these workbooks is not a replication of RNA-seq processing from raw FASTQ.

`backend.safe_harbor.science.get_catalog()` supplies schema-version-1 candidates, actual chromosome lengths, frozen sequence windows and annotation neighborhoods. `inspect_candidate(id)` accepts only the three known IDs. No database writes occur in this lane.

## Files inspected

| Source | Actual sheets | Interpretation |
| --- | --- | --- |
| Supplement 1 v2 | safe sites; active regions; overlap safe-active | Publication filtering outputs; coordinates and inclusive widths |
| Supplement 3 v2 | summary of clone screening; ddPCR data | Screening counts, original droplet measurements and copy-number calculations |
| Supplement 4 v2 | H1 qPCR data; H9 qPCR data | Replicate log2 fold changes, means and source summaries for MAGI3, TXNL1 and ZNRF4 |
| Supplement 5 v2 | Key; 3 coordinate-named candidate sheets; WT H1; 4 enrichment sheets | Significant-only H1 DEseq2 tables and reported functional-enrichment outputs |
| Supplement 6 v2 | Key; 3 coordinate-named candidate sheets; WT H9; 4 enrichment sheets | Corresponding H9 data, kept in a separate biological context |

The numerical DE threshold is absolute log2 fold change ≥ 1 and FDR ≤ 0.01. The contrast compares a targeted clone or an independent untargeted culture with the corresponding reference untargeted culture. Missing table rows are not proof of zero expression or absent biological effects. The supplied tables do not contain all measured genes or raw sequencing counts. Worker inputs exclude the paper's interpretive conclusion paragraphs.

## Verified coordinates

| Candidate | Source GRCh38 interval, one-based closed | Internal interval, zero-based half-open | Width |
| --- | --- | --- | --- |
| Pansio-1 | chr1:113339961–113340514 | chr1:[113339960,113340514) | 554 bp |
| Olônne-18 | chr18:56534775–56536439 | chr18:[56534774,56536439) | 1,665 bp |
| Keppel-19 | chr19:5400761–5402139 | chr19:[5400760,5402139) | 1,379 bp |

Each interval is independently cross-matched between Supplement 1's overlap table and the Supplement 5 sheet title. Supplement 1's explicit width equals end − start + 1. The source method explicitly uses GRCh38. Conversion subtracts one from start only; no lift-over is performed. These are candidate regions, not assertions about an exact insertion nucleotide. Nearby regions share a group key built from the source active-region interval.

## References and annotation coverage

`wgEncodeGencodeCompV36.txt.gz`, `wgEncodeGencodeAttrsV36.txt.gz` and their corresponding SQL schemas were downloaded and inspected from the [UCSC hg38 database directory](https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/). SQL field counts are validated during parsing. The full canonical-chromosome annotation is parsed; each displayed neighborhood contains all transcript records overlapping a 1 Mb flank around that candidate. Complete coverage is explicit even when a filtered query finds no records. Gene-body spans are aggregated by stable Ensembl gene ID within chromosome; TSS positions remain transcript- and strand-specific.

GENCODE v36 is a **new versioned analysis**, not exact reproduction of the publication's Ensembl release 103 selection pipeline or its GENCODE v35 expression quantification. GENCODE access/citation information: [Data access](https://www.gencodegenes.org/pages/data_access.html). UCSC source byte hashes are preserved.

Chromosome lengths come from UCSC hg38 `chromInfo.txt.gz`: chromosomes 1–22, X, Y and M. Reference windows contain the candidate plus 100 bp on either side and were fetched through the [UCSC sequence API](https://genome.ucsc.edu/goldenPath/help/api.html). Every window's returned start/end, base count, byte hash and plus-reference orientation are checked. These cropped windows must be rendered with their recorded genomic offsets; they are not whole-chromosome FASTA files suitable for silently substituting into an igv.js genome definition.

## Actual observed discrepancy

Unique versioned Ensembl IDs in the H1 source tables: **Pansio 96, Olônne 111, Keppel 139, independent untargeted control 260**. Every populated row meets the stated DE thresholds. The article prose reports 119 for Keppel. The observed 139 is retained; the discrepancy is explicitly unresolved and must not be silently replaced by 119. H9 tables contain 60, 51, 91 and 15 respectively. These are inspected source-table counts, not independently reprocessed sequencing results or validated biological conclusions.

## Frozen scientific semantics

`normalized/criteria.json` fixes named criteria and numerical thresholds independently of the harness. Gene-body overlap and TSS distance are separate. Any missing required criterion keeps the aggregate screen incomplete, while individual failures remain visible. Experimental evidence status addresses a named endpoint, assay and cell context only. There is no global safe label, inferred causal threshold or automatic candidate-exclusion threshold based on DE count, overlap or distance.

Cancer-gene source/licensing, ultraconserved regions, DHS buffers, and optional H1 cCREs are unavailable in the current pack. Publication claims about these criteria do not count as newly computed passes. Optional tracks and expansion to more candidates are deferred. Deterministic science tools and reference-answer adjudication are separate dependent tickets; this source pack does not itself establish model reasoning quality.

## Current delivery

D01–D04: source pack, immutable criteria, normalized candidates, reference windows and annotation coverage ready. Acceptance evidence is `normalized/integrity_report.json`, generated by actual hash/schema/data checks. Next dependencies: D05 interval tools, D06 expression/control/proximity calculations, D07 bounded worker interface. D08 must independently recompute reference outputs and record the actual reviewer status.

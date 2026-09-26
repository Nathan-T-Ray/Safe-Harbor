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

`wgEncodeGencodeCompV36.txt.gz`, `wgEncodeGencodeAttrsV36.txt.gz`, `wgEncodeGencodePseudoGeneV36.txt.gz` and their corresponding SQL schemas were downloaded and inspected from the [UCSC hg38 database directory](https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/). SQL field counts are validated during parsing. The separate pseudogene table was added after detecting that Comp alone omits most pseudogenes; it is a real compact source, not inferred annotation. The combined canonical-chromosome gene count is **60,660**, matching [GENCODE v36's official statistics](https://www.gencodegenes.org/human/stats_36.html). Each displayed neighborhood contains all transcript records from both tables overlapping a 1 Mb flank around that candidate. Complete coverage is explicit and names the tables, even when a filtered query finds no records. Gene-body spans are aggregated by stable Ensembl gene ID within chromosome; TSS positions remain transcript- and strand-specific.

GENCODE v36 is a **new versioned analysis**, not exact reproduction of the publication's Ensembl release 103 selection pipeline or its GENCODE v35 expression quantification. GENCODE access/citation information: [Data access](https://www.gencodegenes.org/pages/data_access.html). UCSC source byte hashes are preserved.

Chromosome lengths come from UCSC hg38 `chromInfo.txt.gz`: chromosomes 1–22, X, Y and M. Reference windows contain the candidate plus 100 bp on either side and were fetched through the [UCSC sequence API](https://genome.ucsc.edu/goldenPath/help/api.html). Every window's returned start/end, base count, byte hash and plus-reference orientation are checked. These cropped windows must be rendered with their recorded genomic offsets; they are not whole-chromosome FASTA files suitable for silently substituting into an igv.js genome definition.

## Actual observed discrepancy

Unique versioned Ensembl IDs in the H1 source tables: **Pansio 96, Olônne 111, Keppel 139, independent untargeted control 260**. Every populated row meets the stated DE thresholds. The article prose reports 119 for Keppel. The observed 139 is retained; the discrepancy is explicitly unresolved and must not be silently replaced by 119. H9 tables contain 60, 51, 91 and 15 respectively. These are inspected source-table counts, not independently reprocessed sequencing results or validated biological conclusions.

## Frozen scientific semantics

`normalized/criteria.json` fixes named criteria and numerical thresholds independently of the harness; its SHA-256 is in the manifest and every tool result. Gene-body overlap and TSS distance are separate. Both Bioframe interval gap and nearest included reference-base distance are reported. For disjoint half-open intervals, nearest-base distance is gap plus one; overlapping intervals have zero for both. The source's literal greater-than thresholds apply to nearest-base distance, explicitly declared before assessment/evaluation. For example Pansio's nearest TSS has a 50,000 bp interval gap and 50,001 bp nearest-base distance. This is part of the new versioned annotation analysis, not a claim to reproduce the original pipeline. Any missing required criterion keeps the aggregate screen incomplete, while individual failures remain visible. Experimental evidence status addresses a named endpoint, assay and cell context only. There is no global safe label, inferred causal threshold or automatic candidate-exclusion threshold based on DE count, overlap or distance.

Cancer-gene source/licensing, ultraconserved regions, DHS buffers, and optional H1 cCREs are unavailable in the current pack. Publication claims about these criteria do not count as newly computed passes. Optional tracks and expansion to more candidates are deferred. Deterministic science tools and reference-answer adjudication are separate dependent tickets; this source pack does not itself establish model reasoning quality.

## Current delivery

D01–D04: source pack, immutable criteria, normalized candidates, reference windows and annotation coverage ready. Acceptance evidence is `normalized/integrity_report.json`, generated by actual hash/schema/data checks (15 source files after pseudogene augmentation). D05–D07 calculation/tool modules are implemented and have executed against all three real candidates; actual API/model integration remains the runtime/E2E acceptance step. D08 must independently recompute reference outputs and record the actual reviewer status.

## Bounded worker tools

`science.run_tool(name, candidate_id, arguments={})` accepts only the approved names exported by `APPROVED_TOOL_NAMES`. `science.tool_definitions(names)` supplies model-facing JSON schemas. Unknown IDs, names and extra arguments are rejected; no tool opens an arbitrary URL/path/artifact. Each result includes source hashes, evidence IDs, criteria hash, parameters, limitations and consumed query scopes. Results are capped at 30,000 bytes. Runtime must stamp query versions from the ledger rather than treating the source-pack default version as the current run revision.

| Tool | Scope and bounded arguments |
| --- | --- |
| inspect_candidate | Selected verified region, methods and frozen criteria |
| list_evidence | Source availability and coverage; unavailable is distinct from a zero-row result |
| table_slice | `contrast: candidate|untargeted`, offset 0–1000, limit 1–20; original numerical expression inputs with sheet/row provenance |
| expression_comparison | Unique versioned/stable DE counts, duplicates, threshold checks, control counts if available and five-replicate qPCR means |
| control_overlap | Recomputed intersection/union, both denominator fractions, Jaccard and direction concordance; original precomputed flags are checked only for discrepancy |
| gene_proximity | Bioframe nearest mapped DE gene bodies, all unmapped IDs, distinct original-table coordinates and explicit mapping limits |
| screen_candidate | Frozen genomic criteria, strand-aware transcript TSS, named missing evidence, incomplete aggregate |
| reference_sequence | 1–240 actual bases; offset relative to selected region start, constrained to the frozen window |

`cell_context` is H1 by default; H9 is explicitly a different context. Runtime injects `controls_available` from authoritative evidence availability for expression/list/table/overlap tools; it is absent from model-facing schemas. With controls withdrawn, no control count/set result is returned and requesting the untargeted table is rejected. Source precomputed overlap flags are excluded from table slices. Runtime must also prevent retrieval of prior control-derived artifacts after the corresponding revision.

Measured H1 tool outputs (significant-only gene sets): Pansio shares **31/96** genes with the independent untargeted control's **260**; Olônne **40/111**; Keppel **48/139**. Nearest mapped GENCODE DE gene-body gaps are **4,352,715 bp**, **32,399,164 bp**, and **774,116 bp**, respectively. Mapped counts are 90/96, 103/111 and 130/139; unmapped identifiers prevent treating those distances as an assertion about every DE gene. The original table-coordinate calculation remains visible separately. Overlap and distance do not determine causality or establish safety.

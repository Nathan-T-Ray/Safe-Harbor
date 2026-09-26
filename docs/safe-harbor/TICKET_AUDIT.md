# Safe Harbor ticket publication audit

Read-only audit of ticket specifications, generated ticket/assignment documents, the claim helper, contributor guidance and the completed data delivery. This audit did not claim tickets, edit GitHub issues, rerun publication or run unit/component tests.

## Coverage and specification preservation

**Pass:** 60 unique specification records: F01–F04, D01–D10, R01–R12, H01–H08, U01–U14 and Q01–Q12. There are 60 corresponding ticket documents and 60 assignment documents. No missing or extra IDs were found. All dependency IDs resolve and the complete dependency graph is acyclic.

Every generated ticket retains its specification's complete title, work text and acceptance criteria. Dependencies and range expansions match the original handoff, including R04's D07 tool-signature dependency and Q11's Q01–Q09 prerequisites. Human review, actual process death, real model proposal, fair baselines, unknown usage and honest replay conditions remain explicit. This is a document/schema integrity check, not evidence that these tickets are implemented.

At the final audit read, `github-issues.json` contains all 60 ticket mappings and board issue [35](https://github.com/Nathan-T-Ray/Safe-Harbor/issues/35). The audit verified the local publication manifest, not every issue's remote state. The live GitHub issue remains authoritative.

## Claim visibility

**Pass:** generated tickets and assignments visibly distinguish claimed and unclaimed work. The publication snapshot has 28 claimed tickets: integrator 4, data 4, runtime 9, UI 11; 32 tickets are available. Assignment documents explicitly require refreshing live ownership. Available means unclaimed, not dependency-ready. The board links filtered live lists, and contributor guidance requires isolated worktrees and small reviewed integrations.

The helper refuses a non-UNCLAIMED owner, requires owner/branch/paths for a claim, checks the current body again before editing, and verifies the resulting owner marker. Release checks both named ownership and the assigned GitHub operator. The documented cooperative limitation is accurate: the separate read and edit calls do not provide an atomic distributed lock. Do not advertise stronger locking.

## Issues to correct

1. **Stale ownership in CONTRIBUTING.md.** The working-interface paragraph says R01–R04 are claimed and R05–R12 are available, whereas the current ticket board reserves R01–R09 for `codex-runtime`. Update the paragraph to R01–R09 claimed / R10–R12 available so an external contributor does not select an already-owned runtime ticket.
2. **Stale STATUS.md.** It still reserves all data tools, all runtime work and all UI work in broad lanes, says the source files and MongoDB transactions are unverified, and describes the implementation as awaiting contracts. Replace this startup snapshot with current verified delivery and precise claimed ranges, or prominently mark it historical and point to the authoritative board. It currently contradicts both DATA.md and CONTRIBUTING.md.
3. **Claim lifecycle labels can become contradictory after release.** The helper removes only `status:claimed` when releasing. A ticket previously moved to the documented `status:review` or `status:blocked` can retain that label while receiving `status:available`. Remove the other mutually exclusive status labels on a transition, or define retained labels as orthogonal and adjust the documentation. This does not block initial publication because current generated claims use claimed/available only.
4. **Ownership is broader than a single lifecycle label.** CONTRIBUTING.md says a ticket is claimed only when it has `status:claimed`, then says review/blocked states retain ownership. Clarify that a non-UNCLAIMED owner remains reserved in review/blocked states and include those states when instructing contributors to inspect current owners. The helper already checks the owner marker, so this is principally a visibility/documentation issue.

## Path overlap assessment

Generated data tool tickets use separate proposed modules (`calculations.py`, `expression_tools.py`, `tools.py`), runtime R10–R12 use distinct modules, and U11/U13/U14 have separate proposed files. This supports external contribution now. Integrator retains contracts, dependencies and startup. Existing broad UI and runtime reservations are explicitly identified.

Remaining coordinated boundaries: data tool exports through `science/__init__.py`; runtime context/assessment/export imports through existing coordinator/API modules; UI cues/presentation integration through App; H01/H02 share the harness package; H03/H04 share `evaluation/baselines.py`; D08/D09 require an evaluator distinct from the production calculation implementer; Q01's broad E2E scope overlaps narrower Q tickets. Contributors should claim exact new files and obtain an integration handoff for edits to reserved files. The helper does not enforce filesystem overlap; the documents correctly require manual coordination.

## D01–D04 acceptance recommendation

**Ready for integrator acceptance/closure based on the actual data-integrity evidence, not merely file existence.**

- D01: versioned criteria define each governing threshold/input/missing-evidence rule, separate gene body and strand-specific TSS, separate endpoint/context evidence, and make criteria immutable to the optimizer.
- D02: five actual v2 workbooks are preserved with byte hashes; all sheet/column/row content and merged-cell metadata are inventoried; expression rows retain original file/sheet/row/hash; significant-only scope and H1/H9 contrasts are explicit.
- D03: the three named intervals are cross-matched between Supplement 1 and Supplement 5 sheet titles; source inclusive widths validate start-minus-one conversion; GRCh38 and grouping provenance are preserved.
- D04: actual UCSC sequence responses, chromosome lengths, both GENCODE v36 files and SQL schemas are frozen; complete canonical annotation was parsed into explicit covered neighborhoods; sequence length/hash/orientation and transcript strand/TSS checks pass; catalog records validate against the shared Candidate schema.

The integrator independently ran the delivered data-integrity command. The current report records 13 verified sources, 3 candidates and 25 canonical chromosomes. This audit did not independently redo RNA-seq or biological adjudication; those belong to D05–D09. H1 Keppel's source-table count is 139 versus article prose 119, explicitly unresolved and preserved. Missing cancer/regulatory evidence remains incomplete. No global safety or model-quality claim follows from closing these ingestion tickets.

D05–D07 remain unclaimed by this auditor. They are the next vertical-slice dependency, with runtime requiring bounded `run_tool` results and explicit expression/control evidence-availability handling.

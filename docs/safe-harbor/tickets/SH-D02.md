<!-- claim-start -->
<!-- claim-owner: codex-data -->
## CLAIMED — codex-data
**Owner:** codex-data
**GitHub operator:** @Nathan-T-Ray
**Branch:** `main`
**Reserved paths:** `backend/safe_harbor/science/ingest.py`, `data/safe_harbor/normalized/`
**Updated:** 2026-09-26T18:29:45.963349+00:00
Do not duplicate this work or edit reserved paths without coordinating with the owner.
<!-- claim-end -->

# SH-D02 — Ingest the compact experimental source pack

**Lane:** Data
**Dependencies:** [SH-F04](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/tickets/SH-F04.md)
**Proposed file scope:** `backend/safe_harbor/science/ingest.py`, `data/safe_harbor/normalized/`

## Work

Download the five supplements, hash actual bytes, inventory sheets/columns, and preserve original files alongside normalized data. Identify cell lines, comparisons, thresholds and whether tables contain only significant results.

## Acceptance criteria

Every normalized row points back to a real file, sheet and row. Re-ingestion is reproducible.

## Required handoff

- Changed paths and commit/PR.
- What now works.
- Actual acceptance evidence.
- Remaining limitations.
- Next dependent ticket and owner.

## Shared boundaries

**NO UNIT TESTS. NO COMPONENT TESTS. E2E ONLY.** Build/type/syntax/schema/data-integrity checks are allowed. Use real coordinates, sequence, annotations and source tables. No fabricated biology, model runs or improvements. Distinguish mock, deterministic operational, real model and recorded replay.

Only the integrator edits shared contracts, root dependency manifests/locks and startup composition. Scientific tools return bounded typed data; runtime owns database writes; frontend derives no biological verdicts. At most two runtime workers, 24 nodes, three replans and one transient retry. Harness changes cannot alter criteria/evaluator/input data/model/budget/permissions.

Read [contribution and claim protocol](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/CONTRIBUTING.md), [specification](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/SPECIFICATION.md), [contracts](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/CONTRACTS.md), and [ticket board](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/TICKETS.md). Safe Harbor supersedes the old LA-* plan; do not assume inherited modules or old PRs satisfy this ticket.

Claim command: `python3 scripts/safe_harbor_ticket.py claim SH-D02 --owner YOUR_MODEL --branch YOUR_BRANCH --paths YOUR_PATHS`

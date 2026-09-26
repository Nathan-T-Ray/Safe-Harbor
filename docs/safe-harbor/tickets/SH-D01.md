<!-- claim-start -->
<!-- claim-owner: codex-data -->
## CLAIMED — codex-data
**Owner:** codex-data
**GitHub operator:** @Nathan-T-Ray
**Branch:** `main`
**Reserved paths:** `data/safe_harbor/normalized/criteria.json`, `backend/safe_harbor/science/ingest.py`
**Updated:** 2026-09-26T18:41:21.061334+00:00
Do not duplicate this work or edit reserved paths without coordinating with the owner.
<!-- claim-end -->

# SH-D01 — Freeze scientific criteria and result semantics

**Lane:** Data
**Dependencies:** [SH-F02](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/tickets/SH-F02.md)
**Proposed file scope:** `data/safe_harbor/normalized/criteria.json`, `backend/safe_harbor/science/ingest.py`

## Work

Specify each criterion’s source, threshold, inputs and missing-data behavior. Separate gene-body distance from transcription-start distance and experimental endpoints from computational screens.

## Acceptance criteria

Every eventual verdict can identify its governing criterion. The harness optimizer cannot alter these criteria.

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

Claim command: `python3 scripts/safe_harbor_ticket.py claim SH-D01 --owner YOUR_MODEL --branch YOUR_BRANCH --paths YOUR_PATHS`

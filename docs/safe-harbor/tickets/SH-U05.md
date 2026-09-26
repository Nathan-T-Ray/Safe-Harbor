<!-- claim-start -->
<!-- claim-owner: codex-ui -->
## CLAIMED — codex-ui
**Owner:** codex-ui
**GitHub operator:** @Nathan-T-Ray
**Branch:** `main`
**Reserved paths:** `frontend/src/safe-harbor/Genome.tsx`, `frontend/src/safe-harbor/App.tsx`
**Updated:** 2026-09-26T18:41:21.061334+00:00
Do not duplicate this work or edit reserved paths without coordinating with the owner.
<!-- claim-end -->

# SH-U05 — Connect overview, chromosome, locus and sequence zoom

**Lane:** UI
**Dependencies:** [SH-U02](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/tickets/SH-U02.md), [SH-U03](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/tickets/SH-U03.md), [SH-U04](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/tickets/SH-U04.md)
**Proposed file scope:** `frontend/src/safe-harbor/Genome.tsx`, `frontend/src/safe-harbor/App.tsx`

## Work

Create a shared viewport state containing assembly, chromosome, interval, selection and zoom level. Transition between representations without losing the selected locus.

## Acceptance criteria

Users can zoom in and back out with consistent coordinates and breadcrumbs. Respect available data boundaries.

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

Claim command: `python3 scripts/safe_harbor_ticket.py claim SH-U05 --owner YOUR_MODEL --branch YOUR_BRANCH --paths YOUR_PATHS`

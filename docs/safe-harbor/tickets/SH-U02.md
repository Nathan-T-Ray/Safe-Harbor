<!-- claim-start -->
<!-- claim-owner: codex-ui -->
## CLAIMED — codex-ui
**Owner:** codex-ui
**GitHub operator:** @Nathan-T-Ray
**Branch:** `main`
**Reserved paths:** `frontend/src/safe-harbor/Genome.tsx`
**Updated:** 2026-09-26T18:29:45.963349+00:00
Do not duplicate this work or edit reserved paths without coordinating with the owner.
<!-- claim-end -->

# SH-U02 — Build the coordinate-correct genome overview

**Lane:** UI
**Dependencies:** [SH-D03](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/tickets/SH-D03.md), [SH-D04](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/tickets/SH-D04.md)
**Proposed file scope:** `frontend/src/safe-harbor/Genome.tsx`

## Work

Render chromosome bars from actual lengths and candidate markers from actual intervals. Use neutral unexplored background and clear selection.

## Acceptance criteria

Marker placement is mathematically tied to genomic position, not decorative spacing. Selecting a marker selects the same candidate everywhere.

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

Claim command: `python3 scripts/safe_harbor_ticket.py claim SH-U02 --owner YOUR_MODEL --branch YOUR_BRANCH --paths YOUR_PATHS`

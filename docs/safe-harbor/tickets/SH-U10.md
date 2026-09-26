<!-- claim-start -->
<!-- claim-owner: codex-ui -->
## CLAIMED — codex-ui
**Owner:** codex-ui
**GitHub operator:** @Nathan-T-Ray
**Branch:** `main`
**Reserved paths:** `frontend/src/safe-harbor/record.ts`, `frontend/src/safe-harbor/Timeline.tsx`
**Updated:** 2026-09-26T18:41:21.061334+00:00
Do not duplicate this work or edit reserved paths without coordinating with the owner.
<!-- claim-end -->

# SH-U10 — Implement deterministic timeline replay

**Lane:** UI
**Dependencies:** [SH-U09](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/tickets/SH-U09.md), [SH-R12](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/tickets/SH-R12.md)
**Proposed file scope:** `frontend/src/safe-harbor/record.ts`, `frontend/src/safe-harbor/Timeline.tsx`

## Work

Support play, pause, seek, speed control and meaningful-event navigation. Rebuild state from events or versioned replay snapshots.

## Acceptance criteria

Seeking backward restores earlier assessments and source versions. Final results never leak into an earlier replay frame.

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

Claim command: `python3 scripts/safe_harbor_ticket.py claim SH-U10 --owner YOUR_MODEL --branch YOUR_BRANCH --paths YOUR_PATHS`

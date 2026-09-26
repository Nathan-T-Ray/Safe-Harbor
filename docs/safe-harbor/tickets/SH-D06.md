<!-- claim-start -->
<!-- claim-owner: UNCLAIMED -->
## AVAILABLE — UNCLAIMED
**Owner:** UNCLAIMED
**GitHub operator:** unassigned
**Branch:** unassigned — branch from `main`
**Reserved paths:** none; proposed scope listed below
**Updated:** 2026-09-26T18:29:45.963349+00:00
Available to claim. Dependencies still govern acceptance; check adjacent path owners first.
<!-- claim-end -->

# SH-D06 — Implement expression/control/proximity calculations

**Lane:** Data
**Dependencies:** [SH-D02](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/tickets/SH-D02.md), [SH-D04](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/tickets/SH-D04.md), [SH-D05](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/tickets/SH-D05.md)
**Proposed file scope:** `backend/safe_harbor/science/expression_tools.py`

## Work

Identify exact contrasts, count the defined gene units, compute control overlaps with explicit denominators, and locate relevant genes relative to candidates.

## Acceptance criteria

Outputs reproduce reported counts or preserve diagnosed discrepancies. Duplicate and unmapped identifiers are visible. Computed values are never overwritten to match a paper.

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

Claim command: `python3 scripts/safe_harbor_ticket.py claim SH-D06 --owner YOUR_MODEL --branch YOUR_BRANCH --paths YOUR_PATHS`

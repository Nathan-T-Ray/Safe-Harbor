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

# SH-Q06 — Exercise answer-key and tool-access isolation

**Lane:** E2E
**Dependencies:** [SH-H05](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/tickets/SH-H05.md)
**Proposed file scope:** `e2e/safe_harbor/isolation.py`

## Work

Attempt evaluator-data access through the worker's available interfaces. Attempt unapproved tools and out-of-manifest artifacts.

## Acceptance criteria

Access is denied by actual boundaries, not merely by prompt instructions. The scored worker can still complete legitimate tasks.

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

Claim command: `python3 scripts/safe_harbor_ticket.py claim SH-Q06 --owner YOUR_MODEL --branch YOUR_BRANCH --paths YOUR_PATHS`

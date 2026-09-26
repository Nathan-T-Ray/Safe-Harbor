<!-- claim-start -->
<!-- claim-owner: codex-integrator -->
## CLAIMED — codex-integrator
**Owner:** codex-integrator
**GitHub operator:** @Nathan-T-Ray
**Branch:** `main`
**Reserved paths:** `docs/safe-harbor/TICKETS.md`, `docs/safe-harbor/CLAIMS.md`, `docs/safe-harbor/assignments/`
**Updated:** 2026-09-26T18:41:21.061334+00:00
Do not duplicate this work or edit reserved paths without coordinating with the owner.
<!-- claim-end -->

# SH-F03 — Assign ownership and integration order

**Lane:** Integrator
**Dependencies:** [SH-F02](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/tickets/SH-F02.md)
**Proposed file scope:** `docs/safe-harbor/TICKETS.md`, `docs/safe-harbor/CLAIMS.md`, `docs/safe-harbor/assignments/`

## Work

Assign directories and tickets to agents. Establish one owner for schema changes. Require small integrations instead of large diverging branches.

## Acceptance criteria

Each active agent has a bounded task, dependencies and acceptance criteria; no two agents unknowingly edit the same integration surface.

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

Claim command: `python3 scripts/safe_harbor_ticket.py claim SH-F03 --owner YOUR_MODEL --branch YOUR_BRANCH --paths YOUR_PATHS`

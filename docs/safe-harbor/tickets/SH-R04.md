<!-- claim-start -->
<!-- claim-owner: codex-runtime -->
## CLAIMED — codex-runtime
**Owner:** codex-runtime
**GitHub operator:** @Nathan-T-Ray
**Branch:** `main`
**Reserved paths:** `backend/safe_harbor/runtime/compiler.py`
**Updated:** 2026-09-26T18:29:45.963349+00:00
Do not duplicate this work or edit reserved paths without coordinating with the owner.
<!-- claim-end -->

# SH-R04 — Build the typed DAG compiler

**Lane:** Runtime
**Dependencies:** [SH-F02](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/tickets/SH-F02.md), [SH-D07](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/tickets/SH-D07.md)
**Proposed file scope:** `backend/safe_harbor/runtime/compiler.py`

## Work

Validate node kinds, dependency references, tools, output references, acyclicity and size limits. Use standard topological sorting. Validate complete proposed plans before dispatch.

## Acceptance criteria

Invalid plans fail before work begins and valid independent branches can share upstream evidence.

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

Claim command: `python3 scripts/safe_harbor_ticket.py claim SH-R04 --owner YOUR_MODEL --branch YOUR_BRANCH --paths YOUR_PATHS`

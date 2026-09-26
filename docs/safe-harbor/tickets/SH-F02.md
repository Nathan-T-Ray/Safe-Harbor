<!-- claim-start -->
<!-- claim-owner: codex-integrator -->
## CLAIMED — codex-integrator
**Owner:** codex-integrator
**GitHub operator:** @Nathan-T-Ray
**Branch:** `main`
**Reserved paths:** `shared/`, `docs/safe-harbor/CONTRACTS.md`
**Updated:** 2026-09-26T18:29:45.963349+00:00
Do not duplicate this work or edit reserved paths without coordinating with the owner.
<!-- claim-end -->

# SH-F02 — Freeze schema version 1 and publish fixtures

**Lane:** Integrator
**Dependencies:** [SH-F01](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/tickets/SH-F01.md)
**Proposed file scope:** `shared/`, `docs/safe-harbor/CONTRACTS.md`

## Work

Define the shared records, statuses, coordinate convention, API bodies and event envelope. Publish an initial snapshot, completion event, revision sequence and harness-comparison fixture.

## Acceptance criteria

UI and backend agents can work independently against identical contracts. All fictional fixtures carry mode: mock.

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

Claim command: `python3 scripts/safe_harbor_ticket.py claim SH-F02 --owner YOUR_MODEL --branch YOUR_BRANCH --paths YOUR_PATHS`

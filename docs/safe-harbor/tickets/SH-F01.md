<!-- claim-start -->
<!-- claim-owner: codex-integrator -->
## CLAIMED — codex-integrator
**Owner:** codex-integrator
**GitHub operator:** @Nathan-T-Ray
**Branch:** `main`
**Reserved paths:** `README.md`, `AGENTS.md`, `docs/safe-harbor/`
**Updated:** 2026-09-26T18:41:21.061334+00:00
Do not duplicate this work or edit reserved paths without coordinating with the owner.
<!-- claim-end -->

# SH-F01 — Establish the working repository and short operating documents

**Lane:** Integrator
**Dependencies:** None
**Proposed file scope:** `README.md`, `AGENTS.md`, `docs/safe-harbor/`

## Work

Use the intended new checkout. Record the product, scope, source status and ticket board in the repository. Inspect any existing files before reuse; do not assume old Living Atlas code implements this design.

## Acceptance criteria

The checkout has a clear README, ticket board, startup plan and explicit E2E-only instruction. Do not spend an hour polishing documentation.

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

Claim command: `python3 scripts/safe_harbor_ticket.py claim SH-F01 --owner YOUR_MODEL --branch YOUR_BRANCH --paths YOUR_PATHS`

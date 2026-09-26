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

# SH-D08 — Independently establish reference answers

**Lane:** Evaluator
**Dependencies:** [SH-D05](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/tickets/SH-D05.md), [SH-D06](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/docs/safe-harbor/tickets/SH-D06.md)
**Proposed file scope:** `backend/safe_harbor/evaluation/reference_answers.py`, `data/safe_harbor/evaluator/`

## Work

Recompute expected numerical outputs independently of the production tool path. Write source-backed interpretation rubrics and record actual reviewer status.

## Acceptance criteria

Expected results include justification and tolerances where appropriate. Do not label answers “human-reviewed” until a human has reviewed them.

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

Claim command: `python3 scripts/safe_harbor_ticket.py claim SH-D08 --owner YOUR_MODEL --branch YOUR_BRANCH --paths YOUR_PATHS`

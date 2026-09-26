# Assignment: SH-D08

Implement [SH-D08: Independently establish reference answers](../tickets/SH-D08.md) from `origin/main`.

Current publication-time status: **AVAILABLE — UNCLAIMED**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/evaluation/reference_answers.py`, `data/safe_harbor/evaluator/`. Coordinate shared interfaces and overlapping files. Dependencies: D05, D06.

Work: Recompute expected numerical outputs independently of the production tool path. Write source-backed interpretation rubrics and record actual reviewer status.

Accept only when: Expected results include justification and tolerances where appropriate. Do not label answers “human-reviewed” until a human has reviewed them.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

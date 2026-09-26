# Assignment: SH-H08

Implement [SH-H08: Publish transparent comparison results](../tickets/SH-H08.md) from `origin/main`.

Current publication-time status: **AVAILABLE — UNCLAIMED**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/evaluation/report.py`, `docs/safe-harbor/EVALUATION.md`. Coordinate shared interfaces and overlapping files. Dependencies: H07, R12.

Work: Report per-case outcomes, required-answer accuracy, unsupported conclusions, completion, tokens, calls, duration and cost. Show optimizer/evaluation overhead separately and in total.

Accept only when: Charts, exports and raw records agree. A single noisy cost result is labeled provisional; absent improvement is reported honestly.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

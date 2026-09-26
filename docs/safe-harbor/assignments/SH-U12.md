# Assignment: SH-U12

Implement [SH-U12: Build the harness-change comparison drawer](../tickets/SH-U12.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-ui**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `frontend/src/safe-harbor/Harness.tsx`. Coordinate shared interfaces and overlapping files. Dependencies: H08, U07.

Work: Show parent and candidate architecture, a readable policy diff, validation results and promotion/rejection.

Accept only when: Judges can identify what changed in execution and what happened to measured performance. Display actual values, including failures.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

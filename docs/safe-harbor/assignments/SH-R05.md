# Assignment: SH-R05

Implement [SH-R05: Implement bounded scheduling and deduplication](../tickets/SH-R05.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-runtime**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/runtime/coordinator.py`. Coordinate shared interfaces and overlapping files. Dependencies: R02, R04.

Work: Select ready tasks, enforce two-worker concurrency and use canonical question keys. Stop on completion, no useful action or exhausted limits.

Accept only when: Dependencies are respected, repeated questions cannot create an infinite investigation, and remaining uncertainty is preserved.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

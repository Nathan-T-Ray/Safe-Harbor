# Assignment: SH-Q08

Implement [SH-Q08: Prove replay equals committed state](../tickets/SH-Q08.md) from `origin/main`.

Current publication-time status: **AVAILABLE — UNCLAIMED**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `e2e/safe_harbor/replay.mjs`. Coordinate shared interfaces and overlapping files. Dependencies: U10.

Work: Start with an empty client, replay through a chosen watermark and compare the resulting entities with the backend snapshot.

Accept only when: Candidates, tasks, assessments, versions and totals agree. Repeated seeks remain deterministic.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

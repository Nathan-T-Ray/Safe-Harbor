# Assignment: SH-H04

Implement [SH-H04: Implement the all-checks-plus-synthesis baseline](../tickets/SH-H04.md) from `origin/main`.

Current publication-time status: **AVAILABLE — UNCLAIMED**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/evaluation/baselines.py`. Coordinate shared interfaces and overlapping files. Dependencies: H03.

Work: Run all available relevant deterministic analyses followed by a competent synthesis call, under the same budget cap and evidence conditions.

Accept only when: Its performance and resource use are measured alongside the agent baseline. This is the key check against unnecessary agent complexity.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

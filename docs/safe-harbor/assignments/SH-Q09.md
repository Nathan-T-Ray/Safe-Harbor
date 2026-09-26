# Assignment: SH-Q09

Implement [SH-Q09: Prove the genome zoom remains truthful](../tickets/SH-Q09.md) from `origin/main`.

Current publication-time status: **AVAILABLE — UNCLAIMED**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `e2e/safe_harbor/genome.mjs`. Coordinate shared interfaces and overlapping files. Dependencies: U05, U11, U14.

Work: Select a real candidate, travel through all four zoom levels, inspect bases and return to overview. Repeat during replay at an older revision.

Accept only when: Genomic position, selected evidence and historical version remain consistent throughout the animation.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

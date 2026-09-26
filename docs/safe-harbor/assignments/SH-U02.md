# Assignment: SH-U02

Implement [SH-U02: Build the coordinate-correct genome overview](../tickets/SH-U02.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-ui**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `frontend/src/safe-harbor/Genome.tsx`. Coordinate shared interfaces and overlapping files. Dependencies: D03, D04.

Work: Render chromosome bars from actual lengths and candidate markers from actual intervals. Use neutral unexplored background and clear selection.

Accept only when: Marker placement is mathematically tied to genomic position, not decorative spacing. Selecting a marker selects the same candidate everywhere.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

# Assignment: SH-D06

Implement [SH-D06: Implement expression/control/proximity calculations](../tickets/SH-D06.md) from `origin/main`.

Current publication-time status: **AVAILABLE — UNCLAIMED**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/science/expression_tools.py`. Coordinate shared interfaces and overlapping files. Dependencies: D02, D04, D05.

Work: Identify exact contrasts, count the defined gene units, compute control overlaps with explicit denominators, and locate relevant genes relative to candidates.

Accept only when: Outputs reproduce reported counts or preserve diagnosed discrepancies. Duplicate and unmapped identifiers are visible. Computed values are never overwritten to match a paper.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

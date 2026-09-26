# Assignment: SH-D03

Implement [SH-D03: Import and normalize candidate regions](../tickets/SH-D03.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-data**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/science/catalog.py`, `data/safe_harbor/normalized/candidates.json`. Coordinate shared interfaces and overlapping files. Dependencies: D02.

Work: Import the published candidate coordinates, beginning with the three named demonstration loci. Preserve original notation, confirm assembly and interval widths, and convert explicitly to internal coordinates.

Accept only when: Candidate names resolve to verified intervals; no coordinate was guessed. Nearby or related candidates have grouping IDs for evaluation splitting.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

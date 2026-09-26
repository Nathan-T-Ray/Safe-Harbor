# Assignment: SH-U04

Implement [SH-U04: Build the reference-base strip](../tickets/SH-U04.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-ui**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `frontend/src/safe-harbor/Genome.tsx`. Coordinate shared interfaces and overlapping files. Dependencies: D04.

Work: Render a short frozen sequence window with coordinate ticks, readable bases and candidate highlighting. Preserve reference orientation and label strand-specific transformations explicitly.

Accept only when: Displayed bases match the artifact bytes and genomic offsets. No decorative random DNA appears in a scientific view.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

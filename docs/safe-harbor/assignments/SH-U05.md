# Assignment: SH-U05

Implement [SH-U05: Connect overview, chromosome, locus and sequence zoom](../tickets/SH-U05.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-ui**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `frontend/src/safe-harbor/Genome.tsx`, `frontend/src/safe-harbor/App.tsx`. Coordinate shared interfaces and overlapping files. Dependencies: U02, U03, U04.

Work: Create a shared viewport state containing assembly, chromosome, interval, selection and zoom level. Transition between representations without losing the selected locus.

Accept only when: Users can zoom in and back out with consistent coordinates and breadcrumbs. Respect available data boundaries.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

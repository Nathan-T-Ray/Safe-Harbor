# Assignment: SH-D02

Implement [SH-D02: Ingest the compact experimental source pack](../tickets/SH-D02.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-data**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/science/ingest.py`, `data/safe_harbor/normalized/`. Coordinate shared interfaces and overlapping files. Dependencies: F04.

Work: Download the five supplements, hash actual bytes, inventory sheets/columns, and preserve original files alongside normalized data. Identify cell lines, comparisons, thresholds and whether tables contain only significant results.

Accept only when: Every normalized row points back to a real file, sheet and row. Re-ingestion is reproducible.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

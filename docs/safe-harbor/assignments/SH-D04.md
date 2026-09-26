# Assignment: SH-D04

Implement [SH-D04: Freeze reference windows and annotation coverage](../tickets/SH-D04.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-data**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/science/ingest.py`, `backend/safe_harbor/science/verify_data.py`, `data/safe_harbor/normalized/reference_assets.json`. Coordinate shared interfaces and overlapping files. Dependencies: D03.

Work: Fetch bounded reference sequence and sufficient GENCODE annotation neighborhoods. Record chromosome lengths, available genomic ranges and source versions.

Accept only when: Sequence lengths match coordinates, hashes exist, and the UI can request actual bases. Empty annotation results distinguish complete coverage from missing coverage.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

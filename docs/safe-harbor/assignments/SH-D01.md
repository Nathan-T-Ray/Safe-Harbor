# Assignment: SH-D01

Implement [SH-D01: Freeze scientific criteria and result semantics](../tickets/SH-D01.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-data**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `data/safe_harbor/normalized/criteria.json`, `backend/safe_harbor/science/ingest.py`. Coordinate shared interfaces and overlapping files. Dependencies: F02.

Work: Specify each criterion’s source, threshold, inputs and missing-data behavior. Separate gene-body distance from transcription-start distance and experimental endpoints from computational screens.

Accept only when: Every eventual verdict can identify its governing criterion. The harness optimizer cannot alter these criteria.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

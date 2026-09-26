# Assignment: SH-D05

Implement [SH-D05: Implement deterministic genomic calculations](../tickets/SH-D05.md) from `origin/main`.

Current publication-time status: **AVAILABLE — UNCLAIMED**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/science/calculations.py`. Coordinate shared interfaces and overlapping files. Dependencies: D01, D04.

Work: Use Bioframe for overlap, nearest-feature and distance calculations. Handle strand when computing transcription-start positions. Record tool versions, parameters and input hashes.

Accept only when: A real candidate produces independently checkable numeric artifacts. No model performs interval arithmetic or invents eligibility thresholds.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

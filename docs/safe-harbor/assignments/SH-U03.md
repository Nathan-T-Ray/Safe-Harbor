# Assignment: SH-U03

Implement [SH-U03: Integrate the locus browser](../tickets/SH-U03.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-ui**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `frontend/src/safe-harbor/Genome.tsx`. Coordinate shared interfaces and overlapping files. Dependencies: D04, D05.

Work: Use igv.js for candidate boundaries, the exact annotation release and computed features. Verify reference configuration, offsets and asset access early.

Accept only when: Displayed coordinates and features match backend calculations. Convenient default annotations must not silently replace the computed release.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

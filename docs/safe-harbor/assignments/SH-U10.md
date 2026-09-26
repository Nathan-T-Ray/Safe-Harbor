# Assignment: SH-U10

Implement [SH-U10: Implement deterministic timeline replay](../tickets/SH-U10.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-ui**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `frontend/src/safe-harbor/record.ts`, `frontend/src/safe-harbor/Timeline.tsx`. Coordinate shared interfaces and overlapping files. Dependencies: U09, R12.

Work: Support play, pause, seek, speed control and meaningful-event navigation. Rebuild state from events or versioned replay snapshots.

Accept only when: Seeking backward restores earlier assessments and source versions. Final results never leak into an earlier replay frame.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

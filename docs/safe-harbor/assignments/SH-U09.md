# Assignment: SH-U09

Implement [SH-U09: Implement the event reducer and reconnect behavior](../tickets/SH-U09.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-ui**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `frontend/src/safe-harbor/record.ts`, `frontend/src/safe-harbor/client.ts`. Coordinate shared interfaces and overlapping files. Dependencies: U01, R03.

Work: Apply ordered upserts, deduplicate event IDs and recover sequence gaps using snapshots or missing event pages.

Accept only when: Refresh, reconnect and duplicate delivery do not corrupt state or invent task completion.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

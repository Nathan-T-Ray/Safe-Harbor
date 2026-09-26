# Assignment: SH-U11

Implement [SH-U11: Add cinematic genome-follow cues](../tickets/SH-U11.md) from `origin/main`.

Current publication-time status: **AVAILABLE — UNCLAIMED**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `frontend/src/safe-harbor/cues.ts`. Coordinate shared interfaces and overlapping files. Dependencies: U05, U10.

Work: Create a separate cue file keyed to actual event sequences: focus chromosome, zoom locus, show bases, highlight a result, then reveal the relevant graph branch.

Accept only when: Playback is smooth and synchronized with real events. Pausing or disabling camera follow leaves the application usable. Cues cannot change scientific state.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

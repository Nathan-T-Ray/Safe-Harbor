# Assignment: SH-R03

Implement [SH-R03: Implement API, snapshots and ordered polling](../tickets/SH-R03.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-runtime**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/api.py`, `backend/safe_harbor/runtime/ledger.py`. Coordinate shared interfaces and overlapping files. Dependencies: R02.

Work: Build the specified endpoints. Return consistent snapshot watermarks and bounded ascending event pages. Scope artifact access to the run.

Accept only when: A client loads a snapshot, catches up during concurrent commits and reaches the correct state without gaps.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

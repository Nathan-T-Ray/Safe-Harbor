# Assignment: SH-F02

Implement [SH-F02: Freeze schema version 1 and publish fixtures](../tickets/SH-F02.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-integrator**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `shared/`, `docs/safe-harbor/CONTRACTS.md`. Coordinate shared interfaces and overlapping files. Dependencies: F01.

Work: Define the shared records, statuses, coordinate convention, API bodies and event envelope. Publish an initial snapshot, completion event, revision sequence and harness-comparison fixture.

Accept only when: UI and backend agents can work independently against identical contracts. All fictional fixtures carry mode: mock.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

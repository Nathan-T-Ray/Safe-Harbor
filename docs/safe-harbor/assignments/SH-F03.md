# Assignment: SH-F03

Implement [SH-F03: Assign ownership and integration order](../tickets/SH-F03.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-integrator**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `docs/safe-harbor/TICKETS.md`, `docs/safe-harbor/CLAIMS.md`, `docs/safe-harbor/assignments/`. Coordinate shared interfaces and overlapping files. Dependencies: F02.

Work: Assign directories and tickets to agents. Establish one owner for schema changes. Require small integrations instead of large diverging branches.

Accept only when: Each active agent has a bounded task, dependencies and acceptance criteria; no two agents unknowingly edit the same integration surface.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

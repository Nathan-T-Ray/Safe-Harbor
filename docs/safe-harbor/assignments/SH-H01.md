# Assignment: SH-H01

Implement [SH-H01: Define executable harness specifications](../tickets/SH-H01.md) from `origin/main`.

Current publication-time status: **AVAILABLE — UNCLAIMED**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/harness/`. Coordinate shared interfaces and overlapping files. Dependencies: F02, R04.

Work: Represent roles, dependencies, context policies, tool assignments and review routing as a versioned specification. Hash and freeze it per run.

Accept only when: The runtime instantiates actual tasks from the specification, and each task records the responsible role and harness hash.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

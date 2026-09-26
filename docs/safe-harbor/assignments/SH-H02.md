# Assignment: SH-H02

Implement [SH-H02: Compile bounded structural changes](../tickets/SH-H02.md) from `origin/main`.

Current publication-time status: **AVAILABLE — UNCLAIMED**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/harness/`. Coordinate shared interfaces and overlapping files. Dependencies: H01, R10.

Work: Support a small set of meaningful mutations: split an assessment role, insert a reviewer, change context selection and reassign approved tools. Validate resulting architecture and immutable constraints.

Accept only when: A changed specification causes different executed roles or dependencies. Forbidden mutations fail before execution.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

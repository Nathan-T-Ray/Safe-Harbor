# Assignment: SH-Q03

Implement [SH-Q03: Exercise actual crash recovery](../tickets/SH-Q03.md) from `origin/main`.

Current publication-time status: **AVAILABLE — UNCLAIMED**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `e2e/safe_harbor/recovery.py`. Coordinate shared interfaces and overlapping files. Dependencies: R08.

Work: Kill the actual coordinator after acceptance but before checkpoint. Separately interrupt after budget reservation. Restart fresh processes.

Accept only when: Accepted outputs are preserved, unfinished work resumes and uncertain expenditure remains recorded.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

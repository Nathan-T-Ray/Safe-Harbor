# Assignment: SH-Q05

Implement [SH-Q05: Exercise idempotency, invalid plans and budgets](../tickets/SH-Q05.md) from `origin/main`.

Current publication-time status: **AVAILABLE — UNCLAIMED**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `e2e/safe_harbor/boundaries.py`. Coordinate shared interfaces and overlapping files. Dependencies: R05, R07, H02.

Work: Through real service paths, submit duplicate operations, conflicting duplicates, cyclic plans, unknown dependencies, prohibited patches and exhausted budgets.

Accept only when: Each fails or deduplicates correctly without corrupting the run. Produce inspectable operation/event records.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

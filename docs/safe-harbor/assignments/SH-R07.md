# Assignment: SH-R07

Implement [SH-R07: Implement durable budget accounting](../tickets/SH-R07.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-runtime**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/runtime/ledger.py`, `backend/safe_harbor/runtime/coordinator.py`. Coordinate shared interfaces and overlapping files. Dependencies: R02, R06.

Work: Reserve resources before dispatch, settle actual usage after responses and retain uncertain expenditure after interruption. Record retries and tool/model costs separately.

Accept only when: Exhausted budgets prevent further work, and a crashed call is not silently counted as free.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

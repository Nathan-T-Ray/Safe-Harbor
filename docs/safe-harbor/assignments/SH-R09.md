# Assignment: SH-R09

Implement [SH-R09: Implement evidence revisions and selective invalidation](../tickets/SH-R09.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-runtime**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/runtime/revisions.py`, `backend/safe_harbor/runtime/ledger.py`. Coordinate shared interfaces and overlapping files. Dependencies: R02, R04, R08.

Work: Track the complete input read set, including evidence-query scopes. Version updated artifacts, mark affected assessments stale and create successor tasks without deleting history.

Accept only when: An affected in-flight result is rejected, affected branches reopen and unrelated valid work remains usable.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

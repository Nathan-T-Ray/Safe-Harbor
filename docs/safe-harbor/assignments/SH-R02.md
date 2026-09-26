# Assignment: SH-R02

Implement [SH-R02: Implement transactional result acceptance](../tickets/SH-R02.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-runtime**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/runtime/ledger.py`. Coordinate shared interfaces and overlapping files. Dependencies: R01.

Work: Validate operation hash, coordinator epoch and consumed evidence versions. Commit accepted output, task state, assessment pointers, budget changes and event atomically.

Accept only when: Duplicate identical submission returns the existing result; conflicting reuse fails without modifying state. External calls occur outside transactions.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

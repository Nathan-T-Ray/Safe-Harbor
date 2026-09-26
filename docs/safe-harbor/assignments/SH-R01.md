# Assignment: SH-R01

Implement [SH-R01: Create MongoDB collections and indexes](../tickets/SH-R01.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-runtime**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/runtime/ledger.py`. Coordinate shared interfaces and overlapping files. Dependencies: F02, F04.

Work: Implement collections and uniqueness constraints for runs, artifact IDs, harness hashes, operation IDs and event sequences. Keep immutable artifacts separate from mutable current pointers.

Accept only when: Initialization is repeatable and a restarted API retrieves identical stored records.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

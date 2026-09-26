# Assignment: SH-R08

Implement [SH-R08: Implement checkpoints and fresh-process recovery](../tickets/SH-R08.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-runtime**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/runtime/coordinator.py`. Coordinate shared interfaces and overlapping files. Dependencies: R05, R06, R07.

Work: Integrate MongoDBSaver. Reconcile checkpoints against accepted operations. Use coordinator epochs and leases so obsolete processes cannot commit results after replacement.

Accept only when: Killing the process after acceptance but before checkpoint does not duplicate accepted output on restart.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

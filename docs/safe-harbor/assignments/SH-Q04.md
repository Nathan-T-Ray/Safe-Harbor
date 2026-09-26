# Assignment: SH-Q04

Implement [SH-Q04: Exercise revision during active work](../tickets/SH-Q04.md) from `origin/main`.

Current publication-time status: **AVAILABLE — UNCLAIMED**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `e2e/safe_harbor/revision.py`. Coordinate shared interfaces and overlapping files. Dependencies: R09.

Work: Update a prepared evidence version while an affected task is running. Include two affected branches and an unrelated branch.

Accept only when: Stale acceptance fails, successors run, old results remain inspectable and unrelated work remains valid.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

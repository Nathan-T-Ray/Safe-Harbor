# Assignment: SH-Q06

Implement [SH-Q06: Exercise answer-key and tool-access isolation](../tickets/SH-Q06.md) from `origin/main`.

Current publication-time status: **AVAILABLE — UNCLAIMED**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `e2e/safe_harbor/isolation.py`. Coordinate shared interfaces and overlapping files. Dependencies: H05.

Work: Attempt evaluator-data access through the worker's available interfaces. Attempt unapproved tools and out-of-manifest artifacts.

Accept only when: Access is denied by actual boundaries, not merely by prompt instructions. The scored worker can still complete legitimate tasks.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

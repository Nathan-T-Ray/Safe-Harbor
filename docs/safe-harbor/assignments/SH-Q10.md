# Assignment: SH-Q10

Implement [SH-Q10: Exercise bounded context over accumulated history](../tickets/SH-Q10.md) from `origin/main`.

Current publication-time status: **AVAILABLE — UNCLAIMED**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `e2e/safe_harbor/history.py`. Coordinate shared interfaces and overlapping files. Dependencies: R08, R10, R12.

Work: Run enough legitimate intervening tasks or clearly labeled operational history to exercise retrieval of older evidence after restart.

Accept only when: The original objective and exact evidence remain accessible without loading the entire history. Report actual history/context sizes.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

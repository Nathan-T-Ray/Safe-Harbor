# Assignment: SH-H05

Implement [SH-H05: Build isolated experiment execution and scoring](../tickets/SH-H05.md) from `origin/main`.

Current publication-time status: **AVAILABLE — UNCLAIMED**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/evaluation/`. Coordinate shared interfaces and overlapping files. Dependencies: H03, H04, D09.

Work: Freeze model, settings, evidence, criteria, budgets, case assignments and cache policy. Keep evaluator-only keys inaccessible to workers. Score required outputs, not merely emitted claims.

Accept only when: Every assigned case appears, including failures. Arms cannot reuse one another's derived answers.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

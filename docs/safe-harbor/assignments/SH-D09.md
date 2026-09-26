# Assignment: SH-D09

Implement [SH-D09: Freeze cases, grouping and evaluation splits](../tickets/SH-D09.md) from `origin/main`.

Current publication-time status: **AVAILABLE — UNCLAIMED**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/evaluation/cases.py`, `data/safe_harbor/evaluator/splits.json`. Coordinate shared interfaces and overlapping files. Dependencies: D08.

Work: Target twelve audit cases, provisionally four development, four validation and four final. Keep related loci/scenario variants grouped; use a smaller feasible split if necessary.

Accept only when: Case definitions and split hashes are frozen before model comparisons. Disclose their shared-source nature.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

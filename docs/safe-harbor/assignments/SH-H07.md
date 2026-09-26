# Assignment: SH-H07

Implement [SH-H07: Apply promotion rules and reuse the selected version](../tickets/SH-H07.md) from `origin/main`.

Current publication-time status: **AVAILABLE — UNCLAIMED**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/evaluation/promotion.py`. Coordinate shared interfaces and overlapping files. Dependencies: H06.

Work: Use validation cases for selection. Require no correctness, support or coverage regression, plus a predefined measurable benefit. Preserve rejection when the change fails.

Accept only when: The decision is reproducible and a subsequent run uses the selected saved harness. Final evaluation remains outside selection.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

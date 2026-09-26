# Assignment: SH-R12

Implement [SH-R12: Export complete, replayable investigations](../tickets/SH-R12.md) from `origin/main`.

Current publication-time status: **AVAILABLE — UNCLAIMED**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/runtime/export.py`. Coordinate shared interfaces and overlapping files. Dependencies: R03, R09, R11.

Work: Export manifests, immutable evidence, tasks, events, assessments, harness references and measured usage. Include the assets needed for the selected demonstration views.

Accept only when: A fresh client reconstructs the run and can inspect historical evidence without relying on the original worker’s memory.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

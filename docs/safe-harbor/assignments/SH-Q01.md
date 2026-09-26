# Assignment: SH-Q01

Implement [SH-Q01: Run the first real candidate end to end](../tickets/SH-Q01.md) from `origin/main`.

Current publication-time status: **AVAILABLE — UNCLAIMED**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `e2e/safe_harbor/`, `artifacts/manifests/`. Coordinate shared interfaces and overlapping files. Dependencies: D08, R11, U06.

Work: Execute ingestion-backed tools, a real model assessment, MongoDB persistence and browser inspection.

Accept only when: The result can be independently checked from its exported inputs and calculations. This is the first complete vertical slice.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

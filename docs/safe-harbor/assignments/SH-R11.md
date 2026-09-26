# Assignment: SH-R11

Implement [SH-R11: Produce versioned assessments and shortlists](../tickets/SH-R11.md) from `origin/main`.

Current publication-time status: **AVAILABLE — UNCLAIMED**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/runtime/assessments.py`. Coordinate shared interfaces and overlapping files. Dependencies: R10, D01.

Work: Validate criterion-level outputs and evidence references. Aggregate using frozen rules. Separate current conclusions, unresolved questions and historical assessments.

Accept only when: A complete case and an insufficient-evidence case produce correct distinct states, visible in the API and export.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

# Assignment: SH-H06

Implement [SH-H06: Generate a real automatic harness proposal](../tickets/SH-H06.md) from `origin/main`.

Current publication-time status: **AVAILABLE — UNCLAIMED**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/harness/optimizer.py`. Coordinate shared interfaces and overlapping files. Dependencies: H02, H05.

Work: Give the optimizer development traces and resource measurements. Request one typed, bounded patch. Save its rationale and exact proposed content.

Accept only when: An actual model-generated structural proposal compiles and runs. Developer-authored winning presets do not count as invented architecture.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

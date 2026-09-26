# Assignment: SH-D07

Implement [SH-D07: Publish bounded worker tools](../tickets/SH-D07.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-data**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/science/tools.py`. Coordinate shared interfaces and overlapping files. Dependencies: D05, D06, F02.

Work: Expose typed candidate inspection, evidence listing, table slices, expression comparison, control overlap and gene-proximity tools. Assessment submission is a validated proposal to the runtime.

Accept only when: Tools accept scoped IDs, return bounded results and reject arbitrary URLs, paths and unknown artifacts.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

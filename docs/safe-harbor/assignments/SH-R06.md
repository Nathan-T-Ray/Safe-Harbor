# Assignment: SH-R06

Implement [SH-R06: Build genuine and deterministic execution adapters](../tickets/SH-R06.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-runtime**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/runtime/worker.py`. Coordinate shared interfaces and overlapping files. Dependencies: R05, D07.

Work: Support the actual model provider and a clearly labeled deterministic adapter for operational E2Es. Enforce role tool allowlists and record attempts, inputs, outputs and usage.

Accept only when: One actual model investigation calls a real genomic tool; prohibited tool requests fail at the interface boundary.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

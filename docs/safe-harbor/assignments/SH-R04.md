# Assignment: SH-R04

Implement [SH-R04: Build the typed DAG compiler](../tickets/SH-R04.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-runtime**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/safe_harbor/runtime/compiler.py`. Coordinate shared interfaces and overlapping files. Dependencies: F02, D07.

Work: Validate node kinds, dependency references, tools, output references, acyclicity and size limits. Use standard topological sorting. Validate complete proposed plans before dispatch.

Accept only when: Invalid plans fail before work begins and valid independent branches can share upstream evidence.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

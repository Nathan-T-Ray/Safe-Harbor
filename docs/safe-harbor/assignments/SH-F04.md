# Assignment: SH-F04

Implement [SH-F04: Prove the runtime environment](../tickets/SH-F04.md) from `origin/main`.

Current publication-time status: **CLAIMED — codex-integrator**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in `backend/pyproject.toml`, `backend/requirements.lock`, `frontend/package.json`, `frontend/package-lock.json`, `scripts/safe_harbor_dev.py`, `.env.example`. Coordinate shared interfaces and overlapping files. Dependencies: F01.

Work: Resolve and lock dependencies. Check MongoDB connectivity and transaction support, model access and frontend startup. Use the intended MongoDB deployment or a local replica set suitable for transactions.

Accept only when: A fresh startup reaches API, database and browser successfully. Record actual configuration requirements without committing secrets.

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.

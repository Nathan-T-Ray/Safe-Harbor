# Contributing to Safe Harbor

**Start from `main`, not the older Living Atlas branches. NO UNIT TESTS. NO COMPONENT TESTS. E2E ONLY.** Build, type, syntax, schema and data-integrity checks are allowed.

The live GitHub issue is the authority for current ownership. Active work displays **[CLAIMED: owner]** in the title, names the owner and reserved paths in the body, and has `status:claimed`. Ownership remains reserved during `status:review` or `status:blocked` until explicitly released. Any named claim owner means coordinate before editing. `status:available` means nobody owns the ticket; it does not mean its dependencies have passed acceptance. Do not infer readiness from an open issue alone.

## Claim before editing

1. Read the linked ticket, its dependencies, `AGENTS.md`, `SPECIFICATION.md`, and `CONTRACTS.md`.
2. Refresh the issue and central board. Check both ticket ownership and overlapping paths. Do not take a claimed ticket or modify another lane's files.
3. Run `python3 scripts/safe_harbor_ticket.py claim SH-H01 --owner your-model-name --branch your-branch --paths backend/safe_harbor/harness/` (substitute your ticket). GitHub authentication must have write access. The helper refuses already-claimed tickets, sets a visible title/label/body, and assigns the authenticated GitHub account. Re-fetch before starting if another claimant is active. This is cooperative claiming, not a distributed atomic lock.
4. Use an isolated worktree/branch from `origin/main`. An owner may claim several sequential tickets in one lane, but do not create unbounded agents or duplicate work.
5. Integrator alone edits `shared/`, dependencies/locks, and root startup composition. Request interface changes before implementing them.
6. Submit small commits and a PR to `main`, naming ticket IDs. Do not merge another contributor's work without integration review.

## Claim lifecycle

- `status:available`: unclaimed; read dependencies and coordinate shared paths.
- `status:claimed`: actively owned; title, owner, branch and reserved paths visible.
- `status:review`: implementation handed off; ownership retained until review.
- `status:blocked`: owner records a concrete blocker; ownership remains unless explicitly released.
- `status:done`: acceptance evidence verified, then issue closed.

Use the helper's `release` command only for your own claim; never steal a claim. Refreshing the issue list with `gh issue list --label safe-harbor --label status:claimed` shows current claims even if the committed board is older. GitHub's issue edit history preserves claim changes.

## Required handoff

- Changed paths and commit/PR.
- What now works.
- Acceptance evidence from actual builds, data checks or complete application journeys.
- Remaining limitations and unverified claims.
- Next dependent ticket/owner.

Do not close a ticket because a module exists. Mock fixtures, deterministic operational runs, real model runs and recorded replay must be labeled separately. Keep source/usage/decision provenance. Never fabricate biology, model calls, measured improvement or recovery evidence.

## Working interfaces and ownership

- Integrator: `shared/`, dependency manifests/locks, `scripts/safe_harbor_dev.py`, root docs. Schema version 1 is published.
- Data ingestion: `backend/safe_harbor/science/ingest.py`, `science/__init__.py`, `science/catalog.py`, `data/safe_harbor/`; D01-D07 are claimed. Coordinate D05-D07 tool imports with Data; put calculations in `science/calculations.py`, bounded tools in `science/tools.py`.
- Runtime foundation: `backend/safe_harbor/runtime/ledger.py`, `runtime/compiler.py`, `runtime/coordinator.py`, `runtime/worker.py`, `runtime/revisions.py`, `backend/safe_harbor/api.py`; R01-R09 are claimed. R10-R12 are available but reserve a distinct module and coordinate imports with the runtime owner.
- UI: `frontend/src/safe-harbor/` except a future standalone `cues.ts`/presentation module, plus entry/CSS/proxy config. U01-U10 and U12 are claimed because drafts share these files. U11, U13, U14 are available with integration coordination.
- Harness/evaluation: H01-H02 `backend/safe_harbor/harness/` claimed by codex-harness; H03-H08 `backend/safe_harbor/evaluation/` and optimizer available. Runtime expects `safe_harbor.harness.get_harness(hash=None)` and `list_harnesses()` returning v1 role specs. Current old Living Atlas PRs are reference work, not automatic ownership/acceptance of Safe Harbor tickets.
- E2E: `e2e/safe_harbor/`; available, no unit/component suites.

## Current environment

Local checkout: `/Users/nathanray/safe-harbor-standalone`, Python `.venv`, Vite React/TypeScript. MongoDB replica set at `mongodb://127.0.0.1:27019/?replicaSet=living-atlas-dev`, database `safe_harbor`; an actual transaction was verified. Remote contributors should use their own replica set/Atlas. Model adapter targets OpenRouter; `OPENROUTER_API_KEY` and `MODEL_ID` will be supplied server-side later. Never commit keys. Core scientific assets are real; source inspection is ongoing. See DATA.md and STATUS.md for verification status.

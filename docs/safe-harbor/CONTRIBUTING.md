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
- Runtime: `backend/safe_harbor/runtime/` and `backend/safe_harbor/api.py`; R01–R12 are claimed by codex-runtime, with R10–R12 currently being verified.
- UI: `frontend/src/safe-harbor/` except a future standalone `cues.ts`/presentation module, plus entry/CSS/proxy config. U01-U10 and U12 are claimed because drafts share these files. U11, U13, U14 are available with integration coordination.
- Harness/evaluation: H01–H02 and H06–H08 claimed by codex-harness (`harness/`, `evaluation/promotion.py`, `evaluation/report.py`). H03–H05 claimed by codex-evaluation (`evaluation/baselines.py`, `runner.py`, `scoring.py`). Integrator owns independent D08–D09 references/cases. Coordinate module imports across these owners.
- E2E: `e2e/safe_harbor/`; claim a specific journey/file before editing. Q08 replay integrity is claimed by codex-integrator. Runtime owns its existing process/revision E2E scripts. No unit/component suites.

## Current environment

Local checkout: `/Users/nathanray/safe-harbor-standalone`, Python `.venv`, Vite React/TypeScript. Dedicated MongoDB replica set at `mongodb://127.0.0.1:27021/?replicaSet=safe-harbor-dev`, database `safe_harbor`; transactions and actual process recovery were exercised. Remote contributors should use their own replica set/Atlas. Model adapter targets OpenRouter; configure `OPENROUTER_API_KEY` and `MODEL_ID` in ignored server-side `.env`. Never commit keys. Core scientific assets are real, with 15 hashed source assets and verified coordinates/reference bases. See DATA.md and STATUS.md for acceptance evidence and limitations.

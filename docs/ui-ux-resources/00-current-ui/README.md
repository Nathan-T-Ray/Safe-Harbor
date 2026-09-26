# 00 — Current Safe Harbor UI: map, constraints, known issues

This is a map of `frontend/` as of 2026-09-26. Read it **before** you change any UI file. It was built by reading the source and grepping `e2e/safe_harbor/*.mjs`. Line numbers refer to the minified sources and will drift.

## Stack & commands
- React 19.3, `@xyflow/react` 12.12.0, Vite 8.3, TypeScript 7.0, Playwright 1.63 (the library, not `@playwright/test`).
- No CSS framework, no router, no state library.
- `igv` ^3.8.9 is in `package.json` but **nothing imports it**. The genome viewer is hand-drawn SVG in `Genome.tsx`.
- Build and typecheck: `npm run build --prefix frontend` (runs `tsc --noEmit && vite build`).
- Full stack: `npm ci --prefix frontend`, then `.venv/bin/python scripts/safe_harbor_dev.py --local-mongo`. This serves the UI on :5174, the API on :8010 and Mongo on :27021 (see `docs/safe-harbor/STARTUP.md`). Run it in the background.
- The E2E scripts default to `SAFE_HARBOR_UI_URL=http://127.0.0.1:5181`, so **always set it explicitly**. The `npm run e2e` script points at a missing `browser.mjs`; run the individual scripts instead, e.g. `node e2e/safe_harbor/genome.mjs`.
- The Vite proxy forwards `/api` to `API_TARGET` (default `127.0.0.1:8010`) and strips the prefix.

## Rules (from `AGENTS.md` / `docs/safe-harbor/CONTRIBUTING.md`)
- **Testing:** E2E only. No unit or component tests. Build, type, lint and schema checks are fine.
- **Ownership:** the UI lane owns `frontend/src/`. `shared/contracts.ts`, dependency manifests and lockfiles belong to the integrator, so ask before adding or removing packages.
- **Tickets:** claim one with `scripts/safe_harbor_ticket.py claim` before editing. The handoff must list changed paths, what works, acceptance evidence, limitations and the next ticket.

## Domain constraints (never violate)
- Never label a locus as "safe". Keep `.scientific-footnote` and `.shp-footnote`.
- Show `screen_status` (pass/fail/incomplete), `evidence_status` (supported_for_endpoint/conflicting/unknown) and `freshness` (current/stale) as **three separate displays**. Do not merge them into one verdict colour.
- Missing required evidence means *incomplete*. Missing experimental evidence means *unknown*, not a negative result.
- Keep GRCh38 and the H1 hESC context visible. H9 is a different context. Candidates are *publication-derived*.
- Coordinates are stored 0-based half-open and displayed 1-based inclusive (`formatInterval`).
- Mode labels must stay distinct: MOCK FIXTURE, DETERMINISTIC OPERATIONAL, REAL MODEL, plus the separate LIVE / RECORDED REPLAY pill.
- Replay frames are rebuilt from events only. Never show later data in an earlier frame.
- No fabricated improvement. When a value is not known, say "No improvement is claimed", "Unknown" or "cost unreported".

## Component map (`frontend/src/safe-harbor/`)
| File | Renders | Notes |
|---|---|---|
| `App.tsx` | Whole page and all state: topbar, contextbar, mode notice, error banner, candidate rail, intro/progress, science grid (Genome + conclusion panel), Graph, record actions, Timeline, footer, drawers | Polls the catalog every 5 s until candidates load; global Escape handler; hard-coded run budget |
| `Genome.tsx` | `section.genome-panel`: breadcrumb (Genome/chr/Locus/Sequence), SVG karyogram, chromosome, locus and sequence strip | Fixed viewBox and px arithmetic |
| `Graph.tsx` | `section.graph-panel`: React Flow DAG (`TaskNode`, `EvidenceNode`), view toggles, shared-evidence list | Custom row layout; `fitView` with `minZoom .45` |
| `Inspector.tsx` | `aside.inspector-drawer[role=dialog]`: evidence and artifact cards, tables, raw JSON | Uses `useDialogFocus` |
| `Harness.tsx` | `aside.harness-drawer[role=dialog]`: experiments, comparison report | Polls every 1 s indefinitely |
| `Timeline.tsx` | `section.timeline`: play/reset/slider/next/speed/live, Follow camera | One minified line |
| `Presentation.tsx` + `presentation.css` | Sticky `.shp-bar`, camera story, dossier dialog | Adds `html.shp-presenting` |
| `cues.ts` | `deriveCues` and `useCameraFollow`: scroll-follow that already honours reduced motion | Extend it; do not duplicate |
| `record.ts` | `useRecord`: 1 s snapshot and event polling, replay reconstruction | Keeps polling even after a run completes |
| `dialogFocus.ts` | Tab trap and focus restore | |

## Styling system
- `styles.css` line 2 is a single line of about 19.5k characters.
- Only 5 CSS variables: `--panel #101c2d`, `--line #253349`, `--muted #97a8bf`, `--cyan #83e6d7`, `--amber #e9b774`. Body is `#dce5f3` on `#0a1220`. Everything else is raw hex (about 150 distinct colours).
- `presentation.css` duplicates the palette as `--shp-*`, and the values have drifted from the originals.
- Fonts: DM Sans (body) and Manrope (headings), loaded via a Google Fonts `@import`.
- Breakpoints are 1700, 1200, 960 and 650 px. There is also a `prefers-reduced-motion` block in both CSS files.

## Stable selectors: E2E depends on these, so do not rename or remove them
- **Classes (candidates, conclusion, status):** `.candidate-card .conclusion-text .mode-word .data-version .contextbar .pill .run-progress .run-status-notice .status-axes .conclusion-panel .panel-head .pill .endpoint .criteria-details`
- **Classes (genome):** `.reference-availability .genome-canvas` (and its `svg > rect`, `.marker`, `.marker circle`), `g.marker line .genome-breadcrumb button.active .track-heading .svg-gene .genome-footnote .sequence-strip .sequence-row code span .sequence-label .inside-candidate .sequence-controls span .hash-line`
- **Classes (timeline):** `.sequence-count .timeline .timeline-event`
- **Classes (graph):** `.graph-panel .task-node .task-state .task-failure .react-flow__node-task .react-flow__node[data-id] .stage-labels span/i .graph-footer span .shared-evidence-node .shared-evidence-edge .shared-evidence-record[data-artifact-id] .shared-evidence-records .notice [data-consumer-id]`
- **Classes (drawers, presentation, other):** `.inspector-drawer .artifact-id .notice.amber .experiment-controls .comparison-report .shp-preload.ready .shp-checks .bad .shp-assessments article .page-footer pre`
- **Accessible names (genome, timeline):** 'Genome zoom', 'Genome', 'Locus', 'Sequence', '← 50 bp', '50 bp →', 'Genome viewer', 'Replay event position', 'Reset replay to start', 'Play replay', 'Next meaningful event', 'Return live', 'Replay speed', 'Follow camera'
- **Accessible names (presentation):** 'Presentation', 'Reset presentation to start', 'Play presentation replay', 'Exit presentation', 'Dossier', 'Dossier at this commit', 'Close dossier', 'Download dossier JSON ↓'
- **Accessible names (inspector, run controls):** 'Evidence inspection', 'Close evidence inspector', /Inspect evidence/, /Start investigation/, 'Investigation execution mode', 'Open', 'Export saved record ↓', 'Saved experiment ID', /Harness evolution/, 'Expand task graph', 'Collapse task graph', 'Return to selected candidate'
- **Asserted text:** 'REAL MODEL', 'Ledger connected', 'No assessment has been committed in this record.', 'Exact inputs / numerical result', 'N accepted tasks', the `x / y` sequence counter
- Before renaming anything, run `grep -rn "<selector>" e2e/safe_harbor/`.

## Known issues (fixer backlog)
| Sev | Issue | Where | Guide |
|---|---|---|---|
| High | Minified CSS and JSX make diffs unreviewable. Reformat mechanically first, with no behaviour change. | `styles.css`, `App.tsx` L44/47, `Timeline.tsx` | 05/css-lint-and-analysis |
| High | Type is too small: 9–10 px text appears about 50 times, one rule is 8 px, and graph text shrinks further under fitView. Low-contrast muted labels. | `styles.css`, `presentation.css`, `Graph.tsx` | 02/03-typography, 02/02-dark-theme |
| High | Drawers are `aria-modal` but the page behind them is not `inert`. The scrim is a tab-stop, scroll is not locked, Harness has no `aria-labelledby`, and the Escape handler is global. | `Inspector.tsx`, `Harness.tsx`, `App.tsx` L52 | 02/05-dialog-drawer, 03/aria-patterns |
| High | Polling every 1 s never stops (complete runs, hidden tab, errors) and has no backoff, so the error banner flickers. | `record.ts` L36, `Harness.tsx` L39 | 02/04-state-patterns |
| Med | At ≤960 px the layout hides `.run-progress`, `.data-version` and the Presentation button, including budget and provenance information that honest reporting needs. | `styles.css` 960 rule | 04/dense-dashboard-layout |
| Med | Chromosome-zoom markers are mouse-only. | `Genome.tsx` L35 | 03/aria-patterns |
| Med | The Inspector tabbar has no tab semantics. | `Inspector.tsx` L12 | 03/aria-patterns |
| Med | `record.loading` is never shown, and "Retry record" does not retry the catalog. | `App.tsx` L43 | 02/04-state-patterns |
| Med | Selectors are defined more than once (`.eyebrow` ×3 etc.) and the palette is duplicated as `--shp-*`. | CSS | 05/css-lint-and-analysis |
| Med | The shared-evidence list repeats consumer chips on every record. Gene labels in the SVG can overlap. | `Graph.tsx` L41, `Genome.tsx` L36 | 04/react-flow-v12-dag-ux |
| Low | No `color-scheme: dark`. `theme-color` (`#10171b`) does not match the background. Two `h1`s on the page. Google Fonts `@import` blocks rendering. Unused `igv` dependency. | `styles.css`, `index.html`, `App.tsx` | 02/02-dark-theme |

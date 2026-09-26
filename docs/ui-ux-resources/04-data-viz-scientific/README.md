# 04 — Data-viz, scientific/genomics & node-graph UI resources

**Purpose:** a checked reading list for AI agents that fix or improve the Safe-Harbor frontend (`frontend/src/safe-harbor/*`: React 19.3, Vite 8, `@xyflow/react` 12.12.0, `igv` ^3.8.9). It covers the genome panel, the task/evidence DAG, the three-axis conclusion panel, the timeline/replay, the drawers and presentation mode.

Checked 2026-09-26: star counts, last push and license come from `gh api repos/{owner}/{repo}`. Every doc URL returned HTTP 200, except the Observable Plot site, which returned 429 (rate-limited). Its repo was checked instead.

> **Finding from the codebase (2026-09-26):** `igv` is listed in `frontend/package.json`, but nothing in `frontend/src` imports it. `Genome.tsx` only imports `useState`. Before assuming a live igv.js browser exists, read `distilled/igv-js-integration-notes.md`.

## Resource table

| Name | URL | Stars | Last push | License | What it gives an agent | Relevance |
|---|---|---|---|---|---|---|
| igv.js | https://github.com/igvteam/igv.js · docs https://igv.org/doc/igvjs/ | 735 | 2026-09-24 | MIT | `createBrowser`/`removeBrowser`, `search(locus)`, `locuschange` event, `visibilityChange()` for resize, `toSVG` | High |
| igv-webapp | https://github.com/igvteam/igv-webapp · live https://igv.org/app/ | 129 | 2026-09-25 | MIT | Reference UX for the locus box, genome picker and track menus around igv.js | Med |
| igv-reports | https://github.com/igvteam/igv-reports | 436 | 2026-09-02 | MIT | Pattern: a table of variants/regions where clicking a row moves igv.js to that locus. Matches our candidate rail | High |
| igv-notebook | https://github.com/igvteam/igv-notebook | 84 | 2025-02-07 | MIT | Small example of embedding igv.js in a host UI | Low |
| xyflow (React Flow) | https://github.com/xyflow/xyflow · https://reactflow.dev | 38,501 | 2026-09-24 | MIT | v12 API, custom nodes, `fitView`, a11y props, perf guidance | High |
| React Flow layouting guide | https://reactflow.dev/learn/layouting/layouting · examples `/examples/layout/dagre`, `/examples/layout/elkjs` | — | — | MIT (docs) | Compares dagre, d3-hierarchy, d3-force and ELK, with runnable examples | High |
| React Flow a11y / perf docs | https://reactflow.dev/learn/advanced-use/accessibility · `/performance` | — | — | — | `nodesFocusable`, `ariaLabelConfig`, `domAttributes`, memoization rules | High |
| dagre | https://github.com/dagrejs/dagre | 5,803 | 2026-08-08 | MIT | Fast synchronous layered layout for DAGs (`rankdir: 'LR'`) | High |
| elkjs | https://github.com/kieler/elkjs | 2,784 | 2026-09-17 | EPL-2.0 (GitHub shows NOASSERTION) | Async layered layout with ports, compound nodes and edge routing | Med |
| JBrowse 2 | https://github.com/GMOD/jbrowse-components · https://jbrowse.org/jb2/docs/ | 296 | 2026-09-26 | Apache-2.0 | Modern React genome-browser UX: multi-view, dark theming, session sharing | Med |
| UCSC Genome Browser (kent) | https://github.com/ucscGenomeBrowser/kent · help https://genome.ucsc.edu/goldenPath/help/hgTracksHelp.html | 278 | 2026-09-26 | custom (NOASSERTION) | The standard conventions for locus syntax, zoom ×3/×10 and track density modes | Med |
| Gosling.js | https://github.com/gosling-lang/gosling.js · https://gosling-lang.org/ | 195 | 2026-04-02 | MIT | Grammar-based genomics vis and semantic zoom ideas | Low |
| HiGlass | https://github.com/higlass/higlass · https://docs.higlass.io/ | 342 | 2026-06-17 | MIT | Linked views, synced zoom/locks between panels | Low |
| Fundamentals of Data Visualization (Wilke) | https://github.com/clauswilke/dataviz · https://clauswilke.com/dataviz/ | 3,535 | 2022-07-27 | CC BY-NC-ND (book), NOASSERTION on GitHub | Chapter "Visualizing uncertainty": error bars vs frequency framing; colour and redundancy chapters | High |
| Uncertainty Visualization (Padilla, Kay, Hullman 2022) | http://space.ucmerced.edu/Downloads/publications/Uncertainty_Visualization_Padilla_Kay_Hullman_2022.pdf | — | — | academic | Survey of techniques and the cognitive reasons they succeed or fail | High |
| Hypothetical Outcome Plots (Hullman et al. 2015) | https://idl.cs.washington.edu/files/2015-HOPs-PLOS.pdf | — | — | PLOS (CC BY) | Evidence that animated draws beat static error bars for comparisons | Low |
| ggdist | https://github.com/mjskay/ggdist · https://mjskay.github.io/ggdist/ | 882 | 2026-09-20 | GPL-3.0 | Vocabulary of interval/dots/gradient encodings (ideas only; R, GPL) | Low |
| uncertainty-examples | https://github.com/mjskay/uncertainty-examples | 113 | 2024-10-14 | none | Worked sketches of uncertainty encodings | Low |
| Observable Plot | https://github.com/observablehq/plot | 5,390 | 2026-09-01 | ISC | Lightweight SVG charts if a small inline chart is needed | Low |
| Tremor | https://github.com/tremorlabs/tremor · https://tremor.so/ | 3,635 | 2025-10-10 | Apache-2.0 | Dense dashboard components: KPI cards, badges, tracker bars | Med |
| Grafana dashboard best practices | https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/best-practices/ · Saga https://grafana.com/developers/saga/ | 76,929 (grafana/grafana) | 2026-09-26 | AGPL-3.0 (code; don't copy) | "Tell one story", reduce cognitive load, general-to-specific drill-down, avoid stacking | Med |
| awesome-dataviz | https://github.com/hal9ai/awesome-dataviz | 4,415 | 2024-01-26 | NOASSERTION | Index for finding more libraries | Low |
| vis-timeline | https://github.com/visjs/vis-timeline | 2,561 | 2026-09-25 | Apache-2.0/MIT dual (NOASSERTION) | Timeline UX reference: range window, zoom, current-time marker | Low |
| WAI-ARIA APG Slider (media seek example) | https://www.w3.org/WAI/ARIA/apg/patterns/slider/ | — | — | W3C | Keyboard contract and `aria-valuetext` for the replay scrubber | High |
| MDN prefers-reduced-motion | https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion | — | — | CC-BY-SA | Turning off follow-camera and playback animation for users who ask for less motion | Med |
| Trrack (provenance) | https://github.com/Trrack/trrackjs · https://apps.vdl.sci.utah.edu/trrack | 25 | 2026-04-09 | BSD-3-Clause | Provenance graph plus undo/replay model for interaction history | Med |
| W3C PROV overview | https://www.w3.org/TR/prov-overview/ | — | — | W3C | Entity/Activity/Agent vocabulary for evidence and audit-trail labels | Med |
| ColorBrewer | https://colorbrewer2.org/ | — | — | Apache-2.0 | Colour-blind-safe categorical and sequential palettes for status and tracks | Med |

## How a fixer agent should use these
1. Start with the file in `distilled/` that matches the panel you are touching:
   - `igv-js-integration-notes.md` — genome panel
   - `react-flow-v12-dag-ux.md` — graph
   - `communicating-uncertainty-and-status.md` — conclusion panel, badges, copy
   - `dense-dashboard-layout.md` — overall grid, rail, drawers, presentation mode
   - `timeline-replay-controls.md` — timeline, playback, follow camera, provenance
2. Treat the distilled files as design guidance. For exact API signatures, confirm against the pinned versions (`igv@3.8.9`, `@xyflow/react@12.12.0`). The docs sites follow the latest release.
3. The honesty rules in `communicating-uncertainty-and-status.md` come before any aesthetic suggestion from Tremor or Grafana.
4. Do not copy code from AGPL (Grafana) or GPL (ggdist) sources. MIT, ISC, Apache and BSD examples are fine to adapt, with attribution.
5. Adding a dependency (dagre, elkjs) changes `frontend/package.json`. Note it in your PR and keep bundle size in mind: dagre is small, elkjs is large and should be lazy-loaded.

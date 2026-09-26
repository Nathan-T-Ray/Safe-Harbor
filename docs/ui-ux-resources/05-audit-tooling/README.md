# 05 — UI audit, review & verification tooling

**Purpose.** A vetted shortlist of tools an AI fixer agent can run **headlessly** (Linux, Node 22, Playwright 1.63) to see, measure and verify the Safe Harbor UI (`frontend/`, React 19 + Vite 8 + TS 7, hand-written minified CSS in `frontend/src/safe-harbor/styles.css` and `presentation.css`).

**Policy reminder (AGENTS.md):** no unit tests, no component tests — **E2E only**. Build, type, lint, syntax and schema checks are fine. Every tool below is used either inside an E2E `.mjs` journey (like `e2e/safe_harbor/foundation.mjs`) or as a build/lint/analysis check. Do **not** add packages to `frontend/package.json` without the integrator; install throw-away tools into `/projects/sandbox/.uitools` (outside the repo; `/tmp` did not persist between shell calls in this sandbox) (see distilled files).

Metadata verified via `gh api repos/{owner}/{repo}` on 2026-09-26 (stars rounded as returned; "last push" = `pushed_at`).

| Name | URL | Stars | Last push | License | What it gives an agent | Relevance |
|---|---|---|---|---|---|---|
| Playwright (library, already installed) | https://github.com/microsoft/playwright | 96,706 | 2026-09-26 | Apache-2.0 | `page.screenshot` (fullPage, mask, `animations:'disabled'`, `style`), viewport/device emulation, `locator.ariaSnapshot()`, `page.coverage` CSS/JS coverage, console/pageerror capture | **High** |
| Playwright visual comparisons (`toHaveScreenshot`) | https://playwright.dev/docs/test-snapshots | (part of Playwright) | — | Apache-2.0 | Golden-image diffing via pixelmatch with `maxDiffPixels`, `stylePath`; needs `@playwright/test` runner — project uses bare library, so replicate with pixelmatch (see recipes) | Med |
| pixelmatch | https://github.com/mapbox/pixelmatch | 6,962 | 2026-09-15 | ISC | Tiny pixel-diff lib (the engine behind toHaveScreenshot); usable from a plain `.mjs` E2E script | **High** |
| pngjs | https://github.com/pngjs/pngjs | 743 | 2024-03-23 | MIT (NOASSERTION in API) | Decode/encode PNG buffers for pixelmatch | Med |
| Playwright MCP | https://github.com/microsoft/playwright-mcp | 37,591 | 2026-09-25 | Apache-2.0 | Agent-driven browsing via accessibility snapshots (no vision needed); `--headless`, `--caps vision` for coordinate/screenshot tools | **High** (if MCP host available) |
| Chrome DevTools MCP | https://github.com/ChromeDevTools/chrome-devtools-mcp | 52,632 | 2026-09-25 | Apache-2.0 | Agent access to DevTools: performance traces, network, console, screenshots | Med |
| agent-browser (Vercel Labs) | https://github.com/vercel-labs/agent-browser | 43,225 | 2026-09-24 | Apache-2.0 | CLI browser automation with snapshots/refs for agents (installed as a Kiro power here) | Med |
| OneRedOak claude-code-workflows — design-review | https://github.com/OneRedOak/claude-code-workflows/tree/main/design-review | 3,892 | 2025-09-14 | MIT | Phased design-review agent prompt (interaction → responsive 1440/768/375 → polish → a11y → robustness → code health → console) with Blocker/High/Medium/Nit triage | **High** (as checklist) |
| axe-core | https://github.com/dequelabs/axe-core | 7,559 | 2026-09-23 | MPL-2.0 | Automated WCAG rule engine; injectable into any page from an E2E script | **High** |
| @axe-core/playwright (axe-core-npm) | https://github.com/dequelabs/axe-core-npm | 725 | 2026-09-19 | MPL-2.0 | `AxeBuilder({page}).analyze()` wrapper for Playwright | **High** |
| pa11y | https://github.com/pa11y/pa11y | 4,558 | 2026-09-21 | LGPL-3.0 | CLI a11y runner (axe/htmlcs) with JSON output | Low |
| Lighthouse | https://github.com/GoogleChrome/lighthouse | 30,819 | 2026-09-20 | Apache-2.0 | Headless perf/a11y/best-practice audit, JSON output; can reuse Playwright's Chromium via `CHROME_PATH` | Med |
| Lighthouse CI | https://github.com/GoogleChrome/lighthouse-ci | 7,098 | 2026-03-27 | Apache-2.0 | `lhci autorun` with assertions/budgets over multiple runs | Low-Med |
| web-vitals | https://github.com/GoogleChrome/web-vitals | 8,626 | 2026-09-14 | Apache-2.0 | `onLCP/onINP/onCLS` (+ `/attribution` build); can be injected into a Playwright page as an ES module | Med |
| stylelint | https://github.com/stylelint/stylelint | 11,527 | 2026-09-25 | MIT | CSS linter (v16 dropped stylistic rules → safe on minified CSS); catches invalid values, duplicates, unknown props, specificity issues | **High** |
| stylelint-config-standard | https://github.com/stylelint/stylelint-config-standard | 1,418 | 2026-09-09 | MIT | Community-standard rule set | **High** |
| stylelint-order | https://github.com/hudochenkov/stylelint-order | 959 | 2026-05-08 | MIT | Property-order rules (optional) | Low |
| Prettier | https://github.com/prettier/prettier | 52,311 | 2026-09-24 | MIT | Pretty-print minified CSS **to a temp copy** for reading/diffing (do not reformat committed CSS without agreement) | Med |
| Project Wallace css-analyzer | https://github.com/projectwallace/css-analyzer | 366 | 2026-09-11 | MIT | `analyze(css)` → stats: unique colors, font sizes, z-indexes, specificity, `!important` counts, media queries — exposes design-token drift | **High** |
| csstree validator | https://github.com/csstree/validator | 73 | 2025-02-20 | MIT | Syntax/value validation against CSS spec grammar | Low |
| PurgeCSS | https://github.com/FullHuman/purgecss | 8,050 | 2026-08-20 | MIT | Static unused-selector detection (`--rejected`); risky with dynamic class names — use as a hint only | Med |
| UnCSS | https://github.com/uncss/uncss | 9,399 | 2024-06-18 | MIT | Older jsdom-based unused CSS finder; stale | Low |
| Playwright CSS coverage (`page.coverage.startCSSCoverage`) | https://playwright.dev/docs/api/class-coverage | (part of Playwright) | — | Apache-2.0 | **Runtime** unused-CSS measurement across a real E2E journey; Chromium only; zero install | **High** |
| react-scan | https://github.com/aidenybai/react-scan | 21,857 | 2026-08-16 | MIT | Highlights unnecessary React re-renders; `scan()` API / script tag, visible in screenshots | Med |
| React (DevTools / `<Profiler>`) | https://github.com/facebook/react (redirects to react/react) | 250,753 | 2026-09-25 | MIT | `<Profiler onRender>` timings; DevTools profiler is GUI-only (low value headless) | Low |
| rollup-plugin-visualizer | https://github.com/btd/rollup-plugin-visualizer | 2,424 | 2026-08-14 | MIT | Treemap/`raw-data` JSON of the Vite bundle (documents Vite + Rolldown usage) | Med |
| vite-bundle-visualizer | https://github.com/KusStar/vite-bundle-visualizer | 456 | 2024-10-27 | MIT | Zero-config CLI wrapper around the visualizer; stale | Low |
| size-limit | https://github.com/ai/size-limit | 6,949 | 2026-09-25 | MIT | Bundle size budgets as a check | Low |
| knip | https://github.com/webpro-nl/knip | 12,349 | 2026-09-23 | ISC | Unused files/exports/deps in TS projects (dead UI code) | Low-Med |

Rejected / caveated:
- **lost-pixel** (https://github.com/lost-pixel/lost-pixel, 1,682★, MIT) — **archived** (API `archived: true`, last push 2026-04-22). Do not adopt.
- **reg-suit** (https://github.com/reg-viz/reg-suit, 1,297★, MIT, pushed 2026-09-24) and **BackstopJS** (https://github.com/garris/BackstopJS, 7,182★, MIT, pushed 2026-09-08) — capable visual-regression suites but add config/storage layers; pixelmatch inside existing E2E scripts is lighter for this repo. Low relevance.

## How a fixer agent should use these

1. **Read the loop first:** [`distilled/agent-ui-review-loop.md`](distilled/agent-ui-review-loop.md) — build → background `vite preview` → multi-width screenshots → critique → fix → re-shoot.
2. **Capture evidence with the existing Playwright library** using [`distilled/playwright-screenshot-recipes.md`](distilled/playwright-screenshot-recipes.md). Save PNG + JSON report under `artifacts/`, same as current E2E scripts.
3. **Lint and measure CSS** with [`distilled/css-lint-and-analysis.md`](distilled/css-lint-and-analysis.md) (tools installed in `/projects/sandbox/.uitools`, never in the repo).
4. **Check a11y and performance** with [`distilled/performance-checks.md`](distilled/performance-checks.md) (axe, web-vitals, Lighthouse, bundle size, react-scan).
5. Report only measured results (AGENTS.md: "honest measured results"): attach screenshot paths, diff pixel counts, axe violation counts, stylelint counts before/after.
6. Never run `npm run dev`/`preview` in the foreground — always background + readiness poll + kill.

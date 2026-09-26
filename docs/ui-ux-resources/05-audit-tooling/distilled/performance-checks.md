# Performance & accessibility checks (headless)

Sources: [web-vitals](https://github.com/GoogleChrome/web-vitals) · [Lighthouse](https://github.com/GoogleChrome/lighthouse) · [Lighthouse CI](https://github.com/GoogleChrome/lighthouse-ci) · [react-scan](https://github.com/aidenybai/react-scan) · [rollup-plugin-visualizer](https://github.com/btd/rollup-plugin-visualizer) · [axe-core-npm](https://github.com/dequelabs/axe-core-npm) · [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp)

Content was rephrased for compliance with licensing restrictions.

All checks run against the background `vite preview` server (see `agent-ui-review-loop.md`) or the build output. Report numbers as measured, with environment caveats (sandbox CPU, no throttling unless stated). `T=/projects/sandbox/.uitools`.

## 1. Accessibility — axe inside the E2E script
`new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze()` after each meaningful UI state (card selected, drawer open, sequence zoom). Record `violations[].id/impact/nodes.length`. Target: zero `critical`/`serious`. Axe cannot judge focus order or meaning — still do the keyboard walk from the review checklist.

## 2. Core Web Vitals in a Playwright page (no repo install)
web-vitals ships an ES module; load it as a local file into the page before navigation so metrics are captured from start:
```js
// npm i --prefix $T web-vitals
import { readFile } from 'node:fs/promises';
const wv = await readFile('/projects/sandbox/.uitools/node_modules/web-vitals/dist/web-vitals.iife.js','utf8');
await page.addInitScript(wv + `;window.__v=[];for(const f of ['onLCP','onCLS','onINP','onFCP','onTTFB'])webVitals[f](m=>window.__v.push({n:m.name,v:m.value,r:m.rating}),{reportAllChanges:true});`);
await page.goto(base); /* interact: click a card, open drawer (INP needs a real interaction) */
await page.evaluate(()=>document.visibilityState); await page.waitForTimeout(500);
const vitals = await page.evaluate(()=>window.__v);
```
`dist/web-vitals.iife.js` (and `web-vitals.attribution.iife.js`) verified present; the IIFE build exposes a global `webVitals`. LCP/CLS finalize on page hide; read with `reportAllChanges` or trigger a navigation away. CLS > 0.1 from late-loading panels is the most likely real finding in this app.

## 3. Lighthouse (headless, reuse Playwright's Chromium)
```bash
export CHROME_PATH=$(node -e "import('/projects/sandbox/Safe-Harbor/frontend/node_modules/playwright/index.mjs').then(p=>console.log(p.chromium.executablePath()))")
npx --prefix $T lighthouse http://127.0.0.1:4173 --chrome-flags="--headless=new --no-sandbox" \
  --only-categories=performance,accessibility,best-practices --output=json --output-path=$T/lh.json --quiet
node -e "const r=require('$T/lh.json');for(const[k,c]of Object.entries(r.categories))console.log(k,Math.round(c.score*100))"
```
Single runs are noisy; take the median of 3 before claiming an improvement. Lighthouse CI (`lhci autorun`) adds multi-run + assertions but needs a config file — only worth it if the integrator adopts it.

## 4. React render cost — react-scan
Injected at runtime, so no source change: `await page.addInitScript({path: '/projects/sandbox/.uitools/node_modules/react-scan/dist/auto.global.js'})` (file verified after `npm i --prefix $T react-scan`). It outlines components that re-render; screenshot during an interaction (e.g. dragging/zooming the graph in `Graph.tsx`, typing) to see render storms. Must load before React. For numbers, React's `<Profiler onRender>` gives `actualDuration`, but that requires a source edit — keep it out of commits. The React DevTools profiler is GUI-only; not useful headlessly.

## 5. Bundle size
- Quick: `cd frontend && npm run build` and read the size table Vite prints; `du -b dist/assets/*`.
- Treemap/JSON without touching `vite.config.ts`: write a scratch config in `$T` that imports the project config and adds `visualizer({filename:'$T/stats.html', template:'raw-data'})` (also supports `treemap`), then `npx vite build --config $T/vite.visualize.mjs --outDir $T/dist`. `igv` and `@xyflow/react` are the expected large chunks — lazy-loading the genome view is the typical win.

## 6. Deeper traces (optional)
If an MCP host provides Chrome DevTools MCP, it can record performance traces and surface long tasks/layout shifts for an agent. Treat as exploration; commit only reproducible script output.

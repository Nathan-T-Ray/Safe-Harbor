# Playwright screenshot recipes (bare library, `.mjs` E2E style)

Sources: [Playwright visual comparisons](https://playwright.dev/docs/test-snapshots) · [page.screenshot API](https://playwright.dev/docs/api/class-page#page-screenshot) · [Coverage API](https://playwright.dev/docs/api/class-coverage) · [pixelmatch](https://github.com/mapbox/pixelmatch) · [@axe-core/playwright](https://github.com/dequelabs/axe-core-npm)

Content was rephrased for compliance with licensing restrictions.

## Key facts
- `expect(page).toHaveScreenshot()` belongs to the `@playwright/test` runner, which this repo does **not** use (scripts import `frontend/node_modules/playwright/index.mjs` directly). Its engine is pixelmatch, so we reproduce it with pixelmatch + pngjs.
- Rendering varies with OS, fonts, headless mode and GPU — only compare images made in the same sandbox/browser build.
- Determinism options on `page.screenshot`: `animations:'disabled'` (finite animations jump to end, infinite ones reset), `caret:'hide'` (default), `mask:[locator]` (pink box over volatile regions, e.g. timestamps/run IDs), `style:'css…'` (inject CSS just for the shot), `scale:'css'` (1 px per CSS px).
- `page.coverage.startCSSCoverage()` is Chromium-only.

## Throw-away deps (outside the repo)
```bash
npm i --prefix /projects/sandbox/.uitools pixelmatch pngjs @axe-core/playwright >/dev/null
```
Import them with absolute paths so nothing is added to `frontend/package.json`.

## Recipe: multi-viewport capture + checks
Save as e.g. `/projects/sandbox/.uitools/ui-capture.mjs` (or, if a ticket asks for a committed journey, `e2e/safe_harbor/<name>.mjs`). Run from repo root: `SAFE_HARBOR_UI_URL=http://127.0.0.1:4173 OUT=artifacts/ui-review/SH-x/before node /projects/sandbox/.uitools/ui-capture.mjs`.
```js
import { chromium } from '/projects/sandbox/Safe-Harbor/frontend/node_modules/playwright/index.mjs';
import AxeBuilder from '/projects/sandbox/.uitools/node_modules/@axe-core/playwright/dist/index.mjs';
import { mkdir, writeFile } from 'node:fs/promises';
const base = process.env.SAFE_HARBOR_UI_URL ?? 'http://127.0.0.1:4173';
const out = process.env.OUT ?? 'artifacts/ui-review/latest';
const widths = [[1440,900],[1024,768],[390,844]];
await mkdir(out,{recursive:true});
const browser = await chromium.launch({headless:true});
const report = {base, mode:'deterministic_operational', mock_transport:false, viewports:[]};
try {
  for (const [width,height] of widths) {
    const context = await browser.newContext({viewport:{width,height}, reducedMotion:'reduce', colorScheme:'light'});
    const page = await context.newPage();
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    page.on('console', m => m.type()==='error' && errors.push(m.text()));
    await page.coverage.startCSSCoverage();
    await page.goto(base); await page.locator('.candidate-card').first().waitFor();
    await page.evaluate(() => document.fonts.ready);
    // --- drive the journey you are reviewing here (click card, open drawer, ...) ---
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    const axe = await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze();
    const aria = await page.locator('body').ariaSnapshot();
    const css = await page.coverage.stopCSSCoverage();
    const cssUsed = css.map(c => ({url:c.url, total:c.text.length, used:c.ranges.reduce((n,r)=>n+r.end-r.start,0)}));
    const shot = `${out}/w${width}.png`;
    await page.screenshot({path:shot, fullPage:true, animations:'disabled', scale:'css'});
    await writeFile(`${out}/w${width}.aria.yml`, aria);
    report.viewports.push({width,height,shot,horizontal_overflow_px:overflow,browser_errors:errors,
      axe_violations:axe.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.length})), css_coverage:cssUsed});
    await context.close();
  }
  await writeFile(`${out}/report.json`, JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report.viewports.map(v=>({w:v.width,overflow:v.horizontal_overflow_px,axe:v.axe_violations.length,errors:v.browser_errors.length}))));
} finally { await browser.close(); }
```
Notes: element-level shots → `await page.locator('.harness-drawer').screenshot({path})`. Keyboard/focus check → `await page.keyboard.press('Tab')` repeatedly and screenshot to verify a visible focus ring. Hover state → `locator.hover()` then shoot.

## Recipe: pixel diff before/after
```js
import pixelmatch from '/projects/sandbox/.uitools/node_modules/pixelmatch/index.js';
import { PNG } from '/projects/sandbox/.uitools/node_modules/pngjs/lib/png.js';
import { readFileSync, writeFileSync } from 'node:fs';
const [a,b,diffPath] = process.argv.slice(2);
const A = PNG.sync.read(readFileSync(a)), B = PNG.sync.read(readFileSync(b));
if (A.width!==B.width || A.height!==B.height) { console.log(JSON.stringify({sizeChanged:true,a:[A.width,A.height],b:[B.width,B.height]})); process.exit(0); }
const D = new PNG({width:A.width,height:A.height});
const changed = pixelmatch(A.data,B.data,D.data,A.width,A.height,{threshold:0.1});
writeFileSync(diffPath, PNG.sync.write(D));
console.log(JSON.stringify({changed, ratio:+(changed/(A.width*A.height)).toFixed(5), diff:diffPath}));
```
Full-page shots change height when layout changes — then compare viewport-only shots (`fullPage:false`) or element shots instead.

## Quick one-off CLI shot (no script)
`cd frontend && npx playwright screenshot --viewport-size=390,844 --full-page http://127.0.0.1:4173 /projects/sandbox/.uitools/m.png`

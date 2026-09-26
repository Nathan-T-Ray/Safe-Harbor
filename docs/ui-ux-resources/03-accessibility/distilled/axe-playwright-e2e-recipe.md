# Recipe: axe-core + keyboard checks inside a Safe Harbor E2E script

Sources: [@axe-core/playwright README](https://github.com/dequelabs/axe-core-npm/blob/develop/packages/playwright/README.md), [axe-core rule tags](https://github.com/dequelabs/axe-core/blob/develop/doc/API.md), [Playwright accessibility testing](https://playwright.dev/docs/accessibility-testing), [Playwright ARIA snapshots](https://playwright.dev/docs/aria-snapshots), [page.emulateMedia](https://playwright.dev/docs/api/class-page#page-emulate-media).

**Policy fit:** this is an E2E browser script, same style as `e2e/safe_harbor/*.mjs` (plain Node + `playwright` library, a `checks[]` array, JSON report). No `@playwright/test`, no unit/component tests.

## Install (frontend devDependency, so the relative import style keeps working)
```bash
cd frontend && npm install -D @axe-core/playwright@4.13.0   # MPL-2.0; version tracks axe-core major.minor
```
`@axe-core/playwright` versions mirror axe-core's major.minor (patches may add fixes/APIs, no breaking changes).

## API essentials
- `new AxeBuilder({ page })` — must receive a Playwright `Page`; auto-injects into all frames.
- `.withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa'])` — limit to WCAG A/AA rules (`wcag22aa` adds e.g. `target-size`).
- `.include(sel)` / `.exclude(sel)` — chain calls, one selector each (multi-element arrays aren't supported).
- `.disableRules(id|[ids])`, `.withRules(...)`, `.options(axe.RunOptions)` (options overrides withTags/withRules).
- `.analyze()` → `{ violations, passes, incomplete, inapplicable }`; each violation has `id`, `impact`, `help`, `helpUrl`, `nodes[].target`.

## Script: `e2e/safe_harbor/a11y.mjs` (template)
```js
// Accessibility E2E: axe scan of key states + keyboard/focus contracts + reduced motion.
// Usage: node a11y.mjs <ui-url> <run-id> <output-dir>
import { chromium } from '../../frontend/node_modules/playwright/index.mjs';
import { AxeBuilder } from '../../frontend/node_modules/@axe-core/playwright/dist/index.mjs';
import { mkdir, writeFile } from 'node:fs/promises';

const [ui, runId, output] = process.argv.slice(2);
const checks = [];
const check = (name, passed, evidence) => checks.push({ check: name, passed: Boolean(passed), evidence });
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

async function scan(page, label, { include, exclude = [] } = {}) {
  let b = new AxeBuilder({ page }).withTags(TAGS);
  if (include) b = b.include(include);
  for (const sel of ['.igv-container', ...exclude]) b = b.exclude(sel); // third-party canvas; document why
  const { violations } = await b.analyze();
  const serious = violations.filter(v => ['serious', 'critical'].includes(v.impact));
  check(`axe: no serious/critical violations — ${label}`, serious.length === 0,
    violations.map(v => ({ id: v.id, impact: v.impact, help: v.help, targets: v.nodes.slice(0, 5).map(n => n.target) })));
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 720 }, reducedMotion: 'reduce' });
const page = await context.newPage();
try {
  await page.goto(`${ui}/?run=${encodeURIComponent(runId)}`);
  await page.locator('.candidate-card').first().waitFor({ timeout: 20000 });
  await scan(page, 'dashboard loaded');

  // Toggle-button state is exposed
  const card = page.locator('.candidate-card').first();
  await card.focus();
  await page.keyboard.press('Enter');
  check('candidate toggle exposes aria-pressed=true', (await card.getAttribute('aria-pressed')) === 'true', {});

  // Drawer: open by keyboard, focus inside, Tab wraps, Escape closes, focus returns
  const opener = page.getByRole('button', { name: /inspect|evidence/i }).first(); // adjust to real label
  await opener.focus();
  await page.keyboard.press('Enter');
  const dialog = page.getByRole('dialog');
  await dialog.waitFor();
  check('dialog has accessible name', !!(await dialog.getAttribute('aria-label') || await dialog.getAttribute('aria-labelledby')), {});
  check('focus moved into dialog', await dialog.evaluate(d => d.contains(document.activeElement)), {});
  for (let i = 0; i < 25; i++) await page.keyboard.press('Tab');
  check('Tab stays inside dialog', await dialog.evaluate(d => d.contains(document.activeElement)), {});
  await scan(page, 'drawer open', { include: '[role="dialog"]' });
  await page.keyboard.press('Escape');
  await dialog.waitFor({ state: 'detached' });
  check('focus returned to opener', await opener.evaluate(el => el === document.activeElement), {});

  // Focus visible: focused element has a non-zero outline or box-shadow
  const ring = await page.evaluate(() => { const s = getComputedStyle(document.activeElement); return { outline: s.outlineStyle + ' ' + s.outlineWidth, shadow: s.boxShadow }; });
  check('focused control shows a focus indicator', ring.outline !== 'none 0px' || ring.shadow !== 'none', ring);

  // Timeline slider keyboard (if role=slider / input[type=range])
  const slider = page.getByRole('slider').first();
  if (await slider.count()) {
    await slider.focus();
    const before = await slider.getAttribute('aria-valuenow') ?? await slider.inputValue();
    await page.keyboard.press('ArrowLeft');
    const after = await slider.getAttribute('aria-valuenow') ?? await slider.inputValue();
    check('ArrowLeft changes timeline position', before !== after, { before, after, valuetext: await slider.getAttribute('aria-valuetext') });
  }

  // Status region exists before updates stream in
  check('a polite status region is present', (await page.locator('[role="status"], [aria-live="polite"]').count()) > 0, {});

  // Reduced motion honored
  const running = await page.evaluate(() => document.getAnimations().filter(a => a.playState === 'running').length);
  check('no running animations with reduced motion', running === 0, { running });

  // Optional structural snapshot for review evidence (Playwright >= 1.49)
  await writeFile(`${output}/aria-snapshot.yml`, await page.locator('body').ariaSnapshot()).catch(() => {});
} finally {
  await browser.close();
}
await mkdir(output, { recursive: true });
const passed = checks.every(c => c.passed);
await writeFile(`${output}/report.json`, JSON.stringify({ passed, checks }, null, 2));
process.exit(passed ? 0 : 1);
```

## Notes for fixers
- Import path: v4.13.0 `package.json` `exports["."].import` is `./dist/index.mjs` (verified via `npm view`), so the relative import above works after install. A bare `import { AxeBuilder } from '@axe-core/playwright'` works if the script runs with `frontend/` on the resolution path.
- Gate on `serious`/`critical` first; log `moderate`/`minor` in the report, then tighten.
- Scan **each state** (drawer open, presentation mode, dossier open, timeline recorded vs live) — axe only sees what's rendered.
- `color-contrast` results can be `incomplete` over gradients/semi-transparent scrims; review those manually with WebAIM.
- Never `disableRules` to make a check pass without a comment and a matching fix ticket.
- Also run once with `reducedMotion: 'no-preference'` so smooth behavior isn't regressed.
- Save a screenshot of any failing state to `artifacts/` like the other E2E manifests.

Content was rephrased for compliance with licensing restrictions.

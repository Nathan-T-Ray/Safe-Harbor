// SH-Q01 browser phase: the committed real-model assessment is what the screen shows.
// Invoked by first_real_candidate.py: node first_real_candidate_browser.mjs <ui> <expected-json> <output-dir>
import { chromium } from '../../frontend/node_modules/playwright/index.mjs';
const [ui, expectedJson, output] = process.argv.slice(2);
const expected = JSON.parse(expectedJson);
const checks = [];
const check = (name, passed, evidence) => checks.push({ check: name, passed: Boolean(passed), evidence });
const normalize = text => (text ?? '').replace(/\s+/g, ' ').trim();
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
try {
  await page.goto(`${ui}/?run=${encodeURIComponent(expected.run_id)}`);
  await page.locator('.candidate-card').first().waitFor({ timeout: 20000 });
  await page.waitForFunction(() => /commit [1-9]/.test(document.querySelector('.page-footer')?.textContent ?? ''), null, { timeout: 30000 });
  const card = page.locator('.candidate-card').first();
  await card.click();
  const mode = normalize(await page.locator('.mode-word').textContent());
  check('mode indicator shows REAL MODEL', mode === 'REAL MODEL', { mode });
  await page.locator('.conclusion-text').waitFor();
  const shown = normalize(await page.locator('.conclusion-text').textContent());
  check('displayed conclusion equals committed assessment conclusion', shown === normalize(expected.conclusion), { shown_prefix: shown.slice(0, 200) });
  const axes = normalize(await page.locator('.status-axes').textContent()).toLowerCase();
  check('displayed status axes match committed assessment', axes.includes(expected.screen_status.replaceAll('_', ' ')) && axes.includes(expected.evidence_status.replaceAll('_', ' ')), { axes });
  const revision = normalize(await page.locator('.conclusion-panel .panel-head .pill').textContent());
  check('displayed assessment revision matches', revision === `Revision ${expected.revision}`, { revision });
  const context = normalize(await page.locator('.contextbar').textContent());
  check('assembly and cell context are visible', context.includes('GRCh38') && context.includes('H1 human embryonic stem cells'), { context });
  await page.screenshot({ path: `${output}/conclusion.png` });
  await page.getByRole('button', { name: /Inspect evidence/ }).click();
  const drawer = page.getByRole('dialog', { name: 'Evidence inspection' });
  await drawer.waitFor();
  const drawerText = normalize(await drawer.textContent());
  check('evidence inspector exposes committed tool results', /expression comparison|control overlap|expression_comparison|control_overlap/i.test(drawerText), { drawer_prefix: drawerText.slice(0, 300) });
  await page.screenshot({ path: `${output}/evidence.png` });
  check('no page errors', errors.length === 0, { errors });
} catch (error) {
  check('browser journey completed', false, { error: String(error), errors });
} finally {
  await browser.close();
}
console.log(JSON.stringify({ checks }));

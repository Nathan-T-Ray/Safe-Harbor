// Actual browser → Vite proxy → FastAPI → MongoDB/catalog startup journey.
// No mocked API transport and no model/biological interpretation is asserted.
import { chromium } from '../../frontend/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
const base = process.env.SAFE_HARBOR_UI_URL ?? 'http://127.0.0.1:5175';
const started = Date.now();
const health = await (await fetch(`${base}/api/health`)).json();
assert.equal(health.authoritative_store, 'MongoDB');
const catalog = await (await fetch(`${base}/api/catalog`)).json();
assert.equal(catalog.candidates.length, 3);
const browser = await chromium.launch({headless:true});
const page = await browser.newPage({viewport:{width:1280,height:720}});
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const checks = [];
try {
  await page.goto(base);
  await page.locator('.candidate-card').first().waitFor();
  assert.equal(await page.locator('.candidate-card').count(),3);
  assert.match(await page.title(), /Safe Harbor/);
  for (const candidate of catalog.candidates) {
    await page.locator('.candidate-card').filter({hasText:candidate.name}).click();
    await page.getByRole('navigation',{name:'Genome zoom'}).getByRole('button',{name:'Genome',exact:true}).click();
    await page.getByRole('navigation',{name:'Genome zoom'}).getByRole('button',{name:candidate.chromosome,exact:true}).click();
    await page.getByRole('navigation',{name:'Genome zoom'}).getByRole('button',{name:'Locus',exact:true}).click();
    assert.match(await page.locator('.track-heading').textContent(), /GENCODE v36/);
    await page.getByRole('navigation',{name:'Genome zoom'}).getByRole('button',{name:'Sequence',exact:true}).click();
    const displayed = (await page.locator('.sequence-row code').allTextContents()).join('');
    const sequence = catalog.reference_assets[candidate.candidate_id].sequence;
    const expected = sequence.sequence.slice(candidate.start-20-sequence.start,candidate.start+80-sequence.start).toUpperCase();
    assert.equal(displayed,expected);
    assert.equal(displayed.length,100);
    checks.push({candidate_id:candidate.candidate_id,interval:[candidate.start,candidate.end],sequence_start:candidate.start-20,reference_bases_verified:100});
  }
  assert.equal(await page.evaluate(()=>document.body.scrollWidth),1280);
  assert.deepEqual(errors,[]);
  await mkdir('artifacts/manifests',{recursive:true});
  await page.screenshot({path:'artifacts/manifests/safe-harbor-foundation.png',fullPage:true});
  const report = {journey:'foundation browser/API/MongoDB + actual reference zoom',mode:'deterministic_operational',mock_transport:false,model_calls:0,biological_interpretation_tested:false,base,health,checks,browser_errors:errors,duration_ms:Date.now()-started};
  await writeFile('artifacts/manifests/safe-harbor-foundation.json',JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report,null,2));
} finally { await browser.close(); }

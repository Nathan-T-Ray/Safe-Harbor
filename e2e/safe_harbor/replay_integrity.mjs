// Full browser + actual API/Mongo event replay; no mocked data/transport.
import {chromium} from '../../frontend/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
const base=process.env.SAFE_HARBOR_UI_URL??'http://127.0.0.1:5176';
const run=process.env.SAFE_HARBOR_RUN_ID??'run-61c1f8d4a138477abc0a5dfe20ce9342';
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1280,height:720}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
try {
  await page.goto(`${base}/?run=${encodeURIComponent(run)}`);
  await page.getByText('Ledger connected',{exact:true}).waitFor();
  await page.locator('.run-progress').getByText('18 accepted tasks',{exact:true}).waitFor();
  const checks=await page.evaluate(async run=>{
    const {reconstruct}=await import('/src/safe-harbor/record.ts');
    const records=[];let after=0,more=true;
    while(more){const p=await (await fetch(`/api/runs/${run}/events?after_sequence=${after}`)).json();records.push(...p.events);after=records.at(-1)?.sequence??0;more=p.has_more;}
    const canonical=value=>JSON.stringify(value,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b))):v);
    const sorted=(rows,key)=>[...rows].sort((a,b)=>String(a[key]).localeCompare(String(b[key])));
    const checks=[];
    for(const sequence of [1,Math.floor(after/2),after,1,after]){
      const rebuilt=reconstruct(records,sequence);
      const snap=await (await fetch(`/api/runs/${run}/snapshot?through_sequence=${sequence}`)).json();
      const mismatches=[];
      if(canonical(rebuilt.run)!==canonical(snap.run))mismatches.push('run');
      for(const [field,key] of [['candidates','candidate_id'],['tasks','task_id'],['assessments','assessment_id'],['artifacts','artifact_id'],['harness_versions','harness_hash'],['evaluations','evaluation_id']]){
        if(canonical(sorted(rebuilt[field],key))!==canonical(sorted(snap[field],key)))mismatches.push(field);
      }
      checks.push({sequence,entities_match:mismatches.length===0,mismatches,assessment_count:rebuilt.assessments.length,artifact_count:rebuilt.artifacts.length});
    }
    return checks;
  },run);
  assert(checks.every(c=>c.entities_match),JSON.stringify(checks));
  const slider=page.getByRole('slider',{name:'Replay event position'});
  await slider.fill('0');
  assert.equal(await page.locator('.run-progress').textContent().then(t=>t.includes('18 accepted tasks')),false);
  assert.match(await page.locator('.conclusion-text').textContent(),/unresolved/i);
  await slider.fill('1');
  assert.match(await page.locator('.conclusion-text').textContent(),/unresolved/i);
  await page.getByRole('button',{name:'Return live',exact:true}).click();
  await page.locator('.run-progress').getByText('18 accepted tasks',{exact:true}).waitFor();
  assert.deepEqual(errors,[]);
  const report={mode:'recorded_replay_of_deterministic_operational_run',mock_transport:false,run_id:run,checks,backward_seek_hides_final_assessment:true,browser_errors:errors};
  await writeFile('artifacts/manifests/replay-integrity.json',JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report,null,2));
}finally{await browser.close();}

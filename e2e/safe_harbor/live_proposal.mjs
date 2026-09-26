// Read-only actual-browser check: saved experiment state drives the live proposal drawer.
import {chromium} from '../../frontend/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
const base=process.env.SAFE_HARBOR_UI_URL??'http://127.0.0.1:5176';
const experimentId=process.env.SAFE_HARBOR_EXPERIMENT_ID??'experiment-a879d0fa4f5e499b89a43ed8b7f7f400';
const output=process.env.SAFE_HARBOR_PROPOSAL_OUTPUT??'artifacts/safe_harbor/live-proposal-e2e';
const word=value=>String(value??'').replaceAll('_',' ');
await mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1280,height:720}});
const errors=[],writes=[],records=[];
page.on('pageerror',error=>errors.push(error.message));
page.on('request',request=>{if(!['GET','HEAD'].includes(request.method()))writes.push(`${request.method()} ${request.url()}`);});
page.on('response',async response=>{if(response.url().endsWith(`/api/experiments/${experimentId}`)&&response.ok())records.push(await response.json());});
try{
  await page.goto(`${base}/?run=run-1c38545496844fcb858df0892a3df064`);
  await page.getByRole('button',{name:/Harness evolution/}).click();
  const drawer=page.getByRole('dialog',{name:'Harness evolution'});
  await drawer.getByRole('textbox',{name:'Saved experiment ID'}).fill(experimentId);
  await drawer.getByRole('button',{name:'Open',exact:true}).click();
  const section=drawer.getByRole('region',{name:'Live harness proposal'});
  await section.waitFor();
  while(!records.length)await page.waitForTimeout(50);
  await page.waitForTimeout(100);
  const saved=records.at(-1),optimizer=saved.optimizer??{},promotion=saved.promotion??{};
  const h1Runs=saved.results.filter(row=>row.arm==='H1'&&typeof row.run_id==='string'&&row.run_id.length);
  const compiled=optimizer.status==='candidate_ready'&&typeof optimizer.candidate_hash==='string';
  const expectedExecution=h1Runs.length?'H1 run recorded — inspect its execution':compiled?'Compiled, execution pending':'No executable H1 recorded';
  assert.equal(await section.locator('.proposal-execution').textContent(),expectedExecution);
  assert.equal(await section.locator('.proposal-selection').textContent(),Object.keys(promotion).length?`Saved selection decision: ${word(promotion.status)}`:'Validation / promotion pending — no saved decision.');
  if(typeof optimizer.rationale==='string')assert.equal(await section.locator('.proposal-rationale').textContent(),optimizer.rationale);
  assert.equal(await section.locator('.patch-list > li').count(),optimizer.patch?.operations?.length??0);
  const shown=await section.getByRole('table',{name:'Live assigned case results'}).locator('tbody tr').evaluateAll(rows=>rows.map(row=>({case:row.cells[0].innerText.split('\n')[0],arm:row.cells[1].textContent,status:row.cells[2].textContent,href:row.cells[3].querySelector('a')?.getAttribute('href')??null})));
  assert.equal(shown.length,saved.results.length);
  for(const item of shown){const original=saved.results.find(r=>r.arm===item.arm&&r.case_id===item.case);assert.ok(original);assert.equal(item.status,word(original.status));assert.equal(item.href,original.run_id?`/?run=${encodeURIComponent(original.run_id)}`:null);}
  await section.scrollIntoViewIfNeeded();
  await page.screenshot({path:`${output}/saved-proposal.png`});
  // Verify the existing one-second GET polling remains active; this dispatches no experiment.
  const previous=records.length;await page.waitForTimeout(1200);assert.ok(records.length>previous);
  assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
  const report={passed:true,mode:'read_only_actual_experiment_browser',experiment_id:experimentId,saved_status:saved.status,saved_updated_at:saved.updated_at,optimizer_status:optimizer.status??null,operations_shown:optimizer.patch?.operations?.length??0,exact_rationale_shown:typeof optimizer.rationale==='string',execution_label:expectedExecution,recorded_h1_run_ids:h1Runs.map(r=>r.run_id),promotion_status:promotion.status??null,all_assigned_rows:shown.length,recorded_run_links:shown.filter(r=>r.href).length,polling_verified:true,model_calls_by_inspection:0,ledger_writes:0,browser_errors:errors,limitations:['This verifies only the actual saved phase observed during inspection; later execution or selection is not inferred.','No synthetic evaluation metrics or mock proposal were supplied to the browser.']};
  await writeFile(`${output}/report.json`,JSON.stringify(report,null,2)+'\n');
  await writeFile(`${output}/observed-experiment.json`,JSON.stringify(saved,null,2)+'\n');
  console.log(JSON.stringify(report));
}catch(error){await page.screenshot({path:`${output}/failure.png`}).catch(()=>{});await writeFile(`${output}/report.json`,JSON.stringify({passed:false,experiment_id:experimentId,error:String(error.stack??error),errors,writes},null,2)+'\n');throw error;}finally{await browser.close();}

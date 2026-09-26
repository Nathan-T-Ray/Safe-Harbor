// Actual saved comparison -> browser -> exact report. GET only; no inference.
// A pending report is recorded as pending, never as a passing comparison.
import {chromium} from '../../frontend/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';

const base=process.env.SAFE_HARBOR_UI_URL??'http://127.0.0.1:5176';
const experimentId=process.env.SAFE_HARBOR_EXPERIMENT_ID??'experiment-a879d0fa4f5e499b89a43ed8b7f7f400';
const output=process.env.SAFE_HARBOR_FINAL_REPORT_OUTPUT??'artifacts/safe_harbor/final-comparison-browser';
const get=async path=>{const response=await fetch(`${base}/api${path}`);assert.ok(response.ok,`${path}: ${response.status}`);return response.json();};
const numeric=value=>typeof value==='number'?value.toLocaleString('en-US',{maximumFractionDigits:4}):'Unknown';
const money=value=>typeof value==='number'?`$${value.toFixed(6)}`:'Unknown';
const answer=score=>score?.completed===true&&score?.support_ok===true?'Complete · supported':typeof score?.completed==='boolean'?`${score.completed?'Complete':'Incomplete'} · ${score.support_ok===true?'supported':'support failed'}`:'Evaluation pending';
const save=async value=>writeFile(`${output}/report.json`,JSON.stringify(value,null,2)+'\n');
await mkdir(output,{recursive:true});
const experiment=await get(`/experiments/${experimentId}`);
if(experiment.status!=='complete'||!experiment.report||!experiment.report_attachment) {
  const pending={status:'pending',passed:null,experiment_id:experimentId,observed_experiment_status:experiment.status,observed_at:new Date().toISOString(),report_available:!!experiment.report,report_attached:!!experiment.report_attachment,case_statuses:experiment.results.reduce((acc,row)=>(acc[row.status]=(acc[row.status]??0)+1,acc),{}),reason:'Awaiting the genuine completed report and its committed run attachment. No browser/report pass is claimed.',model_calls:0,ledger_writes:0};
  await writeFile(`${output}/pending.json`,JSON.stringify(pending,null,2)+'\n');
  console.log(JSON.stringify(pending));
  process.exit(0);
}
const report=experiment.report,runId=experiment.report_attachment.run_id;
assert.equal(experiment.mode,'real_model');assert.equal(report.mode,'real_model');
assert.equal(report.case_results.length,24);assert.equal(experiment.results.length,24);
assert.deepEqual(report.case_results,experiment.results);
assert.equal(report.promotion.status,'rejected');assert.equal(report.model_improvement_claim,false);assert.equal(report.cost_win_claim,false);
const exported=await get(`/runs/${runId}/export`);
const attached=exported.snapshot.evaluations.find(e=>e.type==='harness_comparison_report'&&e.experiment_id===experimentId);
assert.ok(attached);assert.deepEqual(attached.report,report);
const event=exported.events.find(e=>e.sequence===experiment.report_attachment.sequence);
assert.equal(event.cause,'experiment.reported');
assert.deepEqual(event.upserts.evaluations.find(e=>e.evaluation_id===attached.evaluation_id).report,report);
assert.equal(exported.snapshot.run.harness_hash,report.promotion.selected_harness_hash);

const checks=[],errors=[],writes=[];
const pass=(check,details={})=>checks.push({check,passed:true,...details});
pass('Final report is committed with the selected-version run and matches the saved experiment',{run_id:runId,report_sequence:event.sequence});
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1440,height:900},locale:'en-US',reducedMotion:'reduce'});
page.on('pageerror',error=>errors.push(error.message));
page.on('request',request=>{if(!['GET','HEAD'].includes(request.method()))writes.push(`${request.method()} ${request.url()}`);});
try {
  await page.goto(`${base}/?run=${runId}`);
  await page.locator('.mode-word,.mode-chip').getByText('REAL MODEL',{exact:true}).waitFor();
  const menu=page.locator('details.more-menu');
  if(await menu.count()&&!await menu.evaluate(node=>node.open))await menu.locator('summary').click();
  await page.getByRole('button',{name:/Harness evolution/}).click();
  const drawer=page.getByRole('dialog',{name:'Harness evolution'});
  await drawer.getByRole('textbox',{name:'Saved experiment ID'}).fill(experimentId);
  await drawer.getByRole('button',{name:'Open',exact:true}).click();
  const comparison=drawer.locator('.comparison-report').filter({has:page.getByRole('heading',{name:'Measured comparison',exact:true})});
  await comparison.waitFor();
  assert.equal(await comparison.count(),1);
  assert.equal(await drawer.getByRole('region',{name:'Live harness proposal'}).count(),0);
  assert.equal((await comparison.locator('.notice strong').textContent()).trim(),'rejected');
  for(const reason of report.promotion.reasons)assert.ok((await comparison.locator('.notice').textContent()).includes(reason));
  pass('Measured report replaces pending proposal and displays the saved rejection without an improvement claim');

  const arms=await comparison.locator('table').first().locator('tbody tr').evaluateAll(rows=>rows.map(row=>[...row.cells].map(cell=>cell.innerText)));
  assert.equal(arms.length,report.arms.length);
  for(const [i,arm] of report.arms.entries()) {
    assert.deepEqual(arms[i],[`${arm.split} · ${arm.arm}`,`${numeric(arm.required_correct)} / ${numeric(arm.required_total)}`,numeric(arm.unsupported_count),`${numeric(arm.completed_case_count)} / ${numeric(arm.assigned_case_count)}`,numeric(arm.usage.tokens),`${numeric(arm.usage.model_calls)} / ${numeric(arm.usage.tool_calls)}`,money(arm.usage.cost_usd)]);
  }
  pass('Every split/arm table matches required outputs, unsupported findings, validated completion and measured usage',{arm_rows:arms.length,rendered_rows:arms});
  await comparison.locator('.artifact-heading').scrollIntoViewIfNeeded();
  await page.screenshot({path:`${output}/01-saved-rejection-and-totals.png`});

  const overhead=comparison.locator('.comparison-overhead > div');
  assert.equal(await overhead.count(),2);
  assert.equal(await overhead.nth(0).locator('strong').textContent(),money(report.optimizer_overhead.cost_usd));
  assert.equal(await overhead.nth(0).locator('small').textContent(),`${numeric(report.optimizer_overhead.tokens)} tokens · ${numeric(report.optimizer_overhead.model_calls)} calls`);
  assert.equal(await overhead.nth(1).locator('strong').textContent(),money(report.combined_run_and_optimizer_usage.cost_usd));
  assert.equal(await overhead.nth(1).locator('small').textContent(),`${numeric(report.combined_run_and_optimizer_usage.tokens)} tokens · ${numeric(report.combined_run_and_optimizer_usage.duration_seconds)} s summed duration`);
  await comparison.getByText('Measured evaluator overhead',{exact:true}).click();
  const evaluationRecord=comparison.locator('details').filter({has:page.locator('summary').filter({hasText:/^Measured evaluator overhead$/})});
  assert.deepEqual(JSON.parse(await evaluationRecord.locator('pre').textContent()),report.evaluation_overhead);
  pass('Optimizer, combined totals and evaluator overhead remain distinct and equal the exact saved record');

  await comparison.getByText('All assigned case outcomes · including failures (24)',{exact:true}).click();
  const caseTable=comparison.locator('details.source-table table');
  const cases=await caseTable.locator('tbody tr').evaluateAll(rows=>rows.map(row=>({cells:[...row.cells].map(cell=>cell.innerText),href:row.querySelector('a')?.getAttribute('href')??null})));
  assert.equal(cases.length,24);
  const identities=new Set();
  for(const [i,item] of report.case_results.entries()) {
    identities.add(`${item.split}:${item.case_id}:${item.arm}`);
    const score=item.score;
    assert.deepEqual(cases[i].cells,[`${item.case_id}\n${item.split}`,item.arm,item.status,`${numeric(score?.required_correct)} / ${numeric(score?.required_total)}`,typeof score?.coverage==='number'?`${Math.round(score.coverage*100)}%`:'Unknown',answer(score),typeof item.run_id==='string'?'Inspect run ↗':'Not executed']);
    assert.equal(cases[i].href,typeof item.run_id==='string'?`/?run=${encodeURIComponent(item.run_id)}`:null);
  }
  assert.equal(identities.size,24);
  const firstH1=caseTable.locator('tr').filter({has:page.locator('a[href="/?run=run-5134783b07da40f2b6ac5c6b053bf901"]')});
  assert.match(await firstH1.textContent(),/18 \/ 18.*Incomplete · support failed/s);
  await firstH1.scrollIntoViewIfNeeded();await page.screenshot({path:`${output}/02-all-cases-with-failures.png`});
  pass('All 24 assigned outcomes and links match; workflow completion never hides failed support or completion',{case_rows:24,failed_workflows:report.case_results.filter(row=>row.status==='failed').length,invalid_answers:report.case_results.filter(row=>row.score?.completed!==true||row.score?.support_ok!==true).length});

  const patchOperations=comparison.locator('.patch-list .raw-record');
  assert.equal(await patchOperations.count(),report.optimizer.patch.operations.length);
  for(const [index,operation] of report.optimizer.patch.operations.entries()) {
    await patchOperations.nth(index).locator('summary').click();
    assert.deepEqual(JSON.parse(await patchOperations.nth(index).locator('pre').textContent()),operation);
  }
  await comparison.getByText('Exact comparison report, cases and usage',{exact:true}).click();
  const exact=comparison.locator('details.raw-record').filter({has:page.locator('summary').filter({hasText:/^Exact comparison report, cases and usage$/})});
  assert.deepEqual(JSON.parse(await exact.locator('pre').textContent()),report);
  pass('Exact executable patch and full inspectable report equal the saved API records');
  const after=await get(`/experiments/${experimentId}`);
  assert.deepEqual(after.report,report);assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
  pass('Browser makes no writes or model calls and leaves the final report unchanged');
  await save({status:'passed',passed:true,mode:'read_only_genuine_final_comparison_browser',observed_at:new Date().toISOString(),experiment_id:experimentId,comparison_manifest_hash:experiment.comparison_manifest_hash,run_id:runId,url:`${base}/?run=${runId}`,report_sequence:event.sequence,experiment_status:experiment.status,promotion_status:report.promotion.status,selected_harness_hash:report.promotion.selected_harness_hash,case_rows:24,model_improvement_claim:report.model_improvement_claim,cost_win_claim:report.cost_win_claim,model_calls:0,ledger_writes:0,checks,browser_errors:errors,limitations:['Rendering and record agreement do not independently establish scientific correctness.','The proposal was rejected; successful self-improvement is not demonstrated.','Reference answers have not been human-reviewed; source-sharing and split limitations remain in the exact report.','Per-arm duration totals are summed run durations, not elapsed experiment time.']});
  console.log(JSON.stringify({passed:true,checks:checks.length,cases:24,report:`${output}/report.json`}));
} catch(error) {
  await page.screenshot({path:`${output}/failure.png`}).catch(()=>{});
  await save({status:'failed',passed:false,experiment_id:experimentId,run_id:runId,checks,error:String(error.stack??error),errors,writes});
  throw error;
} finally {await browser.close();}

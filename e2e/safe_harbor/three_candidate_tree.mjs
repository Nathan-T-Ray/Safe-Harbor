// Inspect a user-authorized genuine three-candidate run. No dispatch or mutations.
import {chromium} from '../../frontend/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
const base=process.env.SAFE_HARBOR_UI_URL??'http://127.0.0.1:5176';
const runId=process.env.SAFE_HARBOR_RUN_ID;
assert.ok(runId,'SAFE_HARBOR_RUN_ID must identify the actual authorized three-candidate run');
const output=process.env.SAFE_HARBOR_TREE_OUTPUT??'artifacts/safe_harbor/three-candidate-tree';
const get=async path=>{const r=await fetch(`${base}/api${path}`);assert.ok(r.ok);return r.json();};
const initial=await get(`/runs/${runId}/snapshot`);
assert.equal(initial.run.mode,'real_model');assert.equal(initial.candidates.length,3);assert.equal(initial.tasks.length,18);
await mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1280,height:720},reducedMotion:'reduce'});
const errors=[],writes=[],checks=[];const pass=(check,details={})=>checks.push({check,passed:true,...details});
page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(!['GET','HEAD'].includes(r.method()))writes.push(r.method()+' '+r.url());});
try {
  await page.goto(`${base}/?run=${runId}`);const tree=page.getByRole('region',{name:'Agent tree chart',exact:true});
  await tree.locator('.tnode.l2').last().waitFor();
  assert.equal(await tree.locator('.tnode.l1').count(),3);assert.equal(await tree.locator('.tnode.l2').count(),18);
  const branches=await tree.locator('.tnode.l1').evaluateAll(nodes=>nodes.map(node=>({id:node.getAttribute('data-node'),position:node.style.transform,label:node.querySelector('.tlabel')?.textContent})));
  assert.equal(new Set(branches.map(b=>b.position)).size,3);
  assert.deepEqual(branches.map(b=>b.id).sort(),initial.candidates.map(c=>`b:${c.candidate_id}`).sort());
  pass('Three visible candidate branches and eighteen tasks come from the actual saved run',{branches});
  const expected=initial.tasks.flatMap(task=>task.depends_on.map(parent=>`${parent}=>${task.task_id}`)).sort();
  const actual=await tree.locator('line[data-dependency-source]').evaluateAll(lines=>lines.map(line=>`${line.dataset.dependencySource}=>${line.dataset.dependencyTarget}`).sort());
  assert.deepEqual(actual,expected);
  for(const candidate of initial.candidates) {
    const roots=initial.tasks.filter(task=>task.candidate_id===candidate.candidate_id&&!task.depends_on.length);
    assert.deepEqual(roots.map(task=>task.role_id).sort(),['inspect','screen']);
  }
  pass('All task-to-task lines are recorded dependencies; each candidate has independent screen and inspect roots',{dependency_edges:actual.length});
  for(const candidate of initial.candidates) {
    await page.getByRole('group',{name:'Candidates',exact:true}).getByRole('button',{name:candidate.name,exact:true}).click();
    assert.ok((await page.locator('.coordinate-footer').textContent()).includes(`[${candidate.start}, ${candidate.end})`));
    assert.match(await page.locator('.reference-availability').textContent(),/Frozen run assets/);
    assert.equal(await page.locator('.cand-chip[aria-pressed="true"]').textContent(),candidate.name);
  }
  pass('Each branch candidate selects its exact frozen genomic interval through the visible candidate control');
  const measurements=await tree.locator('.tlabel,.tsub').evaluateAll(nodes=>nodes.map(node=>{const svg=node.ownerSVGElement,scale=svg.getBoundingClientRect().width/svg.viewBox.baseVal.width;return{text:node.textContent,px:parseFloat(getComputedStyle(node).fontSize)*scale};}));
  await tree.screenshot({path:`${output}/actual-three-branch-tree.png`});await page.screenshot({path:`${output}/overview-1280.png`});
  const task=initial.tasks.find(t=>t.candidate_id===initial.candidates[0].candidate_id&&t.role_id==='screen');
  await tree.locator(`[data-node="a:${task.task_id}"]`).click();
  const inspector=page.getByRole('dialog',{name:'Evidence inspection'});await inspector.getByRole('button',{name:'Task & dependencies',exact:true}).click();
  await inspector.getByText('Exact saved task',{exact:true}).click();const inspected=JSON.parse(await inspector.locator('.raw-record[open] pre').textContent());
  assert.equal(inspected.task_id,task.task_id);assert.deepEqual(inspected.depends_on,task.depends_on);assert.equal(inspected.harness_hash,initial.run.harness_hash);
  await inspector.getByRole('button',{name:'Close evidence inspector'}).click();pass('A real tree node opens its exact task/dependencies and keeps candidate selection coordinated');
  const after=await get(`/runs/${runId}/snapshot`);
  const traces=after.artifacts.filter(a=>a.kind==='worker_trace'||a.kind==='worker_failure_trace');
  const responses=traces.reduce((sum,a)=>sum+(a.data.provider_responses?.length??0),0);
  assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
  pass('Read-only browser does not dispatch work or invent task/provider status',{observed_run_status:after.run.status,recorded_provider_responses:responses,accepted_traces:traces.length});
  await writeFile(`${output}/report.json`,JSON.stringify({passed:true,run_id:runId,mode:'real_model_run_read_only_browser',observed_watermark:after.through_sequence,observed_status:after.run.status,candidates:3,tasks:18,checks,effective_svg_text:measurements,minimum_svg_text_px:Math.min(...measurements.map(m=>m.px)),recorded_provider_responses:responses,model_calls_by_verification:0,ledger_writes:0,browser_errors:errors,limitations:['This proves visible genuine branches and their exact dependency topology, not scientific correctness or improvement.','The run can continue while this inspection takes place; execution figures are stated at the observed watermark.','No model response is claimed for an unfinished call; recorded traces are counted explicitly.']},null,2)+'\n');
  console.log(JSON.stringify({passed:true,checks:checks.length,provider_responses:responses,minimum_svg_text_px:Math.min(...measurements.map(m=>m.px)),report:`${output}/report.json`}));
}catch(error){await page.screenshot({path:`${output}/failure.png`}).catch(()=>{});await writeFile(`${output}/report.json`,JSON.stringify({passed:false,run_id:runId,checks,error:String(error.stack??error),errors,writes},null,2)+'\n');throw error;}finally{await browser.close();}

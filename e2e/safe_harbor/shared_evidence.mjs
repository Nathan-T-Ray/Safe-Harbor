// Browser -> real API -> MongoDB. Uses committed read sets, never mocked records.
import { chromium } from '../../frontend/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
const base=process.env.SAFE_HARBOR_UI_URL??'http://127.0.0.1:5178';
const runId=process.env.SAFE_HARBOR_RUN_ID??'run-cb40fb2ed6a14ddfaea3ff4557b32805';
const response=await fetch(`${base}/api/runs/${runId}/snapshot`);assert.ok(response.ok);
const snapshot=await response.json(),candidateId=snapshot.candidates[0].candidate_id;
const tasks=snapshot.tasks.filter(t=>!t.candidate_id||t.candidate_id===candidateId);
const shared=snapshot.artifacts.map(artifact=>({artifact,consumers:tasks.filter(task=>task.input_read_set.some(read=>read.kind==='artifact'&&[artifact.artifact_id,`artifact:${artifact.artifact_id}`].includes(read.key)&&[artifact.content_hash,artifact.revision].includes(read.version)))})).filter(item=>item.consumers.length>1).sort((a,b)=>a.artifact.created_at.localeCompare(b.artifact.created_at)||a.artifact.artifact_id.localeCompare(b.artifact.artifact_id));
assert.ok(shared.length>8,'Use an actual committed run with enough shared inputs to verify bounding.');
const displayed=shared.slice(0,8),browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1280,height:720},reducedMotion:'reduce'}),errors=[];
page.on('pageerror',error=>errors.push(error.message));
try{
 await page.goto(`${base}/?run=${runId}`);
 await page.getByRole('button',{name:`Show shared evidence (${shared.length})`,exact:true}).waitFor();
 const positions=()=>page.locator('.react-flow__node-task').evaluateAll(nodes=>Object.fromEntries(nodes.map(node=>[node.getAttribute('data-id'),node.style.transform])));
 const before=await positions();assert.equal(Object.keys(before).length,tasks.length);
 await page.getByRole('button',{name:`Show shared evidence (${shared.length})`,exact:true}).click();
 await page.locator('.shared-evidence-record').nth(7).waitFor();
 assert.equal(await page.locator('.shared-evidence-record').count(),8);
 assert.equal(await page.locator('.shared-evidence-node').count(),8);
 assert.equal(await page.locator('.shared-evidence-edge').count(),displayed.reduce((sum,item)=>sum+item.consumers.length,0));
 assert.deepEqual(await positions(),before,'Evidence expansion must preserve actual task positions.');
 assert.match(await page.locator('.shared-evidence-records .notice').textContent(),new RegExp(`Showing 8 of ${shared.length}`));
 for(const item of displayed){
  const row=page.locator(`.shared-evidence-record[data-artifact-id="${item.artifact.artifact_id}"]`);
  assert.deepEqual((await row.locator('[data-consumer-id]').evaluateAll(nodes=>nodes.map(n=>n.dataset.consumerId))).sort(),item.consumers.map(t=>t.task_id).sort());
 }
 const chosen=displayed.find(item=>item.artifact.kind==='scientific_tool_result')??displayed[0];
 await page.locator(`.shared-evidence-record[data-artifact-id="${chosen.artifact.artifact_id}"] .shared-artifact-link`).click();
 const drawer=page.getByRole('dialog',{name:'Evidence inspection'});
 assert.equal(await drawer.locator('.artifact-card').count(),1);
 assert.equal(await drawer.locator('.artifact-id').textContent(),chosen.artifact.artifact_id);
 await drawer.getByText('Exact inputs / numerical result',{exact:true}).click();
 const exact=await drawer.locator('details').filter({has:page.getByText('Exact inputs / numerical result',{exact:true})}).locator('pre').textContent();
 assert.deepEqual(JSON.parse(exact),chosen.artifact.data);
 await page.getByRole('button',{name:'Close evidence inspector'}).click();
 const consumer=chosen.consumers[0];
 await page.locator(`.shared-evidence-record[data-artifact-id="${chosen.artifact.artifact_id}"] [data-consumer-id="${consumer.task_id}"]`).click();
 assert.ok((await drawer.locator('.artifact-id').allTextContents()).includes(chosen.artifact.artifact_id),'Task inspector must include its prefixed read-set inputs.');
 await page.getByRole('button',{name:'Close evidence inspector'}).click();
 await mkdir('artifacts/manifests',{recursive:true});
 await page.locator('.graph-panel').screenshot({path:'artifacts/manifests/shared-evidence-e2e.png'});
 await page.getByRole('button',{name:'Reset replay to start',exact:true}).click();
 await page.locator('.mode-word').filter({hasText:'CATALOG PREVIEW'}).waitFor();
 assert.equal(await page.locator('.shared-evidence-record').count(),0);
 assert.equal(await page.locator('.shared-evidence-node').count(),0);
 assert.equal(await page.locator('.shared-evidence-edge').count(),0);
 assert.deepEqual(errors,[]);
 await mkdir('artifacts/manifests',{recursive:true});
 const report={journey:'Actual shared evidence connections and exact version inspection',mode:'deterministic_operational',mock_transport:false,run_id:runId,candidate_id:candidateId,through_sequence:snapshot.through_sequence,shared_records:shared.length,displayed_records:8,verified_edges:displayed.reduce((sum,item)=>sum+item.consumers.length,0),task_positions_unchanged:true,verified_artifact_id:chosen.artifact.artifact_id,verified_content_hash:chosen.artifact.content_hash,seek_zero_has_no_future_evidence:true,browser_errors:errors,passed:true};
 await writeFile('artifacts/manifests/shared-evidence-e2e.json',JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify(report));
}finally{await browser.close();}

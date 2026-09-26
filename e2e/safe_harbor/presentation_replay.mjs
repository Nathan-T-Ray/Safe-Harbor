// Existing real run only: camera and dossier presentation cannot create ledger events.
import { chromium } from '../../frontend/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import { mkdir, writeFile, readFile } from 'node:fs/promises';
const base=process.env.SAFE_HARBOR_UI_URL??'http://127.0.0.1:5176',runId=process.env.SAFE_HARBOR_RUN_ID??'run-152fa7ce5acd4449a90dd77269ada8d4';
const before=await(await fetch(`${base}/api/runs/${runId}/export`)).json(),sequenceEvent=before.events.find(e=>e.upserts.artifacts?.some(a=>a.kind==='scientific_tool_result'&&a.data.tool_name==='reference_sequence'));
assert.ok(sequenceEvent);const out='artifacts/safe_harbor/ui-real-run';await mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1280,height:720},reducedMotion:'reduce'}),errors=[],writes=[];
page.on('pageerror',error=>errors.push(error.message));page.on('request',request=>{if(!['GET','HEAD'].includes(request.method()))writes.push(request.method()+' '+request.url());});
try{
 await page.goto(`${base}/?run=${runId}`);await page.locator('.mode-word').getByText('REAL MODEL',{exact:true}).waitFor();
 await page.getByRole('combobox',{name:'Investigation execution mode'}).selectOption('real_model');
 assert.match(await page.locator('.assigned-caps').textContent(),/400,000 tokens · 40 tools · \$5 cost cap/);
 await page.getByRole('button',{name:'Presentation',exact:true}).click();await page.locator('.shp-preload.ready').waitFor();
 await page.getByRole('button',{name:'Dossier',exact:true}).click();const dossier=page.getByRole('dialog',{name:/Run run-/});
 await dossier.getByText(/Interim record: the run status is “blocked”/).waitFor();assert.equal(await dossier.locator('.shp-assessments article').count(),1);
 await dossier.getByRole('button',{name:'Close dossier',exact:true}).last().click();
 await page.getByRole('button',{name:'Reset presentation to start'}).click();
 assert.equal(await page.getByRole('button',{name:'Dossier at this commit',exact:true}).isDisabled(),true);
 const slider=page.getByRole('slider',{name:'Replay event position'});
 async function seek(n){await slider.fill(String(n));await page.waitForTimeout(150);}
 await seek(1);await page.getByRole('button',{name:'Dossier at this commit',exact:true}).click();
 await dossier.getByText('No assessment has been committed in this record.',{exact:true}).waitFor();
 assert.equal(await dossier.locator('.shp-assessments article').count(),0);assert.equal(await dossier.locator('.shp-checks .bad').count(),0);
 const downloadPromise=page.waitForEvent('download');await dossier.getByRole('button',{name:'Download dossier JSON ↓',exact:true}).click();const download=await downloadPromise;
 const path=await download.path(),historical=JSON.parse(await readFile(path,'utf8'));assert.equal(historical.snapshot.through_sequence,1);assert.equal(historical.snapshot.assessments.length,0);assert.equal(historical.immutable_assessment_revisions.length,0);assert.ok(historical.events.every(event=>event.sequence<=1));
 await dossier.getByRole('button',{name:'Close dossier',exact:true}).last().click();
 await seek(sequenceEvent.sequence);
 const zoom=page.getByRole('navigation',{name:'Genome zoom'});await zoom.getByRole('button',{name:'Sequence',exact:true}).waitFor();
 assert.ok((await zoom.getByRole('button',{name:'Sequence',exact:true}).getAttribute('class')).includes('active'));
 assert.ok((await page.locator('.sequence-row code').allTextContents()).join('').length>0);
 await page.getByRole('checkbox',{name:'Follow camera'}).uncheck();await seek(1);
 assert.ok((await zoom.getByRole('button',{name:'Sequence',exact:true}).getAttribute('class')).includes('active'));
 await page.getByRole('button',{name:'Return to selected candidate',exact:true}).click();assert.ok((await zoom.getByRole('button',{name:'Locus',exact:true}).getAttribute('class')).includes('active'));
 await page.screenshot({path:`${out}/historical-presentation.png`,fullPage:true});
 const after=await(await fetch(`${base}/api/runs/${runId}/export`)).json();assert.deepEqual(after.events,before.events);assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
 const result={journey:'External presentation/camera integration uses only actual committed events and historical dossiers',source_pr:63,source_commits:['22521e9','6c708cf'],run_id:runId,mode:'real_model_record_inspection',model_calls_by_inspection:0,ledger_writes:0,sequence_cue_event:sequenceEvent.event_id,historical_dossier_watermark:1,historical_dossier_assessments:0,parent_event_stream_unchanged:true,follow_toggle_honored:true,known_budget_caps_visible:true,browser_errors:errors,passed:true};await writeFile(`${out}/presentation-report.json`,JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
}finally{await browser.close();}

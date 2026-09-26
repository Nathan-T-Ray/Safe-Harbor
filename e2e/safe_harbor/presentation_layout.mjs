// Read-only projection and keyboard journey against an existing committed operational run.
import { chromium } from '../../frontend/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import { mkdir,writeFile } from 'node:fs/promises';
const base=process.env.SAFE_HARBOR_UI_URL??'http://127.0.0.1:5176',runId=process.env.SAFE_HARBOR_RUN_ID??'run-61c1f8d4a138477abc0a5dfe20ce9342',out='artifacts/safe_harbor/ui-real-run';await mkdir(out,{recursive:true});
const browser=await chromium.launch(),page=await browser.newPage({viewport:{width:1280,height:720},reducedMotion:'reduce'}),errors=[];page.on('pageerror',error=>errors.push(error.message));
try{
 await page.goto(`${base}/?run=${runId}`);await page.locator('.task-node').first().waitFor();
 const scientificText=await page.locator('.conclusion-text').textContent();
 await page.getByRole('button',{name:'Presentation',exact:true}).click();await page.locator('.shp-preload.ready').waitFor();
 assert.equal(await page.locator('.task-node').count(),0);assert.equal(await page.locator('.stage-labels span').count(),5);
 const bounds=await page.evaluate(()=>{const graph=document.querySelector('.graph-panel').getBoundingClientRect(),conclusion=document.querySelector('.conclusion-text').getBoundingClientRect();return{graph_top:graph.top,conclusion_top:conclusion.top,conclusion_bottom:conclusion.bottom,conclusion_px:parseFloat(getComputedStyle(document.querySelector('.conclusion-text')).fontSize),document_width:document.documentElement.scrollWidth};});
 assert.ok(bounds.graph_top>=0&&bounds.graph_top<640);assert.ok(bounds.conclusion_bottom<=720);assert.ok(bounds.conclusion_px>=18);assert.ok(bounds.document_width<=1280);
 assert.equal(await page.locator('.conclusion-text').textContent(),scientificText,'Scrolling preserves the full authoritative conclusion, without paraphrase.');
 await page.screenshot({path:`${out}/presentation-layout-1280.png`,fullPage:false});
 await page.getByRole('button',{name:'Expand task graph',exact:true}).click();await page.locator('.task-node').first().waitFor();
 const node=page.locator('.react-flow__node-task').first();const id=await node.getAttribute('data-id');await node.focus();await page.keyboard.press('Enter');
 await page.getByRole('dialog',{name:'Evidence inspection'}).waitFor();await page.waitForTimeout(80);
 assert.equal(await page.evaluate(()=>!!document.activeElement?.closest('.inspector-drawer')),true);
 for(let i=0;i<20;i++)await page.keyboard.press('Tab');assert.equal(await page.evaluate(()=>!!document.activeElement?.closest('.inspector-drawer')),true);
 await page.keyboard.press('Escape');assert.equal(await page.locator('.inspector-drawer').count(),0);assert.equal(await page.evaluate(()=>document.activeElement?.getAttribute('data-id')),id);
 await page.getByRole('button',{name:'Collapse task graph',exact:true}).click();assert.equal(await page.locator('.task-node').count(),0);assert.deepEqual(errors,[]);
 const report={journey:'1280×720 compact real-stage summary, intact scrollable conclusion and keyboard graph inspection',run_id:runId,mode:'deterministic_operational_record_inspection',model_calls:0,mock_transport:false,bounds,conclusion_text_unchanged:true,actual_task_expansion:true,graph_enter_opens_inspector:true,dialog_focus_trapped_and_restored:true,browser_errors:errors,passed:true};await writeFile(`${out}/layout-report.json`,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}finally{await browser.close();}

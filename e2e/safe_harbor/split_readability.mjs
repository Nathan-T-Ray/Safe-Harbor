// Focused actual-browser verification of the merged split layout, at 1280x720.
// Narrower than the earlier legacy-layout U14 suite; no equivalence is claimed.
import {chromium} from '../../frontend/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
const base=process.env.SAFE_HARBOR_UI_URL??'http://127.0.0.1:5176';
const runId='run-0142454a0a6b4976bd380c6eeeddec99';
const output='artifacts/safe_harbor/split-readability';
const checks=[],errors=[],writes=[];
const check=(name,passed,details={})=>{checks.push({name,passed,...details});console.log(`${passed?'PASS':'FAIL'} ${name}`);};
await mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true});
try {
  for(const motion of ['no-preference','reduce']) {
    const page=await browser.newPage({viewport:{width:1280,height:720},reducedMotion:motion});
    page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(!['GET','HEAD'].includes(r.method()))writes.push(r.method()+' '+r.url());});
    await page.goto(`${base}/?run=${runId}`);await page.getByRole('region',{name:'Stored final dossier summary'}).waitFor();
    await page.waitForTimeout(motion==='reduce'?100:1000);
    const measured=await page.evaluate(()=>{
      const rgb=s=>{const m=s.match(/rgba?\(([^)]+)\)/);return m?m[1].split(',').map(Number):null;};
      const lum=c=>{const f=v=>(v/=255)<=.04045?v/12.92:((v+.055)/1.055)**2.4;return .2126*f(c[0])+.7152*f(c[1])+.0722*f(c[2]);};
      const bg=el=>{for(let n=el;n;n=n.parentElement){const c=rgb(getComputedStyle(n).backgroundColor);if(c&&(c.length<4||c[3]===1))return c;}return[10,18,32];};
      const entries=[];
      for(const selector of ['.mode-chip','.sage-top .ctx','.cand-chip','.now-state','.now-head h1','.now-question','.genome-breadcrumb button','.coordinate-value','.reference-availability','.conclusion-panel .status-axes span','.conclusion-panel .status-axes strong','.conclusion-text','.final-dossier-stage','.final-dossier-conclusion','.tree-legend li','.sage-budget span']) {
        for(const el of document.querySelectorAll(selector)){const css=getComputedStyle(el);if(css.display==='none'||!el.getBoundingClientRect().width)continue;const fg=rgb(css.color),background=bg(el);const a=fg?lum(fg):null,b=lum(background);entries.push({selector,text:el.textContent.trim().slice(0,65),px:parseFloat(css.fontSize),contrast:a===null?null:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)});}
      }
      const conclusion=document.querySelector('.conclusion-text').getBoundingClientRect();
      return{entries,body_background:getComputedStyle(document.body).backgroundColor,horizontal_overflow:document.documentElement.scrollWidth>innerWidth+1,conclusion_initially_in_view:conclusion.top>=0&&conclusion.bottom<=innerHeight};
    });
    check(`${motion}: no horizontal page overflow`,!measured.horizontal_overflow);
    check(`${motion}: required dark navy background`,measured.body_background==='rgb(10, 18, 32)',{background:measured.body_background});
    const small=measured.entries.filter(e=>e.px<12),lowContrast=measured.entries.filter(e=>e.contrast!==null&&e.contrast<4.5);
    check(`${motion}: critical HTML labels >=12px`,small.length===0,{violations:small});
    check(`${motion}: critical text contrast >=4.5`,lowContrast.length===0,{violations:lowContrast});
    check(`${motion}: conclusion >=18px`,measured.entries.filter(e=>e.selector==='.conclusion-text').every(e=>e.px>=18));
    await page.screenshot({path:`${output}/${motion}-overview.png`});
    const menu=page.locator('details.more-menu');await menu.locator('summary').focus();await page.keyboard.press('Enter');
    await page.getByRole('button',{name:'Harness evolution',exact:true}).focus();await page.keyboard.press('Enter');
    const drawer=page.getByRole('dialog',{name:'Harness evolution'});await drawer.waitFor();
    check(`${motion}: keyboard opens harness and focus stays inside`,await drawer.evaluate(el=>el.contains(document.activeElement)));
    await page.keyboard.press('Escape');await drawer.waitFor({state:'hidden'});
    await menu.locator('summary').focus();if(!await menu.evaluate(el=>el.open))await page.keyboard.press('Enter');
    await page.getByRole('button',{name:'Presentation',exact:true}).focus();await page.keyboard.press('Enter');
    await page.locator('.shp-preload.ready').waitFor();
    check(`${motion}: presentation action closes the menu`,!await menu.evaluate(el=>el.open));
    await page.getByRole('button',{name:'Reset presentation to start'}).focus();await page.keyboard.press('Enter');
    check(`${motion}: keyboard reset removes future dossier`,await page.getByRole('region',{name:'Stored final dossier summary'}).count()===0);
    const slider=page.getByRole('slider',{name:'Replay event position'});await slider.focus();await page.keyboard.press('End');
    await page.getByRole('region',{name:'Stored final dossier summary'}).waitFor();
    check(`${motion}: keyboard timeline restores exact stored final stage`,await page.getByRole('region',{name:'Stored final dossier summary'}).getAttribute('data-current')==='true');
    await page.getByRole('checkbox',{name:'Follow camera'}).uncheck();
    const sequence=page.getByRole('navigation',{name:'Genome zoom'}).getByRole('button',{name:'Sequence',exact:true});await sequence.focus();await page.keyboard.press('Enter');
    check(`${motion}: genome has coordinate-labeled readable base alternative`,await page.locator('.sequence-row code').count()>0&&await page.locator('.coordinate-value').count()>0);
    await page.locator('.secondary-details > summary').focus();await page.keyboard.press('Enter');
    check(`${motion}: detailed task alternative opens by keyboard`,await page.getByRole('region',{name:'Agent tree',exact:true}).isVisible());
    if(motion==='reduce') {
      const moving=await page.locator('.now-head,.genome-canvas,.tnode,.tnode-in,.halo').evaluateAll(nodes=>nodes.map(el=>({tag:el.tagName,animation:getComputedStyle(el).animationName,transition:getComputedStyle(el).transitionDuration})).filter(e=>e.animation!=='none'||e.transition.split(',').some(x=>parseFloat(x)>0)));
      check('reduce: no decorative motion continues',moving.length===0,{violations:moving});
    }
    const card=page.getByRole('region',{name:'Stored final dossier summary'});await card.screenshot({path:`${output}/${motion}-stored-dossier.png`});
    await writeFile(`${output}/${motion}-measurements.json`,JSON.stringify(measured,null,2)+'\n');
    await page.close();
  }
  check('No browser exceptions or API mutations',errors.length===0&&writes.length===0,{errors,writes});
  const passed=checks.every(c=>c.passed);
  await writeFile(`${output}/report.json`,JSON.stringify({passed,run_id:runId,mode:'read_only_real_record_layout_verification',viewport:'1280x720',checks,model_calls:0,ledger_writes:0,limitations:['Focused merged-layout journey; it does not replace all 49 checks of the earlier legacy-layout report.','The new split layout requires vertical scrolling to read full conclusions and the separate final dossier.','Full-genome/graph SVG labels can be smaller than detail text; coordinate/base views and the keyboard-accessible detailed task list provide text alternatives.']},null,2)+'\n');
  console.log(JSON.stringify({passed,checks:checks.length,failures:checks.filter(c=>!c.passed).length,report:`${output}/report.json`}));
  if(!passed)process.exitCode=1;
} catch(error){await writeFile(`${output}/report.json`,JSON.stringify({passed:false,checks,error:String(error.stack??error),errors,writes},null,2)+'\n');throw error;}finally{await browser.close();}

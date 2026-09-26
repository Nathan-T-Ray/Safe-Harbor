// SH-U14 — actual browser readability / keyboard / motion / text-alternative journey.
// Real browser → Vite proxy → FastAPI → MongoDB. A deterministic operational run is
// started through the UI so graph, stage and status content is populated from the ledger.
// No mocked transport, no model calls, no biological interpretation is asserted.
// Every check is recorded; failures are reported honestly and make the exit status 1.
import { chromium } from '../../frontend/node_modules/playwright/index.mjs';
import { mkdir, writeFile } from 'node:fs/promises';

const base = process.env.SAFE_HARBOR_UI_URL ?? 'http://127.0.0.1:5190';
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const outDir = process.env.SAFE_HARBOR_READABILITY_OUT ?? `artifacts/safe_harbor/readability/${stamp}`;
const VIEWPORT = { width: 1280, height: 720 };
// Thresholds are fixed before measurement. 12 CSS px is the floor for any text a viewer
// needs to understand the screen; the conclusion is the "large conclusion" at ≥18 px.
const MIN_CRITICAL_PX = 12;
const MIN_CONCLUSION_PX = 18;
const MIN_CONTRAST = 4.5; // WCAG 2.x AA for normal-size text
const started = Date.now();
const checks = [];
const screenshots = [];
const record = (id, category, pass, details, severity = 'critical') => {
  checks.push({ id, category, status: pass ? 'pass' : 'fail', severity, details });
  console.log(`${pass ? 'PASS' : 'FAIL'} [${category}] ${id}`);
};
await mkdir(outDir, { recursive: true });
const shot = async (page, name) => {
  const path = `${outDir}/${name}.png`;
  await page.screenshot({ path });
  screenshots.push(path);
};

const health = await (await fetch(`${base}/api/health`)).json();
if (health.authoritative_store !== 'MongoDB') throw new Error('API health did not report MongoDB');
const catalog = await (await fetch(`${base}/api/catalog`)).json();

// In-page measurement helpers (serialized into the page).
const MEASURE = `
window.__sh = {
  parse(c){const m=c.match(/rgba?\\(([^)]+)\\)/);if(!m)return null;const p=m[1].split(',').map(s=>parseFloat(s));return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1};},
  lum({r,g,b}){const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)};return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b);},
  bg(el){let layers=[];for(let n=el;n&&n.nodeType===1;n=n.parentElement){const c=this.parse(getComputedStyle(n).backgroundColor);if(c&&c.a>0){layers.push(c);if(c.a>=1)break;}}
    let out={r:10,g:18,b:32};for(const c of layers.reverse()){out={r:c.r*c.a+out.r*(1-c.a),g:c.g*c.a+out.g*(1-c.a),b:c.b*c.a+out.b*(1-c.a)};}return out;},
  contrast(el){const cs=getComputedStyle(el);const isSvg=el instanceof SVGElement;let fg=this.parse(isSvg?cs.fill:cs.color);if(!fg)return null;const bg=this.bg(isSvg?el.ownerSVGElement.parentElement:el);
    fg={r:fg.r*fg.a+bg.r*(1-fg.a),g:fg.g*fg.a+bg.g*(1-fg.a),b:fg.b*fg.a+bg.b*(1-fg.a)};let opacity=1;for(let n=el;n&&n.nodeType===1;n=n.parentElement)opacity*=parseFloat(getComputedStyle(n).opacity);
    if(opacity<1)fg={r:fg.r*opacity+bg.r*(1-opacity),g:fg.g*opacity+bg.g*(1-opacity),b:fg.b*opacity+bg.b*(1-opacity)};
    const a=this.lum(fg),b=this.lum(bg);return Math.round(((Math.max(a,b)+0.05)/(Math.min(a,b)+0.05))*100)/100;},
  size(el){const fs=parseFloat(getComputedStyle(el).fontSize);if(el instanceof SVGElement&&el.ownerSVGElement){const svg=el.ownerSVGElement;const vb=svg.viewBox.baseVal;const scale=vb&&vb.width?svg.getBoundingClientRect().width/vb.width:1;return Math.round(fs*scale*100)/100;}return fs;},
  visible(el){const r=el.getBoundingClientRect();const cs=getComputedStyle(el);return r.width>0&&r.height>0&&cs.visibility!=='hidden'&&cs.display!=='none'&&(el.textContent||'').trim().length>0;},
  measure(selector){return [...document.querySelectorAll(selector)].filter(el=>this.visible(el)).map(el=>({text:(el.textContent||'').trim().replace(/\\s+/g,' ').slice(0,70),px:this.size(el),contrast:this.contrast(el),
    truncated:!(el instanceof SVGElement)&&(el.scrollWidth>el.clientWidth+1),inViewport:(()=>{const r=el.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight&&r.left>=0&&r.right<=innerWidth})()}));}
};`;

// Critical content: what a presenter's audience must read to follow the story.
const CRITICAL = {
  'candidate name': '.candidate-card strong',
  'candidate coordinate': '.candidate-coordinate',
  'candidate status': '.candidate-status',
  'mode label': '.mode-word',
  'mode explanation': '.mode-notice > span:not(.mode-word)',
  'live/recorded pill': '.pill',
  'zoom breadcrumb': '.genome-breadcrumb button',
  'status axis label': '.status-axes span',
  'status axis value': '.status-axes strong',
  'still-to-resolve text': '.question-callout p',
  'scientific footnote': '.scientific-footnote',
  'stage label': '.stage-labels span',
  'task status word': '.task-state',
  'task name': '.task-node strong',
  'task question': '.task-question',
  'status legend': '.graph-footer span',
  'timeline event': '.timeline-event',
  'chromosome axis label (SVG)': '.genome-canvas svg text.svg-label',
  'gene label (SVG)': '.genome-canvas svg text.svg-gene',
  'track heading': '.track-heading span',
  'sequence coordinate label': '.sequence-label',
  'genome footnote': '.genome-footnote',
  'coordinate footer': '.coordinate-footer span',
};

async function sizeAudit(page, label) {
  const findings = [];
  for (const [name, selector] of Object.entries(CRITICAL)) {
    const items = await page.evaluate(sel => window.__sh.measure(sel), selector);
    if (!items.length) continue;
    const small = items.filter(i => i.px < MIN_CRITICAL_PX);
    const lowContrast = items.filter(i => i.contrast !== null && i.contrast < MIN_CONTRAST);
    const truncated = items.filter(i => i.truncated);
    findings.push({ element: name, selector, count: items.length, min_px: Math.min(...items.map(i => i.px)),
      min_contrast: Math.min(...items.map(i => i.contrast ?? 99)), below_min_px: small.length, below_contrast: lowContrast.length,
      truncated: truncated.length, examples: [...small, ...lowContrast, ...truncated].slice(0, 3) });
  }
  const tooSmall = findings.filter(f => f.below_min_px);
  const lowContrast = findings.filter(f => f.below_contrast);
  record(`${label}: critical text ≥ ${MIN_CRITICAL_PX}px`, 'font-size', !tooSmall.length,
    { minimum_px: MIN_CRITICAL_PX, failing_elements: tooSmall.map(f => `${f.element} (${f.min_px}px, ${f.below_min_px}/${f.count})`), audit: findings });
  record(`${label}: critical text contrast ≥ ${MIN_CONTRAST}:1`, 'contrast', !lowContrast.length,
    { failing_elements: lowContrast.map(f => `${f.element} (${f.min_contrast}:1)`) });
  return findings;
}

async function tabTo(page, predicate, limit = 80) {
  const seen = [];
  for (let i = 0; i < limit; i++) {
    await page.keyboard.press('Tab');
    const info = await page.evaluate(() => {
      const el = document.activeElement; if (!el || el === document.body) return null;
      const cs = getComputedStyle(el);
      return { tag: el.tagName.toLowerCase(), text: (el.getAttribute('aria-label') || el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 60),
        cls: typeof el.className === 'string' ? el.className : el.getAttribute('class'), outline: `${cs.outlineStyle} ${cs.outlineWidth}`,
        focusVisible: el.matches(':focus-visible'), inBreadcrumb: !!el.closest('nav[aria-label="Genome zoom"]'), inRail: !!el.closest('.candidate-rail'),
        inGraph: !!el.closest('.graph-panel'), inSvg: el instanceof SVGElement };
    });
    if (info) seen.push(info);
    if (info && predicate(info)) return { found: info, seen };
  }
  return { found: null, seen };
}

const browser = await chromium.launch({ headless: true });
let runId = null;
const errors = [];
try {
  // ---------- Pass 1: default motion preference, 1280×720 ----------
  const context = await browser.newContext({ viewport: VIEWPORT, reducedMotion: 'no-preference' });
  await context.addInitScript(() => { try { localStorage.removeItem('safe-harbor-run'); } catch {} });
  const page = await context.newPage();
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(base);
  await page.addScriptTag({ content: MEASURE });
  await page.locator('.candidate-card').first().waitFor();
  await shot(page, '01-initial-1280x720');
  record('no horizontal page scroll at 1280', 'layout', await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    { scrollWidth: await page.evaluate(() => document.documentElement.scrollWidth) });

  // Start a deterministic operational run through the UI so real statuses/stages render.
  await page.getByRole('button', { name: /Start investigation/ }).click();
  await page.waitForFunction(() => new URLSearchParams(location.search).get('run'), null, { timeout: 30000 });
  runId = await page.evaluate(() => new URLSearchParams(location.search).get('run'));
  await page.waitForFunction(() => /complete/i.test(document.querySelector('.run-progress .pill')?.textContent ?? ''), null, { timeout: 120000 });
  await page.locator('.task-node').first().waitFor();
  await page.waitForTimeout(800);
  await page.addScriptTag({ content: MEASURE });
  await shot(page, '02-run-complete-standard');
  const conclusionStd = await page.evaluate(() => window.__sh.measure('.conclusion-text'));
  record('standard mode: conclusion text ≥ 18px', 'large-conclusion', conclusionStd.length > 0 && conclusionStd.every(c => c.px >= MIN_CONCLUSION_PX),
    { minimum_px: MIN_CONCLUSION_PX, measured: conclusionStd });
  record('standard mode: conclusion fully inside the 720px viewport without scrolling', 'large-conclusion',
    conclusionStd.length > 0 && conclusionStd.every(c => c.inViewport), { measured: conclusionStd.map(c => ({ px: c.px, inViewport: c.inViewport })) }, 'major');
  const standardAudit = await sizeAudit(page, 'standard mode');

  // Stage labels.
  const stages = await page.evaluate(() => window.__sh.measure('.stage-labels span'));
  record('stage labels: five words present and readable', 'stage-labels',
    stages.length === 5 && stages.every(s => s.px >= MIN_CRITICAL_PX && !s.truncated && s.contrast >= MIN_CONTRAST), { measured: stages });
  const stageNumbers = await page.evaluate(() => [...document.querySelectorAll('.stage-labels i')].map(el => ({ text: el.textContent, px: window.__sh.size(el), contrast: window.__sh.contrast(el) })));
  record('stage step numbers ≥ 12px', 'stage-labels', stageNumbers.every(s => s.px >= MIN_CRITICAL_PX), { measured: stageNumbers }, 'minor');

  // Presentation mode (the presenter view at 1280×720).
  await page.getByRole('button', { name: 'Presentation', exact: true }).click();
  await page.waitForTimeout(300);
  await shot(page, '03-presentation-mode');
  const conclusionPres = await page.evaluate(() => window.__sh.measure('.conclusion-text'));
  record('presentation mode: conclusion text ≥ 18px', 'large-conclusion', conclusionPres.length > 0 && conclusionPres.every(c => c.px >= MIN_CONCLUSION_PX), { measured: conclusionPres });
  record('presentation mode: conclusion fully inside the 720px viewport', 'large-conclusion',
    conclusionPres.length > 0 && conclusionPres.every(c => c.inViewport), { measured: conclusionPres.map(c => ({ px: c.px, inViewport: c.inViewport })) }, 'major');
  const presentationAudit = await sizeAudit(page, 'presentation mode');
  const foldReport = await page.evaluate(() => ({ documentHeight: document.documentElement.scrollHeight, graphTop: Math.round(document.querySelector('.graph-panel')?.getBoundingClientRect().top ?? -1),
    timelineTop: Math.round(document.querySelector('.timeline')?.getBoundingClientRect().top ?? -1) }));
  record('presentation mode: graph stage labels visible without scrolling', 'layout', foldReport.graphTop >= 0 && foldReport.graphTop < 720 - 80, foldReport, 'major');
  await page.getByRole('button', { name: 'Exit presentation' }).click();

  // Each zoom level: sizes of SVG / sequence labels + text alternatives.
  const zoomNav = page.getByRole('navigation', { name: 'Genome zoom' });
  const alternatives = [];
  for (const [level, label] of [['genome', 'Genome'], ['chromosome', catalog.candidates[0].chromosome], ['locus', 'Locus'], ['sequence', 'Sequence']]) {
    await page.locator('.candidate-card').first().click();
    await zoomNav.getByRole('button', { name: label, exact: true }).click();
    await page.waitForTimeout(450);
    await shot(page, `04-zoom-${level}`);
    const alt = await page.evaluate(() => {
      const canvas = document.querySelector('.genome-canvas');
      const svgs = [...canvas.querySelectorAll('svg')].map(svg => ({ role: svg.getAttribute('role'), label: svg.getAttribute('aria-label'),
        title: svg.querySelector(':scope > title')?.textContent ?? null, textNodes: svg.querySelectorAll('text').length,
        texts: [...svg.querySelectorAll('text')].map(t => t.textContent).slice(0, 14) }));
      const outsideText = [...canvas.childNodes].filter(n => !(n instanceof SVGElement)).map(n => n.textContent).join(' ').replace(/\s+/g, ' ').trim();
      const sequence = canvas.querySelector('.sequence-strip');
      return { svgs, outsideText: outsideText.slice(0, 400), sequenceLabel: sequence?.getAttribute('aria-label') ?? null, sequenceRole: sequence?.getAttribute('role') ?? null };
    });
    alternatives.push({ level, ...alt });
    const svgNamed = alt.svgs.every(s => s.role === 'img' && (s.label || s.title));
    record(`${level}: SVG has role=img and an accessible name`, 'text-alternatives', alt.svgs.length ? svgNamed : level === 'sequence', { svgs: alt.svgs.map(s => ({ role: s.role, label: s.label })) });
    if (level === 'locus') {
      // role=img hides child <text> from assistive technology; gene names must exist elsewhere.
      const geneNames = alt.svgs.flatMap(s => s.texts).filter(t => /[←→]/.test(t)).map(t => t.replace(/\s*[←→]\s*$/, ''));
      const exposed = geneNames.filter(g => alt.outsideText.includes(g) || alt.svgs.some(s => (s.label ?? '').includes(g)));
      record('locus: displayed gene names/strands available as text outside the role=img SVG', 'text-alternatives',
        geneNames.length > 0 && exposed.length === geneNames.length, { gene_labels_in_svg: geneNames, exposed_as_accessible_text: exposed });
    }
    if (level === 'genome') {
      const markerNames = await page.evaluate(() => [...document.querySelectorAll('.genome-canvas svg .marker')].map(m => ({ label: m.getAttribute('aria-label'), pressed: m.getAttribute('aria-pressed'), current: m.getAttribute('aria-current') })));
      record('genome: selected candidate marker state exposed without color (aria-pressed/aria-current or text)', 'color-independence',
        markerNames.some(m => m.pressed === 'true' || m.current), { markers: markerNames });
    }
    if (level === 'sequence') {
      record('sequence: strip has a text alternative', 'text-alternatives', !!alt.sequenceLabel, { aria_label: alt.sequenceLabel, role: alt.sequenceRole }, 'minor');
      const inside = await page.evaluate(() => { const el = document.querySelector('.inside-candidate'); if (!el) return null; const cs = getComputedStyle(el); return { borderBottom: `${cs.borderBottomStyle} ${cs.borderBottomWidth}`, fontWeight: cs.fontWeight, textDecoration: cs.textDecorationLine }; });
      record('sequence: in-candidate bases marked by a non-color cue', 'color-independence', !!inside && /solid|dashed|dotted/.test(inside.borderBottom) && !/0px/.test(inside.borderBottom), { inside_candidate_style: inside }, 'major');
    }
  }
  await page.addScriptTag({ content: MEASURE });
  // Re-audit locus/sequence-specific selectors.
  await zoomNav.getByRole('button', { name: 'Locus', exact: true }).click(); await page.waitForTimeout(400);
  const locusAudit = await sizeAudit(page, 'locus zoom');
  await zoomNav.getByRole('button', { name: 'Sequence', exact: true }).click(); await page.waitForTimeout(400);
  const sequenceAudit = await sizeAudit(page, 'sequence zoom');

  // Status conveyed with words/icons, not color alone.
  const statusText = await page.evaluate(() => ({
    candidateStatus: [...document.querySelectorAll('.candidate-status')].map(e => e.textContent.trim()),
    axes: [...document.querySelectorAll('.status-axes > div')].map(d => ({ label: d.querySelector('span')?.textContent, value: d.querySelector('strong')?.textContent })),
    taskStates: [...new Set([...document.querySelectorAll('.task-state')].map(e => e.textContent.trim()))],
    legend: [...document.querySelectorAll('.graph-footer span')].map(e => e.textContent.trim()),
    connection: document.querySelector('.connection-dot')?.nextElementSibling?.textContent ?? null,
    livePill: document.querySelector('.contextbar .pill')?.textContent ?? null,
  }));
  const hasWords = arr => arr.length > 0 && arr.every(t => /[A-Za-z]{3,}/.test(t));
  record('status: candidate cards, assessment axes, task nodes, legend and connection use words', 'color-independence',
    hasWords(statusText.candidateStatus) && statusText.axes.every(a => /[A-Za-z]{3,}/.test(a.value ?? '')) && hasWords(statusText.taskStates) && hasWords(statusText.legend) && !!statusText.connection && !!statusText.livePill,
    statusText);
  await zoomNav.getByRole('button', { name: 'Genome', exact: true }).click(); await page.waitForTimeout(400);
  const markerColors = await page.evaluate(() => [...document.querySelectorAll('.genome-canvas svg .marker circle')].map(c => c.getAttribute('fill')));
  const genomeFootnote = await page.locator('.genome-footnote').textContent();
  record('genome legend: explains both marker colors (selected vs other candidates)', 'color-independence',
    new Set(markerColors).size <= 1 || /selected/i.test(genomeFootnote ?? ''), { marker_fills: markerColors, footnote: genomeFootnote }, 'minor');

  // ---------- Keyboard-only navigation ----------
  await page.goto(`${base}/?run=${encodeURIComponent(runId)}`);
  await page.locator('.candidate-card').first().waitFor();
  await page.addScriptTag({ content: MEASURE });
  await page.locator('body').click({ position: { x: 5, y: 700 } });
  await page.evaluate(() => document.activeElement?.blur());
  const railSeek = await tabTo(page, i => i.inRail && /candidate-card/.test(i.cls ?? ''));
  record('keyboard: candidate rail reachable with Tab', 'keyboard', !!railSeek.found, { tab_presses: railSeek.seen.length, focus_order: railSeek.seen.map(s => s.text) });
  if (railSeek.found) {
    record('keyboard: focused candidate card shows a visible focus indicator', 'keyboard', railSeek.found.focusVisible && !/none/.test(railSeek.found.outline), railSeek.found);
    await page.keyboard.press('Tab');
    const second = await page.evaluate(() => ({ text: document.activeElement?.textContent?.trim().slice(0, 40), cls: document.activeElement?.className }));
    await page.keyboard.press('Enter');
    await page.waitForTimeout(200);
    const pressed = await page.evaluate(() => [...document.querySelectorAll('.candidate-card')].map(c => ({ name: c.querySelector('strong')?.textContent, pressed: c.getAttribute('aria-pressed') })));
    const heading = await page.locator('.conclusion-panel h2').textContent();
    const secondName = pressed[1]?.name;
    record('keyboard: Enter on second candidate selects it (aria-pressed + assessment heading)', 'keyboard',
      pressed[1]?.pressed === 'true' && heading === secondName, { focused: second, pressed, heading });
    await shot(page, '05-keyboard-candidate-selected');
  }
  const crumbSeek = await tabTo(page, i => i.inBreadcrumb && /Locus/.test(i.text));
  record('keyboard: zoom breadcrumb reachable with Tab', 'keyboard', !!crumbSeek.found, { tab_presses: crumbSeek.seen.length, last: crumbSeek.seen.slice(-6).map(s => s.text) });
  if (crumbSeek.found) {
    await page.keyboard.press('Enter');
    await page.waitForTimeout(400);
    const locusActive = await page.evaluate(() => ({ active: document.querySelector('.genome-breadcrumb button.active')?.textContent, current: document.querySelector('.genome-breadcrumb button.active')?.getAttribute('aria-current'), track: document.querySelector('.track-heading')?.textContent, focusStillInNav: !!document.activeElement?.closest('nav[aria-label="Genome zoom"]') }));
    record('keyboard: Enter on breadcrumb "Locus" changes zoom', 'keyboard', locusActive.active === 'Locus' && /GENCODE v36/.test(locusActive.track ?? ''), locusActive);
    record('keyboard: focus is retained on the breadcrumb after zoom change', 'keyboard', locusActive.focusStillInNav, locusActive, 'major');
    record('breadcrumb: current zoom level exposed to assistive tech (aria-current)', 'text-alternatives', !!locusActive.current, locusActive, 'major');
    await page.keyboard.press('Tab');
    await page.keyboard.press('Enter');
    await page.waitForTimeout(400);
    const seqActive = await page.evaluate(() => document.querySelector('.genome-breadcrumb button.active')?.textContent);
    record('keyboard: Tab+Enter advances breadcrumb to "Sequence"', 'keyboard', seqActive === 'Sequence', { active: seqActive });
    await shot(page, '06-keyboard-breadcrumb-sequence');
  }
  // Genome markers are SVG <g tabIndex=0>.
  await page.getByRole('navigation', { name: 'Genome zoom' }).getByRole('button', { name: 'Genome', exact: true }).focus();
  await page.keyboard.press('Enter');
  await page.waitForTimeout(400);
  const markerSeek = await tabTo(page, i => i.inSvg, 12);
  if (markerSeek.found) {
    await page.keyboard.press('Enter');
    await page.waitForTimeout(200);
  }
  record('keyboard: genome SVG candidate markers focusable and operable', 'keyboard', !!markerSeek.found, { found: markerSeek.found, seen: markerSeek.seen.map(s => s.text) }, 'major');
  // Graph task nodes → evidence drawer → Escape.
  const nodeSeek = await tabTo(page, i => i.inGraph && /react-flow__node/.test(i.cls ?? ''), 80);
  record('keyboard: investigation graph task nodes reachable with Tab', 'keyboard', !!nodeSeek.found, { found: nodeSeek.found, last: nodeSeek.seen.slice(-5).map(s => `${s.tag}.${s.cls}`) }, 'major');
  if (nodeSeek.found) {
    await page.keyboard.press('Enter');
    await page.waitForTimeout(400);
    const drawerOpen = await page.locator('.inspector-drawer').count();
    record('keyboard: Enter on a task node opens the evidence inspector', 'keyboard', drawerOpen === 1, { drawer_open: drawerOpen === 1 }, 'major');
    if (drawerOpen) {
      await shot(page, '07a-keyboard-task-inspector');
      const focusInDrawer = await page.evaluate(() => !!document.activeElement?.closest('.inspector-drawer'));
      record('keyboard: focus moves into the opened dialog', 'keyboard', focusInDrawer, { focusInDrawer }, 'major');
      await page.keyboard.press('Escape');
      await page.waitForTimeout(200);
      record('keyboard: Escape closes the dialog', 'keyboard', (await page.locator('.inspector-drawer').count()) === 0, {});
    }
  }
  // Evidence button (always present) → drawer → Escape.
  await page.getByRole('button', { name: /Inspect evidence/ }).focus();
  await page.keyboard.press('Enter');
  await page.waitForTimeout(300);
  const evidenceDrawer = await page.locator('.inspector-drawer').count();
  const focusAfterOpen = await page.evaluate(() => ({ inDrawer: !!document.activeElement?.closest('.inspector-drawer'), active: document.activeElement?.textContent?.trim().slice(0, 40) }));
  record('keyboard: evidence inspector opens from keyboard (Enter)', 'keyboard', evidenceDrawer === 1, { drawer_open: evidenceDrawer === 1 });
  record('keyboard: opened evidence dialog receives focus', 'keyboard', evidenceDrawer === 1 && focusAfterOpen.inDrawer, focusAfterOpen, 'major');
  if (evidenceDrawer === 1) {
    await shot(page, '07-keyboard-evidence-inspector');
    await page.keyboard.press('Escape');
    await page.waitForTimeout(200);
    const closed = (await page.locator('.inspector-drawer').count()) === 0;
    const focusAfterClose = await page.evaluate(() => document.activeElement?.textContent?.trim().slice(0, 40) ?? null);
    record('keyboard: Escape closes the evidence dialog', 'keyboard', closed, { closed });
    record('keyboard: focus returns to the invoking control after Escape', 'keyboard', closed && /Inspect evidence/.test(focusAfterClose ?? ''), { active_after_close: focusAfterClose }, 'minor');
  }

  // ---------- Motion (default preference) ----------
  await page.getByRole('navigation', { name: 'Genome zoom' }).getByRole('button', { name: 'Locus', exact: true }).click();
  const motionDefault = await page.evaluate(() => ({ canvasAnimation: getComputedStyle(document.querySelector('.genome-canvas')).animationName,
    infinite: document.getAnimations().filter(a => a.effect?.getTiming().iterations === Infinity).map(a => a.animationName ?? a.constructor.name) }));
  record('default motion: no infinite animation carries information', 'motion', motionDefault.infinite.length === 0, motionDefault, 'major');
  await context.close();

  // ---------- Pass 2: prefers-reduced-motion: reduce ----------
  const reduced = await browser.newContext({ viewport: VIEWPORT, reducedMotion: 'reduce' });
  const rpage = await reduced.newPage();
  rpage.on('pageerror', e => errors.push(e.message));
  await rpage.goto(`${base}/?run=${encodeURIComponent(runId)}`);
  await rpage.locator('.task-node').first().waitFor();
  const rNav = rpage.getByRole('navigation', { name: 'Genome zoom' });
  await rNav.getByRole('button', { name: 'Locus', exact: true }).click();
  const reducedStyles = await rpage.evaluate(() => {
    const canvas = document.querySelector('.genome-canvas');
    const button = document.querySelector('button');
    return { matches: matchMedia('(prefers-reduced-motion: reduce)').matches, canvasAnimation: getComputedStyle(canvas).animationName,
      buttonTransition: getComputedStyle(button).transitionDuration, running: document.getAnimations().filter(a => a.playState === 'running').length };
  });
  record('reduced motion: zoom transition animation disabled', 'motion', reducedStyles.matches && reducedStyles.canvasAnimation === 'none', reducedStyles);
  record('reduced motion: control transitions disabled', 'motion', /^0s/.test(reducedStyles.buttonTransition), reducedStyles, 'minor');
  record('reduced motion: no running animations after zoom change', 'motion', reducedStyles.running === 0, reducedStyles);
  // Replay with follow-camera: state still conveyed in text when animations are off.
  const playButton = rpage.getByRole('button', { name: 'Play replay' });
  if (await playButton.isEnabled()) {
    await rpage.getByRole('button', { name: 'Reset replay to start' }).click();
    await rpage.getByRole('button', { name: 'Next meaningful event' }).click();
    await rpage.waitForTimeout(300);
    const replay = await rpage.evaluate(() => ({ pill: document.querySelector('.timeline .pill')?.textContent, event: document.querySelector('.timeline-event')?.textContent, count: document.querySelector('.sequence-count')?.textContent,
      running: document.getAnimations().filter(a => a.playState === 'running').length }));
    record('reduced motion: replay step shows recorded state, event and position as text', 'motion', /RECORDED/.test(replay.pill ?? '') && !!replay.event && /\d+ \/ \d+/.test(replay.count ?? '') && replay.running === 0, replay);
    await rpage.screenshot({ path: `${outDir}/08-reduced-motion-replay.png` }); screenshots.push(`${outDir}/08-reduced-motion-replay.png`);
    await rpage.getByRole('button', { name: 'Return live' }).click();
  }
  await reduced.close();

  record('no uncaught page errors during journey', 'stability', errors.length === 0, { errors }, 'critical');

  const failed = checks.filter(c => c.status === 'fail');
  const report = { ticket: 'SH-U14', journey: 'readability / keyboard / motion / text alternatives at 1280×720',
    mode: 'deterministic_operational', mock_transport: false, model_calls: 0, biological_interpretation_tested: false,
    base, viewport: VIEWPORT, run_id: runId, health, thresholds: { min_critical_px: MIN_CRITICAL_PX, min_conclusion_px: MIN_CONCLUSION_PX, min_contrast: MIN_CONTRAST },
    summary: { total: checks.length, passed: checks.length - failed.length, failed: failed.length,
      failed_by_severity: failed.reduce((acc, c) => ({ ...acc, [c.severity]: (acc[c.severity] ?? 0) + 1 }), {}) },
    checks, audits: { standard: standardAudit, presentation: presentationAudit, locus: locusAudit, sequence: sequenceAudit },
    text_alternatives: alternatives, screenshots, browser_errors: errors, duration_ms: Date.now() - started };
  await writeFile(`${outDir}/report.json`, JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report.summary, null, 2));
  console.log(`Report: ${outDir}/report.json`);
  process.exitCode = failed.length ? 1 : 0;
} finally {
  await browser.close();
}

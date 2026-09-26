// SH-Q09 E2E: the genome zoom stays truthful, live, in recorded replay at an older revision,
// and while the follow camera (SH-U11 cues) drives zoom transitions during playback.
// Actual browser -> Vite proxy -> FastAPI -> coordinator -> MongoDB. No mocked transport, data or model.
//
//   SAFE_HARBOR_UI_URL=http://127.0.0.1:5181 node e2e/safe_harbor/genome.mjs
//
// Without SAFE_HARBOR_RUN_ID the journey creates a deterministic operational run for the whole
// shortlist (assigned tool_limit 80: three candidates use 39 of the default 40 before the revision)
// and applies the prepared withhold-control-evidence revision, so an older assessment revision
// exists to replay. Expected values come from the API catalog, committed run snapshots/events,
// committed reference artifacts and data/safe_harbor files, never from the rendered page. Motion is
// enabled and state is sampled on every animation frame while transitions are still running.
import { chromium } from '../../frontend/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const outDir = process.env.SAFE_HARBOR_GENOME_OUTPUT ?? path.join(root, 'artifacts/safe_harbor/genome-e2e/2026-09-26-q09-frames');
const base = (process.env.SAFE_HARBOR_UI_URL ?? 'http://127.0.0.1:5181').replace(/\/$/, '');
const startedAt = new Date().toISOString();
const fmt = n => n.toLocaleString('en-US');
const interval = c => `${c.chromosome}:${fmt(c.start + 1)}–${fmt(c.end)}`;
const sha256 = text => createHash('sha256').update(text).digest('hex');
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const close = (a, b, label, tol = 1e-6) => assert.ok(typeof a === 'number' && Math.abs(a - b) <= tol, `${label}: ${a} vs ${b}`);
async function api(route, body) {
  const response = await fetch(`${base}/api${route}`, body ? { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) } : undefined);
  assert.ok(response.ok, `${route}: ${response.status} ${await response.clone().text()}`);
  return response.json();
}
async function allEvents(runId) {
  const events = []; let after = 0, more = true;
  while (more) { const page = await api(`/runs/${runId}/events?after_sequence=${after}`); events.push(...page.events); after = events.at(-1)?.sequence ?? after; more = page.has_more; }
  return events;
}
async function settled(runId, after = 0) {
  const until = Date.now() + 120000;
  while (Date.now() < until) {
    const snap = await api(`/runs/${runId}/snapshot`);
    assert.ok(!['blocked', 'budget_exhausted', 'failed'].includes(snap.run.status), `run ${runId} ended ${snap.run.status}`);
    if (snap.run.status === 'complete' && snap.through_sequence > after) return snap;
    await sleep(400);
  }
  throw new Error(`run ${runId} did not complete`);
}

// ---------- Real inputs ----------
const catalog = await api('/catalog');
const committedChromosomes = JSON.parse(await readFile(path.join(root, 'data/safe_harbor/normalized/chromosomes.json'), 'utf8'));
const committedReference = JSON.parse(await readFile(path.join(root, 'data/safe_harbor/normalized/reference_assets.json'), 'utf8'));
let runId = process.env.SAFE_HARBOR_RUN_ID, provisioning = { created_by_journey: false };
if (!runId) {
  ({ run_id: runId } = await api('/runs', { candidate_ids: catalog.candidates.map(c => c.candidate_id), mode: 'deterministic', budget: { tool_limit: 80 } }));
  const first = await settled(runId);
  const revision = await api(`/runs/${runId}/evidence-revisions`, { fixture_id: 'withhold-control-evidence' });
  const done = await settled(runId, revision.sequence);
  provisioning = { created_by_journey: true, request: 'POST /runs {all catalog candidates, mode: deterministic, budget: {tool_limit: 80}} then POST /runs/{id}/evidence-revisions {fixture_id: withhold-control-evidence}', first_complete_sequence: first.through_sequence, revision_sequence: revision.sequence, final_sequence: done.through_sequence };
}
const events = await allEvents(runId);
const lastSequence = events.at(-1).sequence;
const snapshots = [null]; // index = through_sequence; 0 = before the first commit (no run)
for (let k = 1; k <= lastSequence; k++) snapshots.push(await api(`/runs/${runId}/snapshot?through_sequence=${k}`));
const finalSnap = snapshots[lastSequence];
const finalDigest = sha256(JSON.stringify(await api(`/runs/${runId}/snapshot`)));
const revisionEvent = events.find(e => e.cause === 'evidence.revised');
assert.ok(revisionEvent, 'Run must contain an actual committed evidence revision to exercise an older replay revision.');
const olderSequence = revisionEvent.sequence - 1, olderSnap = snapshots[olderSequence];
const latest = (snap, id) => snap?.assessments.filter(a => a.candidate_id === id).sort((a, b) => b.assessment_revision - a.assessment_revision)[0];
const candidates = finalSnap.candidates.map(c => catalog.candidates.find(x => x.candidate_id === c.candidate_id));
const revised = [...candidates].sort((a, b) => (latest(finalSnap, b.candidate_id)?.assessment_revision ?? 0) - (latest(finalSnap, a.candidate_id)?.assessment_revision ?? 0))[0];

// ---------- Expected display, derived independently of the page ----------
const drawn = catalog.chromosomes.filter(c => c.chromosome !== 'chrM');
const maxLength = Math.max(...catalog.chromosomes.map(c => c.length));
function context(candidate, snap) {
  const reference = snap.artifacts.filter(a => a.kind === 'reference_assets' && a.data.candidate_id === candidate.candidate_id && a.data.data_version === snap.run.data_version).sort((a, b) => a.revision - b.revision).at(-1);
  assert.ok(reference, `${candidate.candidate_id}: no committed reference artifact at sequence ${snap.through_sequence}`);
  const seq = reference.data.reference_assets.sequence, annotation = reference.data.reference_assets.annotation;
  const index = drawn.findIndex(x => x.chromosome === candidate.chromosome), length = drawn[index].length;
  const windowStart = Math.max(annotation.coverage.start, candidate.start - 100000), windowEnd = Math.min(annotation.coverage.end, candidate.end + 100000);
  const geneKeys = new Set(annotation.features.filter(f => f.end > windowStart && f.start < windowEnd).map(f => f.gene_id ?? f.name ?? f.transcript_id ?? String(f.start)));
  return { candidate, reference, seq, annotation, length, windowStart, windowEnd, geneKeys, featureNames: new Set(annotation.features.flatMap(f => [f.name, f.gene_id]).filter(Boolean)),
    overviewCx: Math.floor(index / 12) * 465 + 50 + candidate.start / length * (length / maxLength * 375), px: v => 45 + ((v - windowStart) / (windowEnd - windowStart)) * 850 };
}
function expectedState(snap, candidate) {
  const a = latest(snap, candidate.candidate_id);
  return {
    coordinate: interval(candidate), stored: `Display: 1-based inclusive · stored: [${candidate.start}, ${candidate.end})`,
    selectedCard: candidate.name, conclusionName: candidate.name, revisionPill: a ? `Revision ${a.assessment_revision}` : 'Unresolved',
    axes: a ? [a.screen_status, a.evidence_status, a.freshness].map(s => s.replaceAll('_', ' ')) : ['Not assessed', 'Unknown', 'No assessment'],
    conclusion: a?.conclusion ?? 'Begin with the evidence. The expression concern is unresolved.',
    dataVersion: snap.run.data_version, availability: `Frozen run assets · ${snap.run.data_version}`,
    acceptedTasks: `${snap.tasks.filter(t => t.status === 'complete').length} accepted tasks`, endpoints: a?.experimental_endpoint_results.length ?? 0,
  };
}
const visibleArtifactIds = (snap, candidate) => snap.artifacts.filter(a => { const owner = snap.tasks.find(t => t.task_id === a.provenance?.task_id)?.candidate_id; return (a.data.candidate_id ?? owner ?? candidate.candidate_id) === candidate.candidate_id; }).map(a => a.artifact_id).sort();
const levelExpect = {
  genome: (s, x) => { assert.equal(s.activeCrumb, 'Genome'); assert.equal(s.genomeHeading, 'The published shortlist'); assert.ok(s.selectedMarker, 'selected marker'); close(s.selectedMarker.cx, x.overviewCx, 'overview marker cx'); assert.equal(s.selectedMarker.row, x.candidate.chromosome.replace('chr', ''), 'marker on the wrong chromosome row'); close(s.selectedMarker.rowWidth / 375, x.length / maxLength, 'overview row width proportional to GRCh38 length'); close((s.selectedMarker.cx - s.selectedMarker.rowX) / s.selectedMarker.rowWidth, x.candidate.start / x.length, 'marker fraction along row'); assert.equal(s.selectedMarker.pressed, 'true', 'selected overview marker must expose aria-pressed'); assert.equal(s.selectedMarker.title, `${x.candidate.name} · ${interval(x.candidate)}`); assert.equal(s.selectedMarker.fill, '#7ee8dd'); },
  chromosome: (s, x) => { assert.equal(s.activeCrumb, x.candidate.chromosome); assert.equal(s.genomeHeading, x.candidate.name); assert.equal(s.chromosomeTitle, `${x.candidate.chromosome}${fmt(x.length)} reference bases`); assert.equal(s.svgLabel, `${x.candidate.chromosome}, selected candidate at ${x.candidate.start}`); const m = s.chromosomeMarker.find(v => v.name === x.candidate.name); assert.ok(m, 'chromosome marker'); close(m.x, 35 + x.candidate.start / x.length * 860, 'chromosome marker x'); },
  locus: (s, x) => { assert.equal(s.activeCrumb, 'Locus'); assert.equal(s.genomeHeading, x.candidate.name); assert.equal(s.svgLabel, `Coordinate-correct annotation view for ${interval(x.candidate)}`); assert.deepEqual(s.trackHeading, [x.annotation.release, x.annotation.coverage.complete ? 'Complete coverage of displayed window' : 'Coverage not verified']); assert.ok(s.locusRect, 'locus highlight'); close(s.locusRect.x, x.px(x.candidate.start), 'locus highlight x'); close(s.locusRect.width, Math.max(2, x.px(x.candidate.end) - x.px(x.candidate.start)), 'locus highlight width'); assert.deepEqual(s.ticks.slice(0, 5), [0, 1, 2, 3, 4].map(i => fmt(Math.round(x.windowStart + (x.windowEnd - x.windowStart) * i / 4 + 1)))); assert.equal(s.genesFootnote, `${x.geneKeys.size} genes${x.geneKeys.size > 12 ? ' · 12 nearest spans shown' : ''}`); assert.ok(s.geneLabels.length > 0 && s.geneLabels.every(l => x.featureNames.has(l.replace(/ [←→]$/, ''))), `gene labels not in frozen annotation: ${s.geneLabels}`); },
  // offset null: accept any displayed window, but it must be coordinate-coherent real bases.
  sequence: (s, x, offset = 0) => {
    const { seq, candidate } = x; assert.equal(s.activeCrumb, 'Sequence'); assert.equal(s.genomeHeading, candidate.name); assert.ok(s.rowLabels.length, 'no base rows');
    const start = offset === null ? Number(s.rowLabels[0].replaceAll(',', '')) - 1 : Math.max(seq.start, Math.min(candidate.start - 20 + offset, seq.end - 1));
    assert.ok(start >= seq.start && start < seq.end, `window start ${start} outside frozen window`);
    const bases = seq.sequence.slice(start - seq.start, start - seq.start + 100).toUpperCase();
    assert.deepEqual(s.trackHeading, [`${seq.chromosome}:${fmt(start + 1)}–${fmt(start + bases.length)}`, `GRCh38 · ${bases.length} actual reference bases`]);
    assert.equal(s.bases, bases, 'displayed bases differ from committed reference');
    assert.deepEqual(s.rowLabels, [fmt(start + 1), fmt(start + 51)].slice(0, Math.ceil(bases.length / 50)));
    assert.equal(s.insideCount, [...bases].filter((_, i) => start + i >= candidate.start && start + i < candidate.end).length);
    assert.deepEqual(s.titles, [...bases].map((_, i) => `${seq.chromosome}:${fmt(start + i + 1)}`), 'per-base coordinate titles');
    assert.equal(s.inside, [...bases].map((_, i) => start + i >= candidate.start && start + i < candidate.end ? '1' : '0').join(''), 'per-base candidate membership');
    assert.equal(s.hashLine, `SHA-256 ${seq.sha256}`); assert.equal(s.frozenWindow, `Frozen window: ${fmt(seq.start + 1)}–${fmt(seq.end)}`);
    return { start, bases: bases.length };
  },
};
const zoomOf = s => ['genome', 'chromosome', 'locus', 'sequence'].find(z => s.zoomClass?.includes(`zoom-${z}`));
function assertShared(s, expected, recorded) {
  for (const key of ['coordinate', 'stored', 'selectedCard', 'conclusionName', 'revisionPill', 'conclusion', 'dataVersion', 'availability', 'acceptedTasks', 'endpoints']) assert.deepEqual(s[key], expected[key], `${key}: ${JSON.stringify(s[key])} != ${JSON.stringify(expected[key])}`);
  assert.deepEqual(s.axes, expected.axes, `axes ${s.axes}`);
  if (recorded) { assert.equal(s.sequenceCount, recorded.sequenceCount); assert.equal(s.livePill, recorded.pill); }
}
// Full truth check for any displayed frame, whatever candidate/zoom the user or the camera chose.
function frameTruth(s) {
  const cursor = Number(s.sequenceCount.split(' / ')[0]);
  if (cursor === 0) {
    assert.equal(s.bases, null, 'bases shown before the first commit'); assert.equal(s.revisionPill, 'Unresolved'); assert.equal(s.endpoints, 0);
    assert.match(s.dataVersion, /No historical evidence/); assert.match(s.availability, /No historical reference evidence/); return { cursor, zoom: zoomOf(s) };
  }
  const snap = snapshots[cursor], candidate = candidates.find(c => c.name === s.selectedCard);
  assert.ok(candidate, `no run candidate selected (${s.selectedCard})`);
  const x = context(candidate, snap), zoom = zoomOf(s);
  assertShared(s, expectedState(snap, candidate)); levelExpect[zoom](s, x, null);
  return { cursor, zoom, candidate_id: candidate.candidate_id };
}

// ---------- Browser helpers ----------
const readInPage = () => {
  const q = s => document.querySelector(s), text = s => q(s)?.textContent ?? null;
  const canvas = q('.genome-canvas'), markers = [...document.querySelectorAll('.genome-canvas g.marker')];
  // A selected overview marker renders two circles (r=11 halo, r=7 marker); pick the marker explicitly.
  const selectedCircle = markers.flatMap(g => [...g.querySelectorAll('circle[r="7"][fill="#7ee8dd"]')])[0];
  const row = selectedCircle?.parentElement?.parentElement;
  const locusRect = [...document.querySelectorAll('.genome-canvas svg > rect')].find(r => r.getAttribute('stroke') === '#7ee8dd');
  const titles = [...document.querySelectorAll('.sequence-row code span')];
  return {
    zoomClass: canvas?.className ?? null, genomeHeading: text('.genome-panel .panel-head h2'), opacity: canvas ? Number(getComputedStyle(canvas).opacity) : null,
    animations: canvas ? canvas.getAnimations().filter(an => an.playState === 'running').length : 0,
    activeCrumb: text('nav[aria-label="Genome zoom"] button.active'), availability: text('.reference-availability'),
    coordinate: text('.coordinate-value'), stored: text('.coordinate-footer span:last-child'),
    selectedCard: q('.candidate-card[aria-pressed="true"] strong')?.textContent ?? null,
    conclusionName: text('.conclusion-panel .panel-head h2'), revisionPill: text('.conclusion-panel .panel-head .pill'),
    axes: [...document.querySelectorAll('.status-axes strong')].map(s => s.textContent), conclusion: text('.conclusion-text'), endpoints: document.querySelectorAll('.endpoint').length,
    dataVersion: text('.data-version'), sequenceCount: text('.sequence-count'), livePill: text('.contextbar .pill'), follow: q('.follow-camera input')?.checked ?? null,
    acceptedTasks: [...document.querySelectorAll('.run-progress span')].map(s => s.textContent).find(s => s.endsWith('accepted tasks')) ?? null,
    selectedMarker: selectedCircle ? { cx: Number(selectedCircle.getAttribute('cx')), title: selectedCircle.parentElement.querySelector('title')?.textContent, fill: selectedCircle.getAttribute('fill'), pressed: selectedCircle.parentElement.getAttribute('aria-pressed'), row: row?.querySelector(':scope > text')?.textContent ?? null, rowX: Number(row?.querySelector(':scope > rect')?.getAttribute('x')), rowWidth: Number(row?.querySelector(':scope > rect')?.getAttribute('width')) } : null,
    chromosomeTitle: text('.chromosome-title'), svgLabel: q('.genome-canvas svg')?.getAttribute('aria-label') ?? null,
    chromosomeMarker: markers.filter(g => g.querySelector('line')).map(g => ({ name: g.querySelector('text')?.textContent, x: Number(g.querySelector('line').getAttribute('x1')) })),
    locusRect: locusRect ? { x: Number(locusRect.getAttribute('x')), width: Number(locusRect.getAttribute('width')) } : null,
    trackHeading: [...document.querySelectorAll('.genome-canvas .track-heading span')].map(s => s.textContent),
    ticks: [...document.querySelectorAll('.genome-canvas svg g > text.svg-label')].map(t => t.textContent),
    genesFootnote: text('.genome-canvas .genome-footnote span:last-child'), geneLabels: [...document.querySelectorAll('.genome-canvas .svg-gene')].map(t => t.textContent),
    bases: [...document.querySelectorAll('.sequence-row code')].map(c => c.textContent).join('') || null,
    rowLabels: [...document.querySelectorAll('.sequence-row .sequence-label')].map(s => s.textContent), insideCount: document.querySelectorAll('.sequence-row .inside-candidate').length,
    titles: titles.map(t => t.title), inside: titles.map(t => t.classList.contains('inside-candidate') ? '1' : '0').join(''),
    hashLine: text('.genome-canvas .hash-line'), frozenWindow: [...document.querySelectorAll('.sequence-controls span')].map(s => s.textContent)[0] ?? null,
  };
};
const checks = [];
function check(name, fn, details = {}) {
  try { const extra = fn(); checks.push({ check: name, passed: true, ...details, ...(extra && typeof extra === 'object' ? extra : {}) }); }
  catch (error) { checks.push({ check: name, passed: false, error: error.message.slice(0, 1500), ...details }); }
}
const browser = await chromium.launch({ headless: true });
const browserContext = await browser.newContext({ viewport: { width: 1280, height: 720 }, locale: 'en-US', reducedMotion: 'no-preference' });
const page = await browserContext.newPage();
const errors = []; page.on('pageerror', e => errors.push(e.message));
const read = () => page.evaluate(readInPage);
// Run an action inside the page and sample every animation frame for `ms` (default: one zoom transition).
async function sampleFrames(action, ms = 600, until = null) {
  return page.evaluate(async ({ action, ms, until, readSource }) => {
    const readState = new Function(`return (${readSource})()`);
    if (action.crumb !== undefined || action.text) {
      const button = action.crumb !== undefined ? document.querySelectorAll('nav[aria-label="Genome zoom"] button')[action.crumb] : [...document.querySelectorAll('.genome-canvas button.text-button')].find(b => b.textContent.includes(action.text));
      if (!button) throw new Error(`Zoom control not found: ${JSON.stringify(action)}`);
      button.click();
    } else if (action.play) document.querySelector('button[aria-label="Play replay"]').click();
    const t0 = performance.now(), samples = [];
    while (performance.now() - t0 < ms) { await new Promise(r => requestAnimationFrame(r)); const s = readState(); samples.push({ t: Math.round(performance.now() - t0), ...s }); if (until && s.sequenceCount === until && performance.now() - t0 > 1500 && samples.filter(x => x.sequenceCount === until).length > 90) break; }
    return samples;
  }, { action, ms, until, readSource: readInPage.toString() });
}
async function evidenceIds() {
  await page.locator('.conclusion-panel').getByRole('button', { name: /Inspect evidence/ }).click();
  await page.getByRole('dialog', { name: 'Evidence inspection' }).waitFor();
  const ids = (await page.locator('.inspector-drawer code.artifact-id').allTextContents()).sort();
  await page.getByRole('button', { name: 'Close evidence inspector' }).click();
  await page.getByRole('dialog', { name: 'Evidence inspection' }).waitFor({ state: 'detached' });
  return ids;
}
const displayed = { live: [], replay: [] };
const screenshots = [];
async function tour(label, snap, candidate, recorded) {
  const x = context(candidate, snap), expected = expectedState(snap, candidate), expectedEvidence = visibleArtifactIds(snap, candidate);
  const summary = { label, candidate_id: candidate.candidate_id, through_sequence: snap.through_sequence, expected_revision: expected.revisionPill, expected_freshness: expected.axes[2], levels: [] };
  if ((await read()).activeCrumb !== 'Genome') await sampleFrames({ crumb: 0 });
  await page.locator('.candidate-card', { hasText: candidate.name }).click();
  await page.locator('.candidate-card[aria-pressed="true"]', { hasText: candidate.name }).waitFor();
  const evidenceBefore = await evidenceIds();
  check(`${label} ${candidate.candidate_id}: selected evidence equals snapshot at ${snap.through_sequence}`, () => assert.deepEqual(evidenceBefore, expectedEvidence), { displayed_artifacts: evidenceBefore.length, expected_artifacts: expectedEvidence.length });
  const start = await read();
  check(`${label} ${candidate.candidate_id}: overview marker at real position`, () => { levelExpect.genome(start, x); assertShared(start, expected, recorded); }, { marker_cx: start.selectedMarker?.cx, expected_cx: x.overviewCx });
  for (const [level, action] of [['chromosome', { crumb: 1 }], ['locus', { text: 'Inspect selected locus' }], ['sequence', { text: 'Read frozen reference bases' }], ['genome', { crumb: 0 }]]) {
    const samples = await sampleFrames(action);
    displayed[label].push(...samples.map(s => ({ revisionPill: s.revisionPill, freshness: s.axes[2] })));
    const animated = samples.filter(s => s.animations > 0 || s.opacity < 1);
    const bad = samples.map(s => { try { assert.equal(zoomOf(s), level, `zoom ${s.zoomClass}`); levelExpect[level](s, x); assertShared(s, expected, recorded); return null; } catch (e) { return { t: s.t, error: e.message.slice(0, 400) }; } }).filter(Boolean);
    const minOpacity = Number(Math.min(...samples.map(s => s.opacity)).toFixed(3));
    check(`${label} ${candidate.candidate_id}: ${level} consistent on every animation frame`, () => { assert.ok(animated.length > 0, 'no frame sampled while the transition was running'); assert.deepEqual(bad, []); }, { frames: samples.length, frames_mid_animation: animated.length, min_opacity: minOpacity, first_inconsistent: bad[0] ?? null });
    summary.levels.push({ level, frames: samples.length, frames_mid_animation: animated.length, min_opacity: minOpacity });
    if (level === 'sequence') {
      const s = samples.at(-1), committed = committedReference[candidate.candidate_id].sequence;
      check(`${label} ${candidate.candidate_id}: bases equal committed reference artifact and verified data file`, () => {
        assert.equal(sha256(x.seq.sequence), x.seq.sha256, 'artifact bases hash to recorded sha256');
        assert.equal(committed.sha256, x.seq.sha256); assert.equal(committed.start, x.seq.start); assert.equal(committed.sequence, x.seq.sequence);
        const start = candidate.start - 20; assert.equal(s.bases, committed.sequence.slice(start - committed.start, start - committed.start + 100).toUpperCase());
      }, { artifact_id: x.reference.artifact_id, artifact_content_hash: x.reference.content_hash, sequence_sha256: x.seq.sha256, displayed: `${candidate.chromosome}:${fmt(candidate.start - 19)}–${fmt(candidate.start + 80)}` });
      await page.getByRole('button', { name: '50 bp →' }).click();
      const right = await read();
      check(`${label} ${candidate.candidate_id}: +50 bp shows the next real bases`, () => { levelExpect.sequence(right, x, 50); assertShared(right, expected, recorded); });
      await page.getByRole('button', { name: '← 50 bp' }).click();
      const back = await read();
      check(`${label} ${candidate.candidate_id}: -50 bp restores the original bases`, () => { levelExpect.sequence(back, x, 0); assertShared(back, expected, recorded); });
      if (candidate === revised) { const file = `${label}-${candidate.candidate_id}-sequence.png`; await page.screenshot({ path: path.join(outDir, file) }); screenshots.push(file); }
    }
  }
  const evidenceAfter = await evidenceIds();
  check(`${label} ${candidate.candidate_id}: selected evidence unchanged after returning to overview`, () => assert.deepEqual(evidenceAfter, evidenceBefore));
  return summary;
}
const setFollow = async on => { const box = page.locator('.follow-camera input'); if ((await box.isChecked()) !== on) await box.click(); assert.equal(await box.isChecked(), on); };
const seek = async k => { await page.getByRole('slider', { name: 'Replay event position' }).fill(String(k)); await page.locator('.sequence-count').getByText(`${k} / ${lastSequence}`, { exact: true }).waitFor(); };
// Camera target the product's cue derivation (frontend/src/safe-harbor/cues.ts) assigns to a position.
const cameraTarget = k => page.evaluate(async ({ runId, k }) => {
  const { deriveCues, cameraAt } = await import('/src/safe-harbor/cues.ts');
  const events = []; let after = 0, more = true;
  while (more) { const p = await (await fetch(`/api/runs/${runId}/events?after_sequence=${after}`)).json(); events.push(...p.events); after = events.at(-1)?.sequence ?? after; more = p.has_more; }
  const cues = deriveCues(events); return { target: cameraAt(cues, k), cue_count: cues.length, cues_through_k: cues.filter(c => c.sequence <= k).length };
}, { runId, k });

let summary = {};
try {
  await mkdir(outDir, { recursive: true });
  check('catalog candidates equal run candidates and committed data', () => {
    for (const candidate of candidates) {
      assert.deepEqual({ ...finalSnap.candidates.find(c => c.candidate_id === candidate.candidate_id) }, { ...candidate });
      assert.equal(committedChromosomes.find(c => c.chromosome === candidate.chromosome).length, catalog.chromosomes.find(c => c.chromosome === candidate.chromosome).length);
      assert.equal(candidate.source_coordinates.start - 1, candidate.start); assert.equal(candidate.source_coordinates.end, candidate.end);
      const { seq } = context(candidate, finalSnap); assert.ok(seq.start <= candidate.start && seq.end >= candidate.end && seq.sequence.length === seq.end - seq.start);
    }
  }, { candidates: candidates.map(c => ({ candidate_id: c.candidate_id, interval: interval(c), stored: [c.start, c.end] })) });

  // A. Live record: every candidate through all four levels and back.
  await page.goto(`${base}/?run=${encodeURIComponent(runId)}`);
  await page.getByText('Ledger connected', { exact: true }).waitFor();
  await page.locator('.sequence-count').getByText(`${lastSequence} / ${lastSequence}`, { exact: true }).waitFor();
  await page.locator('.run-progress').getByText(expectedState(finalSnap, candidates[0]).acceptedTasks, { exact: true }).waitFor();
  const live = [];
  for (const candidate of candidates) live.push(await tour('live', finalSnap, candidate, { sequenceCount: `${lastSequence} / ${lastSequence}`, pill: 'LIVE' }));

  // B. Seek to the older position with follow camera on: the camera may move the view, never the history.
  await setFollow(true);
  await seek(olderSequence); await sleep(700);
  const afterSeek = await read(), camera = await cameraTarget(olderSequence);
  check(`follow camera at seek ${olderSequence}: view matches cue target and snapshot`, () => {
    if (camera.target.zoom) assert.equal(zoomOf(afterSeek), camera.target.zoom);
    if (camera.target.candidate_id) assert.equal(afterSeek.selectedCard, candidates.find(c => c.candidate_id === camera.target.candidate_id).name);
    return { frame: frameTruth(afterSeek) };
  }, { cue_target: camera.target, cues_total: camera.cue_count, cues_through_position: camera.cues_through_k });

  // C. Replay tours at the older position (revised candidate first).
  const replay = [];
  for (const candidate of [revised, ...candidates.filter(c => c !== revised)]) replay.push(await tour('replay', olderSnap, candidate, { sequenceCount: `${olderSequence} / ${lastSequence}`, pill: 'RECORDED' }));
  const olderA = latest(olderSnap, revised.candidate_id), finalA = latest(finalSnap, revised.candidate_id);
  check('replay: older position shows no later assessment revision or artifacts', () => {
    assert.ok(olderA && finalA && (olderA.assessment_revision < finalA.assessment_revision || olderA.freshness !== finalA.freshness), 'run must have a later assessment state that could leak');
    const revisedShown = displayed.replay.filter(s => s.revisionPill !== null);
    const allowed = new Set(candidates.map(c => latest(olderSnap, c.candidate_id)).filter(Boolean).map(a => `Revision ${a.assessment_revision}`));
    assert.ok(revisedShown.every(s => allowed.has(s.revisionPill)), `leaked revision: ${[...new Set(revisedShown.map(s => s.revisionPill))]}`);
    assert.ok(finalSnap.artifacts.length > olderSnap.artifacts.length, 'run must have artifacts committed after the older position');
  }, { displayed_states_checked: displayed.replay.length, older_sequence: olderSequence, older_revision: olderA?.assessment_revision, older_freshness: olderA?.freshness, final_revision: finalA?.assessment_revision, final_freshness: finalA?.freshness, artifacts_at_older: olderSnap.artifacts.length, artifacts_final: finalSnap.artifacts.length });

  // D. Follow camera off: seeks across revisions keep the user's sequence view; history follows the cursor.
  await setFollow(false);
  await page.locator('.candidate-card', { hasText: revised.name }).click();
  await sampleFrames({ crumb: 3 });
  const seekResults = [];
  for (const k of [0, olderSequence, lastSequence, olderSequence]) {
    await seek(k); const s = await read();
    seekResults.push({ sequence: k, revision: s.revisionPill, freshness: s.axes[2], bases_shown: s.bases?.length ?? 0, crumb: s.activeCrumb, selected: s.selectedCard });
    check(`follow off, seek ${k} while zoomed to sequence: view held, state equals snapshot`, () => { assert.equal(s.activeCrumb, 'Sequence'); assert.equal(s.selectedCard, revised.name); const f = frameTruth(s); if (k) levelExpect.sequence(s, context(revised, snapshots[k]), 0); return { frame: f }; });
  }

  // E. Follow camera on during playback from the start: cue-driven zoom transitions sampled on every frame.
  await setFollow(true);
  await seek(0);
  await page.getByRole('combobox', { name: 'Replay speed' }).selectOption('4');
  const played = await sampleFrames({ play: true }, 30000, `${lastSequence} / ${lastSequence}`);
  let cameraMoves = 0, prev = null; const zoomsSeen = new Set(), candidatesSeen = new Set(), bad = [];
  let midAnimationAfterCameraMove = 0, lastMoveAt = -1;
  for (const [i, s] of played.entries()) {
    const key = `${zoomOf(s)}|${s.selectedCard}`;
    if (prev !== null && key !== prev) { cameraMoves++; lastMoveAt = i; }
    if (lastMoveAt >= 0 && i - lastMoveAt < 30 && (s.animations > 0 || s.opacity < 1)) midAnimationAfterCameraMove++;
    prev = key; zoomsSeen.add(zoomOf(s)); if (s.selectedCard) candidatesSeen.add(s.selectedCard);
    try { frameTruth(s); } catch (e) { bad.push({ t: s.t, sequence: s.sequenceCount, zoom: zoomOf(s), selected: s.selectedCard, error: e.message.slice(0, 400) }); }
  }
  const cursors = played.map(s => Number(s.sequenceCount.split(' / ')[0]));
  check('follow-camera playback: every frame truthful while cues drive zoom transitions', () => {
    assert.ok(cursors.at(-1) === lastSequence, `playback ended at ${cursors.at(-1)}`);
    assert.ok(cursors.every((c, i) => i === 0 || c >= cursors[i - 1]), 'cursor moved backward during playback');
    assert.ok(cameraMoves > 0, 'cues never moved the camera during playback');
    assert.ok(midAnimationAfterCameraMove > 0, 'no frame sampled mid-animation after a camera move');
    assert.deepEqual(bad.slice(0, 5), []);
  }, { frames: played.length, sequences_covered: new Set(cursors).size, camera_moves: cameraMoves, frames_mid_animation_after_camera_move: midAnimationAfterCameraMove, zooms_seen: [...zoomsSeen], candidates_seen: [...candidatesSeen], inconsistent_frames: bad.length, first_inconsistent: bad[0] ?? null });
  await sleep(1200);
  const endView = await read(), endCamera = await cameraTarget(lastSequence);
  check('follow-camera playback end: view equals final cue target, evidence equals final snapshot', () => {
    if (endCamera.target.zoom) assert.equal(zoomOf(endView), endCamera.target.zoom);
    if (endCamera.target.candidate_id) assert.equal(endView.selectedCard, candidates.find(c => c.candidate_id === endCamera.target.candidate_id).name);
    return { frame: frameTruth(endView) };
  }, { cue_target: endCamera.target });
  const endCandidate = candidates.find(c => c.name === endView.selectedCard);
  const endEvidence = await evidenceIds();
  check('follow-camera playback end: selected evidence equals final snapshot', () => assert.deepEqual(endEvidence, visibleArtifactIds(finalSnap, endCandidate)), { candidate_id: endCandidate?.candidate_id, displayed_artifacts: endEvidence.length });
  const file = 'follow-camera-playback-end.png'; await page.screenshot({ path: path.join(outDir, file) }); screenshots.push(file);
  const afterDigest = sha256(JSON.stringify(await api(`/runs/${runId}/snapshot`)));
  check('cues and zoom never changed the scientific record', () => assert.equal(afterDigest, finalDigest), { snapshot_sha256: afterDigest });

  await page.getByRole('button', { name: 'Return live', exact: true }).click();
  await page.locator('.sequence-count').getByText(`${lastSequence} / ${lastSequence}`, { exact: true }).waitFor();
  const liveAgain = await read();
  check('return live: LIVE label and final state for the selected candidate', () => { assert.equal(liveAgain.livePill, 'LIVE'); return { frame: frameTruth(liveAgain) }; });
  check('no browser page errors', () => assert.deepEqual(errors, []));
  summary = { live, replay, seek_results_follow_off: seekResults };
} catch (error) {
  checks.push({ check: 'journey completed without an unexpected exception', passed: false, error: String(error?.stack ?? error).slice(0, 2000) });
  await page.screenshot({ path: path.join(outDir, 'failure.png') }).catch(() => {});
} finally {
  await browser.close();
}
const passed = checks.length > 0 && checks.every(c => c.passed);
const report = {
  ticket: 'SH-Q09', journey: 'Genome zoom truthfulness: overview -> chromosome -> locus -> sequence -> overview for every candidate, live, at an older replay position, with follow camera off/on and during cue-driven playback',
  mode: 'deterministic_operational', replay_mode: 'recorded_replay_of_deterministic_operational_run', mock_transport: false,
  model_calls: finalSnap.run.budget?.model_calls ?? 0, run_mode: finalSnap.run.mode, run_status: finalSnap.run.status, run_budget: finalSnap.run.budget,
  ui_url: base, run_id: runId, provisioning, started_at: startedAt, finished_at: new Date().toISOString(),
  viewport: '1280x720', reduced_motion: 'no-preference (transitions sampled on every animation frame)', data_version: finalSnap.run.data_version,
  server_camera_cues_in_events: events.filter(e => e.camera_cue).length,
  replay_positions: { older_sequence: olderSequence, evidence_revision_sequence: revisionEvent.sequence, last_sequence: lastSequence, revised_candidate: revised.candidate_id },
  extends: 'artifacts/safe_harbor/genome-e2e/2026-09-26-q09/ and artifacts/safe_harbor/pr67-review/selector-compatible/ (PR #67 journey: transitions checked at start and +700 ms). All of its assertions are kept, including the 897b9e9 halo-safe selector and aria-pressed check; this run adds per-frame sampling, evidence-panel IDs, seeks while zoomed and follow-camera playback.',
  passed, checks_passed: checks.filter(c => c.passed).length, checks_total: checks.length, checks, summary, screenshots, browser_errors: errors,
  limitations: [
    'Deterministic operational run; no model reasoning is shown or evaluated.',
    'Follow-camera targets are derived client-side by frontend/src/safe-harbor/cues.ts from committed events; the run carries no server camera_cue fields. The journey uses cameraAt() only to check where the camera went, and checks truthfulness independently against API snapshots.',
    'The SVG locus view shows merged gene spans, not exon models; igv.js tracks are not exercised.',
    'Reduced-motion rendering is not re-checked here (SH-U14 readability journey covers it).',
  ],
};
await mkdir(outDir, { recursive: true });
await writeFile(path.join(outDir, 'report.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ passed, run_id: runId, checks: checks.map(c => `${c.passed ? 'PASS' : 'FAIL'} ${c.check}`) }, null, 2));
if (!passed) process.exitCode = 1;

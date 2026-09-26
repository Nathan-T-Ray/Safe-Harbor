// SH-Q09 E2E: the genome zoom stays truthful, live and during replay at an older revision.
// Actual browser, Vite proxy, API and MongoDB. No mocked transport, data or model.
//
//   SAFE_HARBOR_UI_URL=http://127.0.0.1:5174 node e2e/safe_harbor/genome.mjs
//
// Without SAFE_HARBOR_RUN_ID the journey creates a deterministic operational run for the
// whole shortlist and applies the prepared withhold-control-evidence revision, so the
// first candidate has an older assessment revision to replay. The assigned tool budget
// covers the reopened work (three candidates use 39 of the default 40 before revision). Expected values come from
// the catalog, the run's committed reference artifacts and the data lane's verified
// sequence hashes, never from the rendered page.
import {chromium} from '../../frontend/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir, readFile, writeFile} from 'node:fs/promises';

const base = (process.env.SAFE_HARBOR_UI_URL ?? 'http://127.0.0.1:5174').replace(/\/$/, '');
const output = process.env.SAFE_HARBOR_GENOME_OUTPUT ?? `artifacts/safe_harbor/genome-e2e/${Date.now()}`;
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

async function api(path, body) {
  const response = await fetch(`${base}/api${path}`, body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  assert.ok(response.ok, `${path}: ${response.status} ${await response.clone().text()}`);
  return response.json();
}

async function settled(runId, after = 0) {
  const until = Date.now() + 120000;
  while (Date.now() < until) {
    const snapshot = await api(`/runs/${runId}/snapshot`);
    assert.ok(!['blocked', 'budget_exhausted', 'failed'].includes(snapshot.run.status), `run ${runId} ended ${snapshot.run.status}`);
    if (snapshot.run.status === 'complete' && snapshot.through_sequence > after) return snapshot;
    await sleep(400);
  }
  throw new Error(`run ${runId} did not complete`);
}

async function prepareRun(catalog) {
  if (process.env.SAFE_HARBOR_RUN_ID) return {runId: process.env.SAFE_HARBOR_RUN_ID, created: false};
  const {run_id: runId} = await api('/runs', {mode: 'deterministic', candidate_ids: catalog.candidates.map(c => c.candidate_id), budget: {tool_limit: 80}});
  await settled(runId);
  const revision = await api(`/runs/${runId}/evidence-revisions`, {fixture_id: 'withhold-control-evidence'});
  await settled(runId, revision.sequence);
  return {runId, created: true};
}

async function allEvents(runId) {
  const events = [];
  let after = 0, more = true;
  while (more) {
    const page = await api(`/runs/${runId}/events?after_sequence=${after}`);
    events.push(...page.events);
    after = events.at(-1)?.sequence ?? after;
    more = page.has_more;
  }
  return events;
}

const latestRevision = (snapshot, candidateId) => Math.max(0, ...snapshot.assessments.filter(a => a.candidate_id === candidateId).map(a => a.assessment_revision));
const near = (actual, expected, tolerance, label) => assert.ok(Math.abs(actual - expected) <= tolerance, `${label}: ${actual} vs ${expected}`);

async function main() {
  const catalog = await api('/catalog');
  const verified = JSON.parse(await readFile('data/safe_harbor/normalized/reference_assets.json', 'utf8'));
  const {runId, created} = await prepareRun(catalog);
  const live = await api(`/runs/${runId}/snapshot`);
  const events = await allEvents(runId);
  const revisionEvent = events.find(event => event.cause === 'evidence.revised');
  assert.ok(revisionEvent, 'Run must contain an actual evidence revision so an older assessment revision exists');
  const historicalSequence = revisionEvent.sequence - 1;
  const historical = await api(`/runs/${runId}/snapshot?through_sequence=${historicalSequence}`);
  const revised = revisionEvent.upserts.artifacts?.[0]?.data?.candidate_id ?? live.run.candidate_ids[0];
  assert.ok(latestRevision(live, revised) > latestRevision(historical, revised), 'Replay position must precede a newer committed assessment revision');

  const lengths = Object.fromEntries(catalog.chromosomes.map(c => [c.chromosome, c.length]));
  const maxLength = Math.max(...catalog.chromosomes.filter(c => c.chromosome !== 'chrM').map(c => c.length));
  const frozen = snapshot => Object.fromEntries(live.candidates.map(candidate => {
    const artifact = snapshot.artifacts.filter(a => a.kind === 'reference_assets' && a.data.candidate_id === candidate.candidate_id && a.data.data_version === snapshot.run.data_version).sort((a, b) => a.revision - b.revision).at(-1);
    assert.ok(artifact, `${candidate.candidate_id}: no committed reference artifact at sequence ${snapshot.through_sequence}`);
    return [candidate.candidate_id, artifact];
  }));
  // Committed bases must be the data lane's verified UCSC window before they can serve as truth.
  const sequenceIntegrity = [];
  for (const [candidateId, artifact] of Object.entries(frozen(live))) {
    const seq = artifact.data.reference_assets.sequence;
    const digest = createHash('sha256').update(seq.sequence).digest('hex');
    assert.equal(digest, seq.sha256, `${candidateId}: committed bases do not match their recorded hash`);
    assert.equal(seq.sha256, verified[candidateId].sequence.sha256, `${candidateId}: committed bases differ from the verified source window`);
    assert.equal(seq.sequence.length, seq.end - seq.start, `${candidateId}: window length differs from its coordinates`);
    sequenceIntegrity.push({candidate_id: candidateId, artifact_id: artifact.artifact_id, window: `${seq.chromosome}:[${seq.start},${seq.end})`, sha256: digest, verified_source_match: true});
  }

  await mkdir(output, {recursive: true});
  const browser = await chromium.launch({headless: true});
  const page = await browser.newPage({viewport: {width: 1280, height: 720}});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const checks = [];
  const fmt = value => page.evaluate(n => n.toLocaleString(), value);
  const crumbs = page.getByRole('navigation', {name: 'Genome zoom'});
  const genome = page.getByRole('region', {name: 'Genome viewer'});

  // Selected evidence and version must agree with the ledger at the displayed watermark, before and after transitions settle.
  async function consistent(candidate, expect, label) {
    for (const wait of [0, 700]) {
      await sleep(wait);
      const panel = page.getByRole('region', {name: 'Selected candidate assessment'});
      assert.equal((await panel.locator('h2').first().textContent()).trim(), candidate.name, `${label}: selected candidate changed`);
      const pill = (await panel.locator('.panel-head .pill').first().textContent()).trim();
      assert.equal(pill, expect.revision ? `Revision ${expect.revision}` : 'Unresolved', `${label}: assessment version`);
      assert.equal((await page.locator('.data-version').textContent()).trim(), expect.dataVersion, `${label}: data version`);
      assert.equal((await page.locator('.contextbar .pill').textContent()).trim(), expect.mode, `${label}: live/recorded label`);
      assert.match(await genome.locator('.reference-availability').textContent(), new RegExp(`Frozen run assets · ${expect.dataVersion}`), `${label}: reference provenance`);
    }
  }

  async function journey(candidate, expect, phase) {
    const record = {phase, candidate_id: candidate.candidate_id, assessment_revision: expect.revision, sequence: expect.sequence, levels: []};
    const length = lengths[candidate.chromosome];
    const seq = expect.reference.data.reference_assets.sequence;
    const annotation = expect.reference.data.reference_assets.annotation;
    await crumbs.getByRole('button', {name: 'Genome', exact: true}).click();

    // 1. Genome overview: real relative chromosome lengths and the candidate's actual position.
    const marker = genome.getByRole('button', {name: `Select ${candidate.name}`});
    const overview = await marker.evaluate(node => {
      const row = node.parentElement, rect = row.querySelector('rect'), circle = node.querySelector('circle');
      return {label: row.querySelector('text').textContent, x: +rect.getAttribute('x'), width: +rect.getAttribute('width'), cx: +circle.getAttribute('cx')};
    });
    assert.equal(overview.label, candidate.chromosome.replace('chr', ''), 'marker on the wrong chromosome row');
    near((overview.cx - overview.x) / overview.width, candidate.start / length, 1e-6, 'overview marker position');
    near(overview.width / 375, length / maxLength, 1e-6, 'overview chromosome length');
    await marker.click();
    await consistent(candidate, expect, `${phase} genome`);
    record.levels.push({level: 'genome', marker_fraction: (overview.cx - overview.x) / overview.width, expected_fraction: candidate.start / length});

    // 2. Selected chromosome at its reference length.
    await crumbs.getByRole('button', {name: candidate.chromosome, exact: true}).click();
    assert.equal((await genome.locator('.chromosome-title strong').textContent()).trim(), candidate.chromosome);
    assert.equal((await genome.locator('.chromosome-title span').textContent()).trim(), `${await fmt(length)} reference bases`);
    const line = await genome.locator('g.marker', {hasText: candidate.name}).locator('line').evaluate(node => +node.getAttribute('x1'));
    near((line - 35) / 860, candidate.start / length, 1e-6, 'chromosome marker position');
    await consistent(candidate, expect, `${phase} chromosome`);
    record.levels.push({level: 'chromosome', length, marker_fraction: (line - 35) / 860});

    // 3. Locus: exact interval label, highlight on the coordinate axis, only frozen annotations.
    await crumbs.getByRole('button', {name: 'Locus', exact: true}).click();
    const interval = `${candidate.chromosome}:${await fmt(candidate.start + 1)}–${await fmt(candidate.end)}`;
    const locus = genome.getByRole('img', {name: `Coordinate-correct annotation view for ${interval}`});
    await locus.waitFor();
    const axis = await locus.evaluate(svg => {
      const ticks = [...svg.querySelectorAll('g')].filter(g => g.querySelector('line') && !g.querySelector('rect')).map(g => ({x: +g.querySelector('line').getAttribute('x1'), label: Number(g.querySelector('text').textContent.replaceAll(',', ''))}));
      const highlight = [...svg.querySelectorAll(':scope > rect')].find(r => r.getAttribute('stroke'));
      return {ticks, x: +highlight.getAttribute('x'), width: +highlight.getAttribute('width'), genes: [...svg.querySelectorAll('.svg-gene')].map(t => t.textContent.replace(/ [←→]$/, ''))};
    });
    const [first, last] = [axis.ticks[0], axis.ticks.at(-1)];
    const scale = (last.x - first.x) / (last.label - first.label);
    // Tick labels are rounded one-based positions, so allow about one base of rounding in pixels.
    const baseTolerance = Math.abs(scale) * 1.5 + 0.01;
    near(axis.x, first.x + (candidate.start + 1 - first.label) * scale, baseTolerance, 'locus highlight start');
    near(axis.x + axis.width, first.x + (candidate.end + 1 - first.label) * scale, Math.max(baseTolerance, 2), 'locus highlight end');
    const names = new Set((annotation?.features ?? []).flatMap(f => [f.name, f.gene_id]).filter(Boolean));
    const unknown = axis.genes.filter(name => !names.has(name));
    assert.deepEqual(unknown, [], 'locus shows genes absent from the frozen annotation window');
    await consistent(candidate, expect, `${phase} locus`);
    record.levels.push({level: 'locus', interval, tick_count: axis.ticks.length, genes_shown: axis.genes.length, genes_verified_in_frozen_window: axis.genes.length});

    // 4. Sequence: actual committed bases with one-based coordinates; step and return.
    await crumbs.getByRole('button', {name: 'Sequence', exact: true}).click();
    const strip = async shift => {
      const start = Math.max(seq.start, Math.min(candidate.start - 20 + shift, seq.end - 1));
      const expected = seq.sequence.slice(start - seq.start, start - seq.start + 100).toUpperCase();
      await genome.locator('.track-heading span').first().filter({hasText: `${seq.chromosome}:${await fmt(start + 1)}–${await fmt(start + expected.length)}`}).waitFor();
      const shown = await genome.locator('.sequence-row code').evaluateAll(rows => rows.flatMap(row => [...row.children].map(span => ({base: span.textContent, title: span.getAttribute('title'), inside: span.classList.contains('inside-candidate')}))));
      assert.equal(shown.map(s => s.base).join(''), expected, `bases at offset ${shift}`);
      for (const [index, item] of shown.entries()) {
        assert.equal(item.title, `${seq.chromosome}:${await fmt(start + index + 1)}`, `base ${index} coordinate`);
        assert.equal(item.inside, start + index >= candidate.start && start + index < candidate.end, `base ${index} candidate membership`);
      }
      return {start_zero_based: start, bases: shown.length, inside_candidate: shown.filter(s => s.inside).length};
    };
    const steps = [await strip(0)];
    await genome.getByRole('button', {name: '50 bp →'}).click();
    steps.push(await strip(50));
    await genome.getByRole('button', {name: '← 50 bp'}).click();
    steps.push(await strip(0));
    assert.match(await genome.locator('.hash-line').textContent(), new RegExp(seq.sha256));
    await consistent(candidate, expect, `${phase} sequence`);
    record.levels.push({level: 'sequence', sha256: seq.sha256, steps});

    // 5. Return to overview; selection persists and is marked on the same chromosome.
    await crumbs.getByRole('button', {name: 'Genome', exact: true}).click();
    assert.equal((await genome.locator('h2').textContent()).trim(), 'The published shortlist');
    const selectedMarker = await genome.getByRole('button', {name: `Select ${candidate.name}`}).locator('circle').evaluate(c => ({r: c.getAttribute('r'), fill: c.getAttribute('fill')}));
    assert.deepEqual(selectedMarker, {r: '7', fill: '#7ee8dd'}, 'returned overview does not mark the selected candidate');
    await consistent(candidate, expect, `${phase} return`);
    record.levels.push({level: 'return_to_overview', selected_marker: selectedMarker});
    await page.screenshot({path: `${output}/${phase}-${candidate.candidate_id}.png`});
    record.passed = true;
    checks.push(record);
  }

  try {
    await page.goto(`${base}/?run=${encodeURIComponent(runId)}`);
    await page.getByText('Ledger connected', {exact: true}).waitFor();
    await page.locator('.run-progress').filter({hasText: `${live.tasks.filter(t => t.status === 'complete').length} accepted tasks`}).waitFor();
    const liveReferences = frozen(live);
    for (const candidate of live.candidates) {
      await journey(candidate, {revision: latestRevision(live, candidate.candidate_id), dataVersion: live.run.data_version, mode: 'LIVE', reference: liveReferences[candidate.candidate_id], sequence: live.through_sequence}, 'live');
    }

    // Replay at the watermark before the evidence revision: the older assessment and the same coordinates.
    const slider = page.getByRole('slider', {name: 'Replay event position'});
    await slider.fill(String(historicalSequence));
    await page.locator('.sequence-count').filter({hasText: `${historicalSequence} / ${live.through_sequence}`}).waitFor();
    const historicalReferences = frozen(historical);
    const order = [revised, ...live.candidates.map(c => c.candidate_id).filter(id => id !== revised)];
    for (const candidateId of order) {
      const candidate = live.candidates.find(c => c.candidate_id === candidateId);
      await journey(candidate, {revision: latestRevision(historical, candidateId), dataVersion: historical.run.data_version, mode: 'RECORDED', reference: historicalReferences[candidateId], sequence: historicalSequence}, 'replay');
    }
    await page.getByRole('button', {name: 'Return live', exact: true}).click();
    await consistent(live.candidates.find(c => c.candidate_id === order.at(-1)), {revision: latestRevision(live, order.at(-1)), dataVersion: live.run.data_version, mode: 'LIVE'}, 'return live');
    assert.deepEqual(errors, []);
    const report = {ticket: 'SH-Q09', journey: 'Genome zoom truthfulness, live and in recorded replay', mode: 'deterministic_operational', mock_transport: false, model_calls: 0,
      passed: true, run_id: runId, run_created_by_journey: created, ui: base, viewport: '1280x720', data_version: live.run.data_version,
      replay: {historical_sequence: historicalSequence, evidence_revision_sequence: revisionEvent.sequence, live_sequence: live.through_sequence, revised_candidate: revised,
        historical_revision: latestRevision(historical, revised), live_revision: latestRevision(live, revised)},
      sequence_integrity: sequenceIntegrity, journeys: checks, browser_errors: errors,
      limitations: ['Deterministic operational run; no model reasoning is shown or evaluated.', 'Positions are checked after each transition starts and after 700 ms; intermediate animation frames are not individually sampled.', 'The SVG locus view shows merged gene spans, not exon models; igv.js tracks are not exercised.', `Follow camera was ${events.some(event => event.camera_cue) ? 'exercised by committed camera cues' : 'not exercised: the run has no camera cues (SH-U11 pending); rerun after cues land'}.`]};
    await writeFile(`${output}/report.json`, JSON.stringify(report, null, 2) + '\n');
    console.log(JSON.stringify({passed: true, run_id: runId, journeys: checks.length, report: `${output}/report.json`}, null, 2));
  } catch (error) {
    await page.screenshot({path: `${output}/failure.png`}).catch(() => {});
    await writeFile(`${output}/report.json`, JSON.stringify({ticket: 'SH-Q09', passed: false, run_id: runId, error: String(error?.stack ?? error), journeys: checks, browser_errors: errors}, null, 2) + '\n');
    throw error;
  } finally {
    await browser.close();
  }
}

await main();

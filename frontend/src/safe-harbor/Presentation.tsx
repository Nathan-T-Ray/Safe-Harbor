/*
 * SH-U13 — presentation mode chrome, reset-to-start, versioned dossier and replay preloading.
 * Read-only: this module fetches GET /runs/{id}/export and GET /runs/{id}/artifacts/{id}; it never
 * writes to the ledger and derives no biological verdict. Every figure shown comes from stored records.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import type { Artifact, Assessment, CommitEvent, Mode, Run, Snapshot } from '../../../shared/contracts';
import { request } from './client';
import { reconstruct, type RecordState } from './record';
import { CUE_STEPS, cueStepLabel, type Cue } from './cues';
import './presentation.css';

export interface RunExport {
  schema_version: 1; exported_at: string; mode: Mode | string; authoritative_store: string;
  snapshot: Snapshot; events: CommitEvent[]; operations: Record<string, unknown>[];
  immutable_assessment_revisions: Assessment[]; limitations: string[]; [key: string]: unknown;
}
export interface PresentationProps {
  runId: string | null;
  /** Run record as displayed (record.state.run). Its `mode` is what the ledger stored. */
  run?: Run;
  events: readonly CommitEvent[];
  /** Replay cursor; null means the live record is displayed. */
  cursor: number | null;
  lastSequence: number;
  activeCue?: Cue | null;
  /** Host resets replay/view state to sequence 0 (e.g. record.seek(0) plus clearing drawers). */
  onReset: () => void;
  onExit: () => void;
  /** Optional replay play/pause so the story can run while the timeline is scrolled out of view. */
  playing?: boolean;
  onTogglePlay?: () => void;
}

const exportCache = new Map<string, Promise<RunExport>>();
const artifactCache = new Map<string, Promise<Artifact>>();
export function fetchExport(runId: string, watermark: number): Promise<RunExport> {
  const key = `${runId}@${watermark}`;
  if (!exportCache.has(key)) { const p = request<RunExport>(`/runs/${encodeURIComponent(runId)}/export`); p.catch(() => exportCache.delete(key)); exportCache.set(key, p); }
  return exportCache.get(key)!;
}
function fetchArtifact(runId: string, artifactId: string): Promise<Artifact> {
  const key = `${runId}/${artifactId}`;
  if (!artifactCache.has(key)) { const p = request<Artifact>(`/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifactId)}`); p.catch(() => artifactCache.delete(key)); artifactCache.set(key, p); }
  return artifactCache.get(key)!;
}

export function modeWords(mode: string | undefined): { word: string; note: string; tone: 'mock' | 'deterministic' | 'model' | 'unknown' } {
  if (mode === 'real_model') return { word: 'REAL MODEL', note: 'Model tool calls and accepted conclusions are recorded.', tone: 'model' };
  if (mode === 'deterministic') return { word: 'DETERMINISTIC OPERATIONAL', note: 'Real source calculations, deterministic adapter. Not a measure of model reasoning or improvement.', tone: 'deterministic' };
  if (mode === 'mock') return { word: 'MOCK FIXTURE', note: 'Fictional interface fixture. No biological finding or model improvement.', tone: 'mock' };
  return { word: mode ? `UNRECOGNISED MODE: ${mode.toUpperCase()}` : 'NO RUN OPEN', note: mode ? 'Mode is not one of the v1 contract modes.' : 'Open or start an investigation to present its record.', tone: 'unknown' };
}
const human = (value: string) => value.replaceAll('_', ' ');
function latestByCandidate(assessments: readonly Assessment[]): Map<string, Assessment> {
  const out = new Map<string, Assessment>();
  for (const a of assessments) { const prev = out.get(a.candidate_id); if (!prev || a.assessment_revision > prev.assessment_revision) out.set(a.candidate_id, a); }
  return out;
}

type Check = { label: string; ok: boolean; detail: string };
/** Compare the exported dossier with what the screen reconstructs from the same committed events. */
function agreement(exported: RunExport, events: readonly CommitEvent[], run?: Run): Check[] {
  const watermark = exported.snapshot.through_sequence;
  const checks: Check[] = [];
  checks.push({ label: 'Mode', ok: exported.mode === (run?.mode ?? exported.snapshot.run.mode), detail: `export ${exported.mode} · screen ${run?.mode ?? 'not loaded'}` });
  const screenIds = events.filter(e => e.sequence <= watermark).map(e => e.event_id).join('|');
  const exportIds = [...exported.events].sort((a, b) => a.sequence - b.sequence).map(e => e.event_id).join('|');
  checks.push({ label: 'Committed events', ok: screenIds === exportIds, detail: `${exported.events.length} exported · ${events.filter(e => e.sequence <= watermark).length} on screen through ${watermark}` });
  let screen: RecordState | null = null;
  try { screen = reconstruct([...events], watermark); } catch (error) { checks.push({ label: 'Replay reconstruction', ok: false, detail: error instanceof Error ? error.message : String(error) }); }
  if (screen) {
    const a = latestByCandidate(screen.assessments), b = latestByCandidate(exported.snapshot.assessments);
    const keys = new Set([...a.keys(), ...b.keys()]);
    const mismatched = [...keys].filter(id => { const x = a.get(id), y = b.get(id); return !x || !y || x.assessment_id !== y.assessment_id || x.assessment_revision !== y.assessment_revision || x.screen_status !== y.screen_status || x.evidence_status !== y.evidence_status || x.freshness !== y.freshness; });
    checks.push({ label: 'Latest assessments', ok: mismatched.length === 0, detail: mismatched.length ? `differs for ${mismatched.join(', ')}` : `${keys.size} candidate${keys.size === 1 ? '' : 's'} identical (id, revision, screen, evidence, freshness)` });
    const taskDiff = exported.snapshot.tasks.filter(t => screen!.tasks.find(s => s.task_id === t.task_id)?.status !== t.status).length + Math.max(0, screen.tasks.length - exported.snapshot.tasks.length);
    checks.push({ label: 'Task states', ok: taskDiff === 0, detail: taskDiff ? `${taskDiff} task state difference${taskDiff === 1 ? '' : 's'}` : `${exported.snapshot.tasks.length} tasks identical` });
  }
  return checks;
}

interface Preload { state: 'idle' | 'loading' | 'ready' | 'error'; events: number; artifacts: number; fetched: number; missing: number; error?: string }
/** Warm the selected run's replay: export (all events + revisions), artifacts referenced but not carried inline, fonts. */
function usePreload(active: boolean, runId: string | null, events: readonly CommitEvent[], lastSequence: number): [Preload, RunExport | null, string | null, () => void] {
  const [preload, setPreload] = useState<Preload>({ state: 'idle', events: 0, artifacts: 0, fetched: 0, missing: 0 });
  const [exported, setExported] = useState<RunExport | null>(null), [exportError, setExportError] = useState<string | null>(null), [nonce, setNonce] = useState(0);
  const eventsRef = useRef(events); eventsRef.current = events;
  useEffect(() => {
    if (!active || !runId || lastSequence === 0) { setPreload(p => ({ ...p, state: 'idle' })); return; }
    let cancelled = false;
    setPreload(p => ({ ...p, state: 'loading' }));
    (async () => {
      try {
        const all = eventsRef.current;
        const inline = new Set(all.flatMap(e => e.upserts.artifacts?.map(a => a.artifact_id) ?? []));
        const referenced = new Set(all.flatMap(e => e.upserts.tasks?.flatMap(t => t.result_artifact_ids ?? []) ?? []));
        const toFetch = [...referenced].filter(id => !inline.has(id)).slice(0, 200);
        let fetched = 0, missing = 0;
        const queue = [...toFetch];
        const worker = async () => { while (queue.length && !cancelled) { const id = queue.shift()!; try { await fetchArtifact(runId, id); fetched++; } catch { missing++; } } };
        const [dossier] = await Promise.all([
          fetchExport(runId, lastSequence).then(value => { if (!cancelled) { setExported(value); setExportError(null); } return value; }, error => { if (!cancelled) setExportError(error instanceof Error ? error.message : String(error)); return null; }),
          Promise.all(Array.from({ length: 4 }, worker)),
          document.fonts?.ready,
        ]);
        if (!cancelled) setPreload({ state: dossier ? 'ready' : 'error', events: all.length, artifacts: inline.size + fetched, fetched, missing, error: dossier ? undefined : 'Dossier export unavailable' });
      } catch (error) { if (!cancelled) setPreload(p => ({ ...p, state: 'error', error: error instanceof Error ? error.message : String(error) })); }
    })();
    return () => { cancelled = true; };
  }, [active, runId, lastSequence, nonce]);
  return [preload, exported, exportError, () => { if (runId) exportCache.delete(`${runId}@${lastSequence}`); setNonce(n => n + 1); }];
}

function Dossier({ runId, exported, error, events, run, onClose, onRetry }: { runId: string; exported: RunExport | null; error: string | null; events: readonly CommitEvent[]; run?: Run; onClose: () => void; onRetry: () => void }) {
  const checks = useMemo(() => exported ? agreement(exported, events, run) : [], [exported, events, run]);
  const latest = useMemo(() => exported ? [...latestByCandidate(exported.snapshot.assessments).values()] : [], [exported]);
  const names = useMemo(() => new Map(exported?.snapshot.candidates.map(c => [c.candidate_id, c.name]) ?? []), [exported]);
  const dossiers = exported?.snapshot.artifacts.filter(a => a.kind === 'versioned_dossier') ?? [];
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => { closeRef.current?.focus(); const key = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.stopPropagation(); onClose(); } }; addEventListener('keydown', key, true); return () => removeEventListener('keydown', key, true); }, [onClose]);
  const download = () => {
    if (!exported) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(exported, null, 2)], { type: 'application/json' }));
    const link = Object.assign(document.createElement('a'), { href: url, download: `safe-harbor-${runId}-through-${exported.snapshot.through_sequence}.json` });
    link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const allAgree = checks.length > 0 && checks.every(c => c.ok);
  const words = modeWords(exported?.mode);
  return <div className="shp-dossier-layer" role="dialog" aria-modal="true" aria-labelledby="shp-dossier-title">
    <button className="shp-scrim" aria-label="Close dossier" onClick={onClose} />
    <section className="shp-dossier">
      <header className="shp-dossier-head">
        <div><span className="shp-eyebrow">Versioned dossier · read from the MongoDB ledger</span><h2 id="shp-dossier-title">Run {runId}</h2></div>
        <button ref={closeRef} className="shp-icon" onClick={onClose} aria-label="Close dossier">×</button>
      </header>
      {error && <div className="shp-notice amber" role="alert">Export failed: {error} <button onClick={onRetry}>Retry</button></div>}
      {!exported && !error && <p className="shp-muted">Loading GET /runs/{runId}/export…</p>}
      {exported && <>
        <dl className="shp-facts">
          <div><dt>Mode</dt><dd className={`shp-tone-${words.tone}`}>{words.word}</dd></div>
          <div><dt>Through commit</dt><dd>{exported.snapshot.through_sequence}</dd></div>
          <div><dt>Run status</dt><dd>{human(exported.snapshot.run.status)}</dd></div>
          <div><dt>Harness</dt><dd className="shp-mono">{exported.snapshot.run.harness_hash.slice(0, 12)}</dd></div>
          <div><dt>Assessment revisions</dt><dd>{exported.immutable_assessment_revisions.length}</dd></div>
          <div><dt>Exported</dt><dd>{new Date(exported.exported_at).toLocaleString()}</dd></div>
        </dl>
        {exported.snapshot.run.status !== 'complete' && <div className="shp-notice">Interim record: the run status is “{human(exported.snapshot.run.status)}”. This export is versioned at commit {exported.snapshot.through_sequence}, not a final shortlist.</div>}
        <h3>Screen agreement {allAgree ? <span className="shp-ok">✓ agrees</span> : <span className="shp-bad">! differs</span>}</h3>
        <ul className="shp-checks">{checks.map(c => <li key={c.label} className={c.ok ? 'ok' : 'bad'}><span>{c.ok ? '✓' : '!'} {c.label}</span><small>{c.detail}</small></li>)}</ul>
        <h3>Latest assessment per candidate</h3>
        {latest.length ? <div className="shp-assessments">{latest.map(a => <article key={a.assessment_id}>
          <header><strong>{names.get(a.candidate_id) ?? a.candidate_id}</strong><span>revision {a.assessment_revision} · {a.cell_context} · {a.assembly}</span></header>
          <dl><div><dt>Computational screen</dt><dd>{human(a.screen_status)}</dd></div><div><dt>Experimental evidence</dt><dd>{human(a.evidence_status)}</dd></div><div><dt>Freshness</dt><dd className={a.freshness === 'stale' ? 'shp-amber' : ''}>{a.freshness}</dd></div></dl>
          <p>{a.conclusion}</p>
          {a.unresolved_questions.length > 0 && <p className="shp-muted">Unresolved: {a.unresolved_questions.join(' · ')}</p>}
        </article>)}</div> : <p className="shp-muted">No assessment has been committed in this record.</p>}
        <p className="shp-muted">{dossiers.length} versioned dossier artifact{dossiers.length === 1 ? '' : 's'} · {exported.events.length} ordered events · {exported.operations.length} accepted operations</p>
        {exported.limitations.length > 0 && <><h3>Limitations</h3><ul className="shp-limitations">{exported.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul></>}
        <p className="shp-footnote">A screen pass covers named criteria only. Endpoint support is specific to assay and cell context. Neither establishes biological safety.</p>
        <footer className="shp-dossier-actions"><button className="shp-primary" onClick={download}>Download dossier JSON ↓</button><button onClick={onRetry}>Refresh export</button></footer>
      </>}
    </section>
  </div>;
}

/** Presentation chrome. Render it while presentation mode is on; it is read-only apart from host callbacks. */
export function Presentation({ runId, run, events, cursor, lastSequence, activeCue, onReset, onExit, playing, onTogglePlay }: PresentationProps) {
  const [dossierOpen, setDossierOpen] = useState(false);
  const [preload, exported, exportError, retry] = usePreload(true, runId, events, lastSequence);
  // A run's mode is frozen at creation; at replay position 0 the reconstructed run is empty, so read the committed run record.
  const words = modeWords(run?.mode ?? events[0]?.upserts.runs?.[0]?.mode);
  const live = cursor === null;
  const shown = cursor ?? lastSequence;
  const event = events.find(e => e.sequence === shown);
  useEffect(() => { document.documentElement.classList.add('shp-presenting'); return () => document.documentElement.classList.remove('shp-presenting'); }, []);
  return <>
    <section className="shp-bar" aria-label="Presentation controls">
      <div className="shp-mode" aria-live="polite">
        <span className={`shp-pill ${live ? 'live' : 'recorded'}`}>{live ? 'LIVE' : 'RECORDED REPLAY'}</span>
        <span className={`shp-pill shp-tone-${words.tone}`} title={words.note}>{words.word}</span>
        <span className="shp-where">{runId ? <>commit <b>{shown}</b> / {lastSequence}{event ? <> · {event.cause.replaceAll('.', ' · ')} · recorded {new Date(event.occurred_at).toLocaleTimeString()}</> : shown === 0 && !live ? ' · before the first committed event' : ''}</> : 'No run open'}</span>
      </div>
      <ol className="shp-story" aria-label="Camera story">{CUE_STEPS.map(step => <li key={step} className={activeCue?.step === step ? 'active' : ''}>{cueStepLabel[step]}</li>)}</ol>
      <div className="shp-actions">
        <span className={`shp-preload ${preload.state}`} title={preload.error ?? ''}>{preload.state === 'ready' ? `✓ ${preload.events} events · ${preload.artifacts} artifacts ready` : preload.state === 'loading' ? '◌ Preloading replay…' : preload.state === 'error' ? '! Preload incomplete' : '○ Nothing to preload'}</span>
        {onTogglePlay && <button onClick={onTogglePlay} disabled={!runId || !events.length} aria-label={playing ? 'Pause presentation replay' : 'Play presentation replay'}>{playing ? 'Ⅱ Pause' : '▶ Play'}</button>}
        <button onClick={onReset} disabled={!runId || !events.length} aria-label="Reset presentation to start">↤ Reset to start</button>
        <button onClick={() => setDossierOpen(true)} disabled={!runId}>Dossier</button>
        <button onClick={onExit}>Exit presentation</button>
      </div>
      <p className="shp-cue" key={activeCue?.key ?? 'none'}>{activeCue ? <>{cueStepLabel[activeCue.step]} · {activeCue.label}<small> · cue keyed to commit {activeCue.sequence}{activeCue.source === 'server' ? ' (recorded cue)' : ''}</small></> : <small>{live ? 'Camera follows recorded replay only; the live view stays where you put it.' : 'No camera cue yet at this commit.'}</small>}</p>
      <p className="shp-note">{words.note}{!live ? ' Replay rebuilds stored history; later data never appears in earlier frames.' : ''}</p>
    </section>
    {dossierOpen && runId && <Dossier runId={runId} exported={exported} error={exportError} events={events} run={run} onClose={() => setDossierOpen(false)} onRetry={retry} />}
  </>;
}

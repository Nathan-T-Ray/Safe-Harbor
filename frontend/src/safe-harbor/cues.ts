/*
 * SH-U11 — presentation-only camera cues.
 *
 * Cues are derived purely from committed ledger events (CommitEvent v1). They never invent events,
 * never read final state into earlier frames, and never touch scientific records: the only output is
 * a frozen CameraTarget that the host applies to *view* state (selected candidate, zoom level,
 * highlighted graph node / assessment). Replaying to sequence N only consults events with
 * sequence <= N.
 *
 * The camera follows one candidate thread: a switch happens only when another candidate commits bases,
 * an assessment or a branch-changing event, so interleaved workers do not make it jump every second.
 *
 * Story order inside one committed event: focus chromosome -> zoom locus -> show bases ->
 * highlight a result -> reveal the graph branch that produced it.
 */
import { useEffect, useRef, useState } from 'react';
import type { Artifact, Assessment, CommitEvent, Task } from '../../../shared/contracts';
import type { Zoom } from './Genome';

export type CueStep = 'overview' | 'focus_chromosome' | 'zoom_locus' | 'show_bases' | 'highlight_result' | 'reveal_branch';
export type CueRegion = 'genome' | 'conclusion' | 'graph';
export const CUE_STEPS: readonly CueStep[] = Object.freeze(['focus_chromosome', 'zoom_locus', 'show_bases', 'highlight_result', 'reveal_branch']);
const ORDER: Record<CueStep, number> = { overview: 0, focus_chromosome: 1, zoom_locus: 2, show_bases: 3, highlight_result: 4, reveal_branch: 5 };
export const cueStepLabel: Record<CueStep, string> = { overview: 'Genome overview', focus_chromosome: 'Focus chromosome', zoom_locus: 'Zoom locus', show_bases: 'Show reference bases', highlight_result: 'Highlight result', reveal_branch: 'Reveal graph branch' };

/** View-only camera position. `null` clears a highlight; `undefined` leaves it unchanged. */
export interface CameraTarget {
  readonly candidate_id?: string;
  readonly chromosome?: string;
  readonly zoom?: Zoom;
  readonly task_id?: string | null;
  readonly assessment_id?: string | null;
  readonly region?: CueRegion;
}
export interface Cue {
  readonly key: string;
  /** Sequence of the committed event this cue is keyed to. */
  readonly sequence: number;
  readonly event_id: string;
  readonly cause: string;
  readonly occurred_at: string;
  readonly step: CueStep;
  readonly label: string;
  readonly source: 'derived' | 'server';
  readonly target: CameraTarget;
}

type TaskRef = Pick<Task, 'task_id' | 'candidate_id' | 'kind' | 'status'>;
const LOCUS_TOOLS = new Set(['inspect_candidate', 'screen_candidate', 'gene_proximity', 'control_overlap', 'list_evidence']);
const ZOOMS = new Set<Zoom>(['genome', 'chromosome', 'locus', 'sequence']);
const record = (value: unknown): Record<string, unknown> => (value && typeof value === 'object' ? value as Record<string, unknown> : {});
const text = (value: unknown): string | undefined => (typeof value === 'string' && value ? value : undefined);
const human = (value: string) => value.replaceAll('_', ' ');

function freezeCue(cue: Cue): Cue { Object.freeze(cue.target); return Object.freeze(cue); }

/**
 * Derive the ordered, frozen cue list from committed events. Pure: the input is not mutated and the
 * output depends only on the events. Events must be the ordered committed sequence (as useRecord keeps it).
 */
export function deriveCues(events: readonly CommitEvent[]): readonly Cue[] {
  const ordered = [...events].sort((a, b) => a.sequence - b.sequence);
  const tasks = new Map<string, TaskRef>();
  const chromosomes = new Map<string, string>();
  const names = new Map<string, string>();
  const cues: Cue[] = [];
  let focused: string | undefined;

  for (const event of ordered) {
    const u = event.upserts ?? {};
    u.candidates?.forEach(c => { chromosomes.set(c.candidate_id, c.chromosome); names.set(c.candidate_id, c.name); });
    u.tasks?.forEach(t => tasks.set(t.task_id, { task_id: t.task_id, candidate_id: t.candidate_id, kind: t.kind, status: t.status }));
    const local: Omit<Cue, 'key' | 'sequence' | 'event_id' | 'cause' | 'occurred_at'>[] = [];
    const add = (step: CueStep, label: string, target: CameraTarget, source: Cue['source'] = 'derived') => local.push({ step, label, target, source });
    const nameOf = (id: string) => names.get(id) ?? id;
    const focus = (candidateId: string | undefined | null) => {
      if (!candidateId || candidateId === focused) return;
      focused = candidateId;
      const chromosome = chromosomes.get(candidateId);
      add('focus_chromosome', `${chromosome ?? 'Chromosome'} · ${nameOf(candidateId)}`, { candidate_id: candidateId, chromosome, zoom: 'chromosome', region: 'genome' });
    };
    const candidateOfArtifact = (a: Artifact) => text(record(a.data).candidate_id) ?? tasks.get(String(a.provenance?.task_id ?? ''))?.candidate_id ?? undefined;

    if (event.cause === 'run.created') {
      add('overview', 'Published shortlist on GRCh38', { zoom: 'genome', task_id: null, assessment_id: null, region: 'genome' });
    }
    // task.started commits no result, so it never moves the camera (two workers would make it ping-pong).
    // Tool results that actually committed in this event, in the order the worker recorded them.
    for (const artifact of u.artifacts ?? []) {
      if (artifact.kind !== 'scientific_tool_result') continue;
      const data = record(artifact.data), calculation = record(data.calculation);
      const tool = text(data.tool_name), candidateId = candidateOfArtifact(artifact);
      if (!tool || !candidateId) continue;
      if (LOCUS_TOOLS.has(tool)) {
        // Routine locus results for another candidate do not steal the camera; results, bases and branches do.
        if (focused && candidateId !== focused) continue;
        focus(candidateId);
        if (!local.some(c => c.step === 'zoom_locus' && c.target.candidate_id === candidateId))
          add('zoom_locus', `${nameOf(candidateId)} locus · ${human(tool)}`, { candidate_id: candidateId, zoom: 'locus', region: 'genome' });
      } else if (tool === 'reference_sequence' && typeof calculation.sequence === 'string' && calculation.sequence.length > 0) {
        focus(candidateId);
        const start = typeof calculation.start === 'number' ? calculation.start + 1 : undefined;
        add('show_bases', `${calculation.sequence.length} reference bases${start ? ` from ${text(calculation.chromosome) ?? ''}:${start.toLocaleString()}` : ''}`, { candidate_id: candidateId, zoom: 'sequence', region: 'genome' });
      }
    }
    const producing = (u.tasks ?? []).filter(t => ['complete', 'reopened', 'failed', 'blocked', 'superseded'].includes(t.status));
    // One highlight per candidate: the highest revision committed in this event.
    const newest = new Map<string, Assessment>();
    for (const a of u.assessments ?? []) { const prev = newest.get(a.candidate_id); if (!prev || a.assessment_revision > prev.assessment_revision) newest.set(a.candidate_id, a); }
    for (const a of newest.values()) {
      focus(a.candidate_id);
      add('highlight_result', `${nameOf(a.candidate_id)} · revision ${a.assessment_revision} · ${human(a.screen_status)} screen${a.freshness === 'stale' ? ' · stale' : ''}`, { candidate_id: a.candidate_id, zoom: 'locus', assessment_id: a.assessment_id, region: 'conclusion' });
    }
    // Reveal the branch that produced a result, reopened after a revision, failed, or recovered.
    const branch = event.cause === 'evidence.revised' ? producing.find(t => t.status === 'reopened') ?? producing[0]
      : (u.assessments?.length || ['task.failed', 'coordinator.recovered'].includes(event.cause) || producing.some(t => t.kind === 'publish_shortlist')) ? producing[0] : undefined;
    if (branch) {
      const reopened = (u.tasks ?? []).filter(t => t.status === 'reopened').length;
      if (branch.candidate_id) focused = branch.candidate_id;
      add('reveal_branch', event.cause === 'evidence.revised' ? `${reopened} task${reopened === 1 ? '' : 's'} reopened by evidence revision` : `${human(branch.kind)} · ${branch.status}`, { candidate_id: branch.candidate_id ?? undefined, task_id: branch.task_id, region: 'graph' });
    }
    // An explicit camera_cue committed by the server is honoured, but only its view fields.
    const server = record(event.camera_cue);
    const serverCandidate = text(server.candidate_id), serverZoom = text(server.zoom) as Zoom | undefined;
    if (serverCandidate || (serverZoom && ZOOMS.has(serverZoom))) {
      add(serverZoom === 'sequence' ? 'show_bases' : serverZoom === 'locus' ? 'zoom_locus' : serverZoom === 'genome' ? 'overview' : 'focus_chromosome', text(server.label) ?? 'Recorded camera cue', { candidate_id: serverCandidate, zoom: serverZoom && ZOOMS.has(serverZoom) ? serverZoom : undefined }, 'server');
      if (serverCandidate) focused = serverCandidate;
    }

    local.sort((a, b) => ORDER[a.step] - ORDER[b.step]).forEach((cue, index) => cues.push(freezeCue({ ...cue, key: `${event.event_id}#${index}`, sequence: event.sequence, event_id: event.event_id, cause: event.cause, occurred_at: event.occurred_at })));
  }
  return Object.freeze(cues);
}

function merge(target: CameraTarget, next: CameraTarget): CameraTarget {
  const out: { -readonly [K in keyof CameraTarget]: CameraTarget[K] } = { ...target };
  if (next.candidate_id !== undefined && next.candidate_id !== target.candidate_id) { out.assessment_id = null; out.task_id = null; }
  for (const key of Object.keys(next) as (keyof CameraTarget)[]) if (next[key] !== undefined) (out as Record<string, unknown>)[key] = next[key];
  return out;
}

/** Cues keyed to exactly this committed sequence, in story order. */
export function cuesAt(cues: readonly Cue[], sequence: number): readonly Cue[] { return cues.filter(cue => cue.sequence === sequence); }
/** Latest cue at or before the sequence (never looks ahead). */
export function latestCue(cues: readonly Cue[], sequence: number): Cue | null { let found: Cue | null = null; for (const cue of cues) { if (cue.sequence > sequence) break; found = cue; } return found; }
/** Composite camera after every cue at or before `sequence`. Sequence 0 is the genome overview. */
export function cameraAt(cues: readonly Cue[], sequence: number): CameraTarget {
  let target: CameraTarget = { zoom: 'genome', task_id: null, assessment_id: null, region: 'genome' };
  for (const cue of cues) { if (cue.sequence > sequence) break; target = merge(target, cue.target); }
  return Object.freeze(target);
}
/** Next sequence (> after) that carries a cue — useful for a "next story beat" control. */
export function nextCueSequence(cues: readonly Cue[], after: number): number | null { return cues.find(cue => cue.sequence > after)?.sequence ?? null; }

export function prefersReducedMotion(): boolean { return typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches; }
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(prefersReducedMotion);
  useEffect(() => { const query = window.matchMedia?.('(prefers-reduced-motion: reduce)'); if (!query) return; const change = () => setReduced(query.matches); query.addEventListener('change', change); return () => query.removeEventListener('change', change); }, []);
  return reduced;
}

export interface CameraFollowOptions {
  cues: readonly Cue[];
  /** Displayed committed sequence. Pass the replay cursor; `null` (live) means the camera does not move. */
  position: number | null;
  /** Follow-camera toggle. When false nothing is applied and pending steps are cancelled. */
  enabled: boolean;
  /** Applies a view-only target. Must only set UI state (selection, zoom, highlight). */
  apply: (target: CameraTarget, cue: Cue | null) => void;
  /** Delay between story steps committed in one event (ms). Default 520. Ignored under reduced motion. */
  dwellMs?: number;
  /** Time until the next event is shown during playback (ms), e.g. 1000 / speed. Steps are compressed to fit it. */
  stepBudgetMs?: number;
  /** Optional element lookup per region; the region is scrolled into view when a cue targets it. */
  regions?: Partial<Record<CueRegion, () => Element | null>>;
}
export interface CameraFollowState { activeCue: Cue | null; target: CameraTarget; reducedMotion: boolean }

/**
 * Follow controller. Single forward steps play the event's cues in story order with a short dwell;
 * seeks, backward moves and reduced-motion jump directly to the composite camera for that position.
 * Disabling follow cancels pending steps and leaves every control usable; re-enabling snaps to the
 * composite for the current position.
 */
export function useCameraFollow({ cues, position, enabled, apply, dwellMs = 520, stepBudgetMs = 1000, regions }: CameraFollowOptions): CameraFollowState {
  const reducedMotion = useReducedMotion();
  const applyRef = useRef(apply), regionsRef = useRef(regions), timers = useRef<number[]>([]);
  const seen = useRef<{ position: number | null; enabled: boolean }>({ position: null, enabled: false });
  applyRef.current = apply; regionsRef.current = regions;
  const [state, setState] = useState<{ activeCue: Cue | null; target: CameraTarget }>(() => ({ activeCue: null, target: cameraAt([], 0) }));
  // Committed events are immutable, so a new cue list (polling appends events) never changes cues at or
  // before the displayed position. Only a change of position or of the follow toggle moves the camera.
  const cuesRef = useRef(cues); cuesRef.current = cues;
  const cueCount = cues.length;

  useEffect(() => () => { timers.current.forEach(id => window.clearTimeout(id)); timers.current = []; }, []);
  useEffect(() => {
    const last = seen.current;
    if (last.position === position && last.enabled === enabled) return;
    seen.current = { position, enabled };
    timers.current.forEach(id => window.clearTimeout(id)); timers.current = [];
    if (!enabled || position === null) return;
    const all = cuesRef.current;
    const commit = (target: CameraTarget, cue: Cue | null, scroll = true) => {
      applyRef.current(target, cue);
      setState({ activeCue: cue, target });
      const region = scroll ? cue?.target.region : undefined, element = region ? regionsRef.current?.[region]?.() : null;
      element?.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'nearest' });
    };
    const steps = cuesAt(all, position);
    const singleForwardStep = last.enabled && last.position !== null && position === last.position + 1;
    if (!singleForwardStep || reducedMotion || steps.length < 2) { commit(cameraAt(all, position), latestCue(all, position)); return; }
    let target = cameraAt(all, position - 1);
    const dwell = Math.max(90, Math.min(dwellMs, (stepBudgetMs * 0.9) / steps.length));
    steps.forEach((cue, index) => {
      // Scrolling between panels several times a second is disorienting: when steps are brief only the final one scrolls.
      const run = () => { target = merge(target, cue.target); commit(Object.freeze({ ...target }), cue, dwell >= 400 || index === steps.length - 1); };
      if (index === 0) run(); else timers.current.push(window.setTimeout(run, index * dwell));
    });
  }, [position, enabled, reducedMotion, dwellMs, stepBudgetMs, cueCount]);

  return { ...state, reducedMotion };
}

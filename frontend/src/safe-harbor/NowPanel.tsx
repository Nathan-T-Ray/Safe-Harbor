/*
 * "What the agent is doing right now": focuses the running task (or the most recent committed one in replay),
 * in plain language, with the genome view zooming as cues arrive. Debounced so the focus changes calmly.
 * Everything shown is read from committed records; no verdict is derived here.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { Artifact, Candidate, Task } from '../../../shared/contracts';
import { buildAgent } from './AgentTree';
import { taskName } from './Graph';

const verb: Record<string, string> = { screen_regions: 'Screening named criteria for', inspect_evidence: 'Reading recorded evidence for', compute_features: 'Comparing expression changes for', assess_candidate: 'Drafting the assessment for', review_candidate: 'Reviewing the assessment for', publish_shortlist: 'Assembling the dossier' };
const MIN_DWELL = 4000;

function pickFocus(tasks: Task[], cueTask?: string | null): Task | undefined {
  const running = tasks.filter(t => t.status === 'running');
  if (cueTask) { const t = tasks.find(x => x.task_id === cueTask); if (t && (t.status === 'running' || !running.length)) return t; }
  if (running.length) return running[running.length - 1];
  const done = tasks.filter(t => t.status !== 'queued');
  return done[done.length - 1] ?? tasks[0];
}

function ToolIcon({ kind }: { kind: 'tool' | 'model' | 'none' }) {
  const p = { width: 22, height: 22, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true };
  if (kind === 'model') return <svg {...p}><circle cx="12" cy="12" r="8" /><path d="M8 12h8M12 8v8" /></svg>;
  if (kind === 'tool') return <svg {...p}><path d="M14.5 5.5a4 4 0 0 0-5 5L4 16l4 4 5.5-5.5a4 4 0 0 0 5-5l-2.5 2.5-3-3z" /></svg>;
  return <svg {...p}><circle cx="12" cy="12" r="8" strokeDasharray="2 3" /></svg>;
}

export function NowPanel({ tasks, artifacts, candidates, cueTaskId, genome, footer }: { tasks: Task[]; artifacts: Artifact[]; candidates: Candidate[]; cueTaskId?: string | null; genome: ReactNode; footer: ReactNode }) {
  const wanted = pickFocus(tasks, cueTaskId);
  const [shownId, setShownId] = useState<string | undefined>(wanted?.task_id);
  const last = useRef(0);
  useEffect(() => {
    if (wanted?.task_id === shownId) return;
    const wait = Math.max(0, MIN_DWELL - (Date.now() - last.current));
    const timer = setTimeout(() => { last.current = Date.now(); setShownId(wanted?.task_id); }, wait);
    return () => clearTimeout(timer);
  }, [wanted?.task_id, shownId]);
  const task = tasks.find(t => t.task_id === shownId) ?? wanted;
  const cand = candidates.find(c => c.candidate_id === task?.candidate_id);
  const agent = task ? buildAgent(task, artifacts, tasks) : undefined;
  const lastCall = agent?.calls.at(-1);
  const headline = !task ? 'Waiting for the coordinator to plan work' : task.kind === 'publish_shortlist' ? verb.publish_shortlist : `${verb[task.kind] ?? 'Working on'} ${cand?.name ?? task.candidate_id ?? 'all candidates'}`;
  const statusText = task ? (task.status === 'running' ? 'Working now' : task.status === 'complete' ? 'Most recent · complete' : task.status.replaceAll('_', ' ')) : 'Idle';
  return <section className="now-panel" aria-label="What the agent is doing now">
    <div className="now-head" key={task?.task_id ?? 'none'}>
      <span className={`now-state ${task?.status ?? 'idle'}`}><i aria-hidden="true" />{statusText}{task ? ` · ${taskName[task.kind as keyof typeof taskName] ?? task.kind}` : ''}</span>
      <h1 aria-live="polite">{headline}</h1>
      {task?.question && <p className="now-question">{task.question}</p>}
      <div className="now-tool"><span className="now-tool-icon"><ToolIcon kind={lastCall?.kind ?? 'none'} /></span><div><strong>{lastCall ? (lastCall.kind === 'model' ? 'Model call' : lastCall.label) : task?.status === 'running' ? 'Call in flight — recorded on completion' : 'No call recorded yet'}</strong><span>{lastCall?.detail ?? (cand ? `${cand.chromosome}:${(cand.start + 1).toLocaleString()} · GRCh38` : 'GRCh38 · H1')}</span></div></div>
      <div className="now-numbers"><div><strong>{agent?.hasTrace ? agent.tools : '—'}</strong><span>tool calls</span></div><div><strong>{agent?.hasTrace ? agent.models : '—'}</strong><span>model calls</span></div><div><strong>{agent?.hasTrace ? agent.tokens.toLocaleString() : '—'}</strong><span>tokens</span></div></div>
    </div>
    <div className="now-zoom">{genome}</div>
    {footer}
  </section>;
}

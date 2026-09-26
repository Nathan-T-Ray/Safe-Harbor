/*
 * Live agent tree. Built only from committed records in the displayed RecordState (live snapshot+events,
 * or replay reconstructed through the cursor), so replay never shows later work. Derives no biological verdict.
 */
import { useMemo, useRef, useState, type KeyboardEvent } from 'react';
import type { Artifact, Candidate, Run, Task } from '../../../shared/contracts';
import { taskName } from './Graph';

type Rec = Record<string, unknown>;
const rec = (v: unknown): Rec => (v && typeof v === 'object' && !Array.isArray(v) ? v as Rec : {});
const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : 0);
const stageOrder: Record<string, number> = { screen_regions: 0, inspect_evidence: 1, compute_features: 2, assess_candidate: 3, review_candidate: 4, publish_shortlist: 5 };
const statusWord: Record<string, string> = { queued: 'Queued', running: 'Running', complete: 'Complete', failed: 'Failed', blocked: 'Blocked', reopened: 'Reopened', superseded: 'Superseded' };
const canonical = (value: unknown): string => JSON.stringify(value, (_key, v: unknown) => v && typeof v === 'object' && !Array.isArray(v) ? Object.fromEntries(Object.entries(v).sort(([a], [b]) => a.localeCompare(b))) : v);

export interface CallLeaf { id: string; kind: 'model' | 'tool'; label: string; detail: string; tokens?: number; cost?: number | null; artifactId?: string }
export interface Agent { task: Task; calls: CallLeaf[]; tokens: number; tools: number; models: number; cost: number | null; hasTrace: boolean; deps: string[] }
export interface Branch { id: string; name: string; interval?: string; agents: Agent[] }

function argsSummary(args: unknown): string {
  const entries = Object.entries(rec(args));
  if (!entries.length) return 'no arguments';
  const text = entries.map(([k, v]) => `${k}=${typeof v === 'object' ? JSON.stringify(v) : String(v)}`).join(', ');
  return text.length > 70 ? `${text.slice(0, 69)}…` : text;
}

export function buildAgent(task: Task, artifacts: Artifact[], tasks: Task[]): Agent {
  const traces = artifacts.filter(a => (a.kind === 'worker_trace' || a.kind === 'worker_failure_trace') && a.provenance?.task_id === task.task_id)
    .sort((a, b) => a.created_at.localeCompare(b.created_at));
  const results = artifacts.filter(a => a.kind === 'scientific_tool_result' && a.provenance?.task_id === task.task_id);
  const calls: CallLeaf[] = []; let tokens = 0, tools = 0, models = 0, cost: number | null = 0;
  traces.forEach((trace, t) => {
    const d = rec(trace.data), usage = rec(d.usage);
    tokens += num(usage.tokens); models += num(usage.model_calls);
    if (typeof usage.cost_usd === 'number' && Number.isFinite(usage.cost_usd) && cost !== null) cost += usage.cost_usd; else cost = null;
    const responses = Array.isArray(d.provider_responses) ? d.provider_responses.map(rec) : [];
    const toolCalls = Array.isArray(d.tool_calls) ? d.tool_calls.map(rec) : [];
    const used = new Set<string>(), linked = new Set<number>();
    const addTool = (c: Rec, i: number, ordering: string) => {
      tools += 1;
      const name = String(c.tool_name ?? 'tool');
      // Repeated calls to one tool may use different arguments/results. Link
      // only an exact committed result; otherwise inspect the original trace.
      const match = results.find(a => !used.has(a.artifact_id) && a.data.tool_name === name && canonical(a.data) === canonical(c.result));
      if (match) used.add(match.artifact_id);
      calls.push({ id: `${trace.artifact_id}:t${i}`, kind: 'tool', label: name.replaceAll('_', ' '), detail: `${argsSummary(c.arguments)} · ${ordering}${traces.length > 1 ? ` · trace ${t + 1}` : ''}`, artifactId: match?.artifact_id ?? trace.artifact_id });
    };
    responses.forEach((r, i) => {
      const resp = rec(r.response), u = rec(resp.usage), callNumber = num(r.call_index) + 1;
      calls.push({ id: `${trace.artifact_id}:m${i}`, kind: 'model', label: `Model call ${callNumber}`, detail: `${String(resp.model ?? 'model')} · ${num(u.prompt_tokens).toLocaleString()} in / ${num(u.completion_tokens).toLocaleString()} out${traces.length > 1 ? ` · trace ${t + 1}` : ''}`, tokens: num(u.total_tokens), cost: typeof u.cost === 'number' ? u.cost : null, artifactId: trace.artifact_id });
      const choices = Array.isArray(resp.choices) ? resp.choices.map(rec) : [];
      const requested = choices.flatMap(choice => {const list=rec(choice.message).tool_calls; return Array.isArray(list) ? list.map(rec) : [];});
      const ids = new Set(requested.map(call => call.id).filter((id): id is string => typeof id === 'string'));
      toolCalls.forEach((call, index) => {
        if (!linked.has(index) && typeof call.model_call_id === 'string' && ids.has(call.model_call_id)) {
          linked.add(index); addTool(call, index, `requested by model call ${callNumber}`);
        }
      });
    });
    toolCalls.forEach((call, index) => {if (!linked.has(index)) addTool(call,index,responses.length ? 'provider link unavailable; relative order unrecorded' : 'recorded tool order; no model response');});
  });
  const deps = task.depends_on.map(id => tasks.find(x => x.task_id === id)).filter(Boolean).map(x => `${taskName[x!.kind]} [${x!.role_id}]${x!.candidate_id !== task.candidate_id ? ` (${x!.candidate_id ?? 'run'})` : ''}`);
  return { task, calls, tokens, tools, models, cost: traces.length ? cost : null, hasTrace: traces.length > 0, deps };
}

function StatusIcon({ status }: { status: string }) {
  const p = { width: 14, height: 14, viewBox: '0 0 16 16', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true };
  if (status === 'complete') return <svg {...p}><path d="M3 8.5l3 3 7-7" /></svg>;
  if (status === 'running') return <svg {...p}><circle cx="8" cy="8" r="5.5" strokeDasharray="4 3" /></svg>;
  if (status === 'failed' || status === 'blocked') return <svg {...p}><path d="M8 2l6.5 11.5h-13z" /><path d="M8 6.5v3M8 11.6v.1" /></svg>;
  if (status === 'reopened') return <svg {...p}><path d="M3 8a5 5 0 1 0 1.6-3.7" /><path d="M3 2.5v2.8h2.8" /></svg>;
  if (status === 'superseded') return <svg {...p}><path d="M4 12L12 4M6 4h6v6" /></svg>;
  return <svg {...p}><circle cx="8" cy="8" r="5.5" /></svg>;
}
const money = (v: number | null) => (v === null ? 'cost unreported' : `$${v.toFixed(v < 0.01 ? 5 : 3)}`);

export function deriveBranches(run: Run | undefined, tasks: Task[], artifacts: Artifact[], candidates: Candidate[]): Branch[] {
  const byId = new Map(tasks.map(task => [task.task_id, task])), depths = new Map<string, number>();
  const depth = (task: Task): number => {
    const known = depths.get(task.task_id); if (known !== undefined) return known;
    const parents = task.depends_on.map(id => byId.get(id)).filter((parent): parent is Task => Boolean(parent));
    const value = parents.length ? Math.max(...parents.map(depth)) + 1 : 0; depths.set(task.task_id, value); return value;
  };
  const ids = [...new Set([...(run?.candidate_ids ?? []), ...tasks.map(t => t.candidate_id ?? '__run')])];
  return ids.map(id => {
    const c = candidates.find(x => x.candidate_id === id);
    const agents = tasks.filter(t => (t.candidate_id ?? '__run') === id)
      .sort((a, b) => depth(a) - depth(b) || (stageOrder[a.kind] ?? 9) - (stageOrder[b.kind] ?? 9) || num(a.plan_revision) - num(b.plan_revision) || a.task_id.localeCompare(b.task_id))
      .map(t => buildAgent(t, artifacts, tasks));
    return { id, name: id === '__run' ? 'Run-wide' : c?.name ?? id, interval: c ? `${c.chromosome}:${(c.start + 1).toLocaleString()}` : undefined, agents };
  }).filter(b => b.agents.length || b.id !== '__run');
}

export function AgentTree({ run, tasks, artifacts, candidates, selectedTask, cursor, onSelectTask, onSelectArtifact }: {
  run?: Run; tasks: Task[]; artifacts: Artifact[]; candidates: Candidate[]; selectedTask?: string; cursor: number | null;
  onSelectTask: (t: Task) => void; onSelectArtifact: (a: Artifact) => void;
}) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [focusId, setFocusId] = useState('root');
  const treeRef = useRef<HTMLDivElement>(null);
  const branches = useMemo(() => deriveBranches(run, tasks, artifacts, candidates), [run, tasks, artifacts, candidates]);
  const running = tasks.filter(t => t.status === 'running');
  const budget = run?.budget; const limits = rec(run?.execution_limits);
  const modeWord = run?.mode === 'real_model' ? 'REAL MODEL' : run?.mode === 'mock' ? 'MOCK FIXTURE' : run ? 'DETERMINISTIC' : 'NO RUN';
  const where = cursor === null ? 'now' : `at commit ${cursor}`;

  // Visible treeitems in preorder, for roving focus and arrow keys.
  const order: { id: string; parent: string | null; expandable: boolean; open: boolean; act?: () => void }[] = [{ id: 'root', parent: null, expandable: false, open: true }];
  for (const b of branches) {
    const bOpen = !collapsed.has(b.id);
    order.push({ id: `b:${b.id}`, parent: 'root', expandable: true, open: bOpen });
    if (!bOpen) continue;
    for (const a of b.agents) {
      const aOpen = expanded.has(a.task.task_id);
      order.push({ id: `a:${a.task.task_id}`, parent: `b:${b.id}`, expandable: a.calls.length > 0, open: aOpen, act: () => onSelectTask(a.task) });
      if (aOpen) for (const c of a.calls) order.push({ id: `c:${c.id}`, parent: `a:${a.task.task_id}`, expandable: false, open: false, act: () => { const art = artifacts.find(x => x.artifact_id === c.artifactId); if (art) onSelectArtifact(art); else onSelectTask(a.task); } });
    }
  }
  const active = order.some(o => o.id === focusId) ? focusId : 'root';
  const move = (id: string) => { setFocusId(id); requestAnimationFrame(() => treeRef.current?.querySelector<HTMLElement>(`[data-tree-id="${CSS.escape(id)}"]`)?.focus()); };
  const toggle = (id: string) => {
    if (id.startsWith('b:')) setCollapsed(s => { const n = new Set(s); const k = id.slice(2); if (n.has(k)) n.delete(k); else n.add(k); return n; });
    if (id.startsWith('a:')) setExpanded(s => { const n = new Set(s); const k = id.slice(2); if (n.has(k)) n.delete(k); else n.add(k); return n; });
  };
  const onKey = (e: KeyboardEvent) => {
    const i = order.findIndex(o => o.id === active); const cur = order[i]; if (!cur) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); if (order[i + 1]) move(order[i + 1].id); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); if (i > 0) move(order[i - 1].id); }
    else if (e.key === 'Home') { e.preventDefault(); move(order[0].id); }
    else if (e.key === 'End') { e.preventDefault(); move(order[order.length - 1].id); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); if (cur.expandable && !cur.open) toggle(cur.id); else if (cur.open && order[i + 1]?.parent === cur.id) move(order[i + 1].id); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); if (cur.expandable && cur.open) toggle(cur.id); else if (cur.parent) move(cur.parent); }
    else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); if (cur.act) cur.act(); else if (cur.expandable) toggle(cur.id); }
  };
  const item = (id: string, level: number, extra: Record<string, unknown> = {}) => ({ role: 'treeitem', 'data-tree-id': id, tabIndex: active === id ? 0 : -1, 'aria-level': level, onFocus: () => setFocusId(id), ...extra });

  const meter = (label: string, used: number, limit: number | undefined, text: string) => {
    const pct = limit ? Math.min(100, (used / limit) * 100) : 0;
    return <div className="at-meter"><span className="at-meter-label">{label}</span><strong>{text}</strong><span className="at-bar" aria-hidden="true"><i style={{ width: `${pct}%` }} className={pct >= 85 ? 'warn' : ''} /></span></div>;
  };

  return <section className="panel agent-tree-panel" id="agent-tree" aria-label="Agent tree">
    <div className="panel-head"><div><span className="eyebrow">Who is doing the work · {cursor === null ? 'live ledger' : `replay through commit ${cursor}`}</span><h2>Agent tree</h2></div>
      <div className="at-head-actions"><span className={`at-running-chip ${running.length ? 'on' : ''}`} aria-live="polite"><span className="at-pulse" aria-hidden="true" />{running.length} / {num(limits.workers) || 2} workers running {where}</span>
        <button onClick={() => { setCollapsed(new Set()); setExpanded(new Set(tasks.map(t => t.task_id))); }}>Expand all</button>
        <button onClick={() => { setExpanded(new Set()); }}>Collapse calls</button></div></div>
    {run && <div className="at-meters">
      {meter('Tokens', budget?.tokens_used ?? 0, budget?.token_limit, `${(budget?.tokens_used ?? 0).toLocaleString()} / ${(budget?.token_limit ?? 0).toLocaleString()}`)}
      {meter('Tool calls', budget?.tool_calls ?? 0, budget?.tool_limit, `${budget?.tool_calls ?? 0} / ${budget?.tool_limit ?? 0}`)}
      {meter('Cost', budget?.cost_usd ?? 0, budget?.cost_limit_usd, `${budget?.cost_usd === null || budget?.cost_usd === undefined ? 'unreported' : `$${budget.cost_usd.toFixed(4)}`} / $${budget?.cost_limit_usd ?? 0}`)}
      {meter('Model calls', budget?.model_calls ?? 0, undefined, String(budget?.model_calls ?? 0))}
      {meter('Task nodes', tasks.length, num(limits.task_nodes) || 24, `${tasks.length} / ${num(limits.task_nodes) || 24}`)}
      {meter('Replans', num(run.replan_rounds), num(limits.replan_rounds) || 3, `${num(run.replan_rounds)} / ${num(limits.replan_rounds) || 3}`)}
    </div>}
    {!run ? <div className="empty-state">Start or open an investigation to see its coordinator, worker agents and their recorded tool and model calls.</div> :
      <div className="at-tree" role="tree" aria-label="Coordinator, candidate branches, worker agents and recorded calls" ref={treeRef} onKeyDown={onKey}>
        <div className="at-root" {...item('root', 1)}>
          <span className="at-kicker">Coordinator</span>
          <strong>{run.run_id}</strong>
          <span className="at-facts"><span className="at-chip mode">{modeWord}</span><span>epoch {run.coordinator_epoch}</span><span>{String(run.status).replaceAll('_', ' ')}</span><span>model {String(run.model_id ?? 'none · deterministic adapter')}</span><span className="mono">harness {run.harness_hash.slice(0, 10)}…</span><span>limits: ≤{num(limits.workers) || 2} workers · {num(limits.task_nodes) || 24} nodes · {num(limits.replan_rounds) || 3} replans</span></span>
        </div>
        <div className="at-branches" role="group" style={{ gridTemplateColumns: `repeat(${Math.max(1, branches.length)}, minmax(250px, 1fr))` }}>
          {branches.map(b => { const bOpen = !collapsed.has(b.id); const done = b.agents.filter(a => a.task.status === 'complete').length; return <div className="at-branch" key={b.id}>
            <div className={`at-branch-head ${active === `b:${b.id}` ? 'focus' : ''}`} {...item(`b:${b.id}`, 2, { 'aria-expanded': bOpen, onClick: () => { setFocusId(`b:${b.id}`); toggle(`b:${b.id}`); } })}>
              <span className="at-caret" aria-hidden="true">{bOpen ? '▾' : '▸'}</span><strong>{b.name}</strong><span>{b.interval ?? ''} · {done}/{b.agents.length} complete</span>
            </div>
            {bOpen && <div role="group" className="at-agents">{b.agents.map(a => { const t = a.task; const aOpen = expanded.has(t.task_id); return <div className="at-agent-wrap" key={t.task_id}>
              <div className={`at-agent ${t.status} ${selectedTask === t.task_id ? 'selected' : ''}`} {...item(`a:${t.task_id}`, 3, { 'aria-selected': selectedTask === t.task_id, ...(a.calls.length ? { 'aria-expanded': aOpen } : {}), onClick: () => { setFocusId(`a:${t.task_id}`); onSelectTask(t); }, title: t.question })}>
                <span className={`at-status ${t.status}`}>{t.status === 'running' && <span className="at-pulse" aria-hidden="true" />}<StatusIcon status={t.status} />{statusWord[t.status] ?? t.status}</span>
                <strong>{taskName[t.kind] ?? t.kind}</strong>
                <span className="at-meta">{t.role_id} · attempt {t.attempt} · plan r{num(t.plan_revision)}</span>
                <span className="at-meta">{a.hasTrace ? `${a.tools} tools · ${a.models} model · ${a.tokens.toLocaleString()} tok · ${money(a.cost)}` : t.status === 'running' ? `In flight · usage commits on completion${num(rec(t.reservation).tokens) ? ` · ≤${num(rec(t.reservation).tokens).toLocaleString()} tok reserved` : ''}` : 'No trace committed yet'}</span>
                {a.deps.length > 0 && <span className="at-dep">after {a.deps.join(', ')}</span>}
                {t.reopen_reason && <span className="at-lineage">{t.status === 'superseded' ? `Superseded by ${String(t.superseded_by ?? '').split(':').at(-1)}` : 'Reopened'}: {t.reopen_reason}</span>}
                {a.calls.length > 0 && <button type="button" tabIndex={-1} className="at-toggle" aria-hidden="true" onClick={e => { e.stopPropagation(); toggle(`a:${t.task_id}`); }}>{aOpen ? 'Hide' : 'Show'} {a.calls.length} calls</button>}
              </div>
              {aOpen && <div role="group" className="at-calls">{a.calls.map(c => <div key={c.id} className={`at-call ${c.kind}`} {...item(`c:${c.id}`, 4, { onClick: () => { setFocusId(`c:${c.id}`); const art = artifacts.find(x => x.artifact_id === c.artifactId); if (art) onSelectArtifact(art); else onSelectTask(t); } })}>
                <span className="at-call-kind">{c.kind === 'model' ? 'MODEL' : 'TOOL'}</span><strong>{c.label}</strong><span className="at-meta">{c.detail}{c.tokens !== undefined ? ` · ${c.tokens.toLocaleString()} tok` : ''}{c.kind === 'model' ? ` · ${money(c.cost ?? null)}` : ''}</span>
              </div>)}</div>}
            </div>; })}</div>}
          </div>; })}
        </div>
      </div>}
    <p className="at-footnote">Built only from committed tasks and worker traces{cursor === null ? '' : ` through commit ${cursor}; later work is not shown`}. Tasks follow dependency order, not wall-clock chronology. Tool calls follow their recorded provider request IDs; missing links are labeled. Usage per agent comes from its recorded trace; absent cost stays unreported. Arrow keys move, Right/Left expand or collapse, Enter inspects.</p>
  </section>;
}

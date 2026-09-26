/*
 * Top-down tidy tree of the investigation: coordinator → candidates → agent tasks → recorded tool/model calls.
 * Built only from the displayed RecordState (live or replay through the cursor), so no future work leaks in.
 * Deterministic layered layout (subtree widths, parents centred over children). Derives no biological verdict.
 */
import { useMemo, useRef, useState, type KeyboardEvent } from 'react';
import type { Artifact, Candidate, Run, Task } from '../../../shared/contracts';
import { deriveBranches } from './AgentTree';
import { taskName } from './Graph';

type Status = 'complete' | 'running' | 'queued' | 'planned' | 'failed' | 'blocked' | 'reopened' | 'superseded';
interface TNode { id: string; level: number; label: string; sub?: string; status: Status; tip: string; children: TNode[]; act?: () => void; x: number; y: number; w: number }
const MAX_CALLS = 5;
const statusWord: Record<Status, string> = { complete: 'Complete', running: 'Running', queued: 'Queued', planned: 'Not started', failed: 'Failed', blocked: 'Blocked', reopened: 'Reopened', superseded: 'Superseded' };
const trunc = (s: string, n: number) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);
function agg(statuses: Status[]): Status {
  if (!statuses.length) return 'planned';
  if (statuses.includes('running')) return 'running';
  if (statuses.some(s => s === 'failed' || s === 'blocked')) return 'failed';
  if (statuses.every(s => s === 'complete' || s === 'superseded')) return 'complete';
  return 'queued';
}

export function NodeGlyph({ status, r }: { status: Status; r: number }) {
  switch (status) {
    case 'complete': return <g className="tg complete"><circle r={r} className="fill-deep" /><path d={`M${-r * .42} 0l${r * .3} ${r * .32} ${r * .55}-${r * .62}`} className="mark-light" /></g>;
    case 'running': return <g className="tg running"><circle r={r + 7} className="halo" /><circle r={r} className="ring-sage" /><circle r={r * .36} className="fill-sage" /></g>;
    case 'queued': return <g className="tg queued"><circle r={r} className="ring-dashed" /></g>;
    case 'planned': return <g className="tg planned"><circle r={r} className="ring-dotted" /></g>;
    case 'failed': case 'blocked': return <g className="tg failed"><circle r={r} className="fill-char" /><path d={`M${-r * .38} ${-r * .38}L${r * .38} ${r * .38}M${r * .38} ${-r * .38}L${-r * .38} ${r * .38}`} className="mark-light" /></g>;
    case 'reopened': return <g className="tg reopened"><circle r={r} className="ring-slate" /><path d={`M${r * .45} ${-r * .1}A${r * .45} ${r * .45} 0 1 1 ${r * .1} ${-r * .45}M${r * .1} ${-r * .7}v${r * .3}h${r * .3}`} className="mark-dark" /></g>;
    case 'superseded': return <g className="tg superseded"><circle r={r} className="ring-slate" /><path d={`M${-r * .8} ${r * .8}L${r * .8} ${-r * .8}`} className="mark-dark" /></g>;
  }
}

export function TreeLegend() {
  const items: Status[] = ['complete', 'running', 'queued', 'planned', 'failed', 'reopened', 'superseded'];
  return <ul className="tree-legend" aria-label="Node status legend">{items.map(s => <li key={s}><svg width="22" height="22" viewBox="-11 -11 22 22" aria-hidden="true"><NodeGlyph status={s} r={6} /></svg>{statusWord[s]}</li>)}</ul>;
}

export function TreeChart({ run, tasks, artifacts, candidates, selectedTask, cursor, onSelectTask, onSelectArtifact }: {
  run?: Run; tasks: Task[]; artifacts: Artifact[]; candidates: Candidate[]; selectedTask?: string; cursor: number | null;
  onSelectTask: (t: Task) => void; onSelectArtifact: (a: Artifact) => void;
}) {
  const [hover, setHover] = useState<TNode | null>(null);
  const [focusId, setFocusId] = useState('root');
  const svgRef = useRef<SVGSVGElement>(null);
  const { flat, width, height } = useMemo(() => {
    const branches = deriveBranches(run, tasks, artifacts, candidates);
    const cands: TNode[] = branches.map(b => {
      const agents: TNode[] = b.agents.map(a => {
        const t = a.task;
        const shown = a.calls.slice(0, MAX_CALLS);
        const calls: TNode[] = shown.map(c => ({ id: `c:${c.id}`, level: 3, label: c.kind === 'model' ? 'model' : trunc(c.label, 14), status: 'complete' as Status, tip: `${c.kind === 'model' ? 'Model call' : 'Tool call'} · ${c.label} · ${c.detail}`, children: [], x: 0, y: 0, w: 30, act: () => { const art = artifacts.find(x => x.artifact_id === c.artifactId); if (art) onSelectArtifact(art); else onSelectTask(t); } }));
        if (a.calls.length > MAX_CALLS) calls.push({ id: `c:${t.task_id}:more`, level: 3, label: `+${a.calls.length - MAX_CALLS}`, status: 'complete', tip: `${a.calls.length - MAX_CALLS} more recorded calls · open inspector`, children: [], x: 0, y: 0, w: 30, act: () => onSelectTask(t) });
        const status = t.status as Status;
        return { id: `a:${t.task_id}`, level: 2, label: taskName[t.kind as keyof typeof taskName] ?? t.kind, sub: `${t.role_id} · ${statusWord[status] ?? t.status}`, status, tip: `${taskName[t.kind as keyof typeof taskName] ?? t.kind} · ${statusWord[status] ?? t.status} · ${t.question}`, children: calls, x: 0, y: 0, w: 118, act: () => onSelectTask(t) };
      });
      const done = b.agents.filter(a => a.task.status === 'complete').length;
      return { id: `b:${b.id}`, level: 1, label: b.name, sub: `${done}/${b.agents.length} done`, status: agg(agents.map(a => a.status)), tip: `${b.name}${b.interval ? ` · ${b.interval}` : ''} · ${done}/${b.agents.length} tasks complete`, children: agents, x: 0, y: 0, w: 140 };
    });
    const runStatus: Status = !run ? 'planned' : run.status === 'complete' ? 'complete' : ['failed', 'blocked', 'budget_exhausted'].includes(run.status) ? 'failed' : 'running';
    const root: TNode = { id: 'root', level: 0, label: 'Coordinator', sub: run ? String(run.status).replaceAll('_', ' ') : 'not started', status: runStatus, tip: run ? `Coordinator · ${run.run_id} · epoch ${run.coordinator_epoch}` : 'No run', children: cands, x: 0, y: 0, w: 160 };
    // Candidate columns contain tasks in topological order; edges below use recorded dependencies.
    const colW = 220; root.x = (cands.length * colW) / 2; root.y = 34;
    cands.forEach((c, i) => { c.x = i * colW + 40; c.y = 120; c.children.forEach((a, j) => { a.x = c.x; a.y = 200 + j * 64; a.children.forEach((k, m) => { k.x = a.x + 26 + m * 15; k.y = a.y + 32; }); }); });
    root.w = cands.length * colW;
    const flat: TNode[] = []; const walk = (n: TNode) => { flat.push(n); n.children.forEach(walk); }; walk(root);
    const height = Math.max(260, ...flat.map(n => n.y + 40));
    return { root, flat, width: Math.max(root.w, 480), height };
  }, [run, tasks, artifacts, candidates, onSelectArtifact, onSelectTask]);
  const nodesById = new Map(flat.map(node => [node.id, node]));
  const edges: [TNode, TNode][] = [];
  flat.forEach(node => {
    if (node.level !== 1) node.children.forEach(child => edges.push([node, child]));
    else node.children.forEach(child => {
      const task = tasks.find(item => `a:${item.task_id}` === child.id);
      const parents = (task?.depends_on ?? []).map(id => nodesById.get(`a:${id}`)).filter((parent): parent is TNode => Boolean(parent));
      if (parents.length) parents.forEach(parent => edges.push([parent, child]));
      else edges.push([node, child]);
    });
  });
  const active = flat.some(n => n.id === focusId) ? focusId : 'root';
  const onKey = (e: KeyboardEvent) => {
    const i = flat.findIndex(n => n.id === active); let next: TNode | undefined;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = flat[i + 1]; else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = flat[i - 1];
    else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); flat[i]?.act?.(); return; } else return;
    e.preventDefault(); if (next) { setFocusId(next.id); requestAnimationFrame(() => svgRef.current?.querySelector<SVGGElement>(`[data-node="${CSS.escape(next!.id)}"]`)?.focus()); }
  };
  const radius = [16, 13, 11, 6];
  return <section className="tree-panel" aria-label="Agent tree chart">
    <div className="tree-head"><div><span className="eyebrow">Who is doing the work · {cursor === null ? 'live' : `replay through commit ${cursor}`}</span><h2>Investigation tree</h2></div><TreeLegend /></div>
    {!run ? <div className="empty-state">Start or open an investigation to grow the tree.</div> :
      <div className="tree-canvas">
        <svg ref={svgRef} role="tree" aria-label="Coordinator, candidates, agent tasks and recorded calls" viewBox={`-10 0 ${width + 20} ${height}`} preserveAspectRatio="xMidYMin meet" onKeyDown={onKey}>
          <g className="tree-edges">{edges.map(([a, b]) => <line key={`${a.id}:${b.id}`} data-dependency-source={a.level===2&&b.level===2?a.id.slice(2):undefined} data-dependency-target={a.level===2&&b.level===2?b.id.slice(2):undefined} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className={`edge ${b.status}`} />)}</g>
          {flat.map(n => <g key={n.id} data-node={n.id} role="treeitem" aria-level={n.level + 1} aria-label={n.tip} aria-selected={selectedTask !== undefined && n.id === `a:${selectedTask}`} tabIndex={active === n.id ? 0 : -1}
            className={`tnode l${n.level} ${n.id === `a:${selectedTask}` ? 'selected' : ''}`} style={{ transform: `translate(${n.x}px, ${n.y}px)` }}
            onFocus={() => { setFocusId(n.id); setHover(n); }} onBlur={() => setHover(null)} onMouseEnter={() => setHover(n)} onMouseLeave={() => setHover(null)} onClick={() => { setFocusId(n.id); n.act?.(); }}>
            <g className="tnode-in"><NodeGlyph status={n.status} r={radius[n.level]} />
              {n.level < 3 ? n.level === 2 ? <><text x={20} y={-2} className="tlabel">{trunc(n.label, 22)}</text><text x={20} y={14} className="tsub">{n.sub}</text></> : <><text y={-radius[n.level] - (n.level ? 22 : 10)} textAnchor="middle" className="tlabel">{trunc(n.label, 22)}</text>{n.sub && <text y={-radius[n.level] - (n.level ? 7 : -48)} textAnchor="middle" className="tsub">{n.sub}</text>}</>
                : <text y={20} textAnchor="middle" className="tcall">{n.label.startsWith('+') ? n.label : ''}</text>}
            </g>
          </g>)}
        </svg>
        {hover && <div className="tree-tip" role="status" style={{ left: `${(hover.x + 10) / (width + 20) * 100}%`, top: `${hover.y / height * 100}%` }}>{hover.tip}</div>}
      </div>}
    <p className="tree-foot">Built only from committed tasks and traces{cursor === null ? '' : ` through commit ${cursor}`}. Task-to-task lines are recorded dependencies; candidate and call lines group records. Arrow keys move · Enter inspects.</p>
  </section>;
}

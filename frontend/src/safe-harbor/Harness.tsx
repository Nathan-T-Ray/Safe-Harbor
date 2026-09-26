import { useEffect, useState } from 'react';
import type { Evaluation, HarnessVersion } from '../../../shared/contracts';
import { request } from './client';
import { JsonRecord } from './Inspector';

type SavedRecord = Record<string, unknown>;
const record = (value: unknown): SavedRecord => value && typeof value === 'object' && !Array.isArray(value) ? value as SavedRecord : {};
const records = (value: unknown): SavedRecord[] => Array.isArray(value) ? value.map(record) : [];
const number = (value: unknown, suffix=''): string => typeof value === 'number' ? `${value.toLocaleString(undefined,{maximumFractionDigits:4})}${suffix}` : 'Unknown';
const money = (value: unknown): string => typeof value === 'number' ? `$${value.toFixed(6)}` : 'Unknown';

function ComparisonReport({report}: {report:SavedRecord}) {
  const promotion=record(report.promotion), optimizer=record(report.optimizer);
  const optimizerUsage=record(report.optimizer_overhead), totals=record(report.combined_run_and_optimizer_usage);
  const arms=records(report.arms), cases=records(report.case_results);
  const operations=records(record(optimizer.patch).operations);
  return <section className="comparison-report">
    <div className="artifact-heading"><h3>Measured comparison</h3><span className="pill">{String(report.mode??'Unconfigured').replaceAll('_',' ')}</span></div>
    <div className="notice"><strong>{String(promotion.status??'Selection pending').replaceAll('_',' ')}</strong><p>{Array.isArray(promotion.reasons)?promotion.reasons.join(' '):String(promotion.reason??'No promotion decision has been accepted.')}</p>{promotion.cost_conclusion_provisional===true&&<p>Single paired cost comparison · provisional.</p>}</div>
    {operations.length>0&&<section><h3>What the proposal changed</h3><ol className="patch-list">{operations.map((operation,index)=><li key={index}><strong>{String(operation.op).replaceAll('_',' ')}</strong><span>{String(operation.role_id??operation.after_role_id??operation.from_role_id??'')}</span><JsonRecord value={operation} label="Exact executable operation"/></li>)}</ol><p className="muted small">{String(optimizer.rationale??'')}</p></section>}
    {arms.length>0?<div className="table-scroll"><table><thead><tr><th>Split / arm</th><th>Required answers</th><th>Unsupported</th><th>Completed</th><th>Tokens</th><th>Model / tool calls</th><th>Cost</th></tr></thead><tbody>{arms.map((arm,index)=>{const usage=record(arm.usage);return <tr key={index}><td>{String(arm.split)} · <strong>{String(arm.arm)}</strong></td><td>{number(arm.required_correct)} / {number(arm.required_total)}</td><td>{number(arm.unsupported_count)}</td><td>{number(arm.completed_case_count)} / {number(arm.assigned_case_count)}</td><td>{number(usage.tokens)}</td><td>{number(usage.model_calls)} / {number(usage.tool_calls)}</td><td>{money(usage.cost_usd)}</td></tr>;})}</tbody></table></div>:<p className="muted small">No scored arm results have been accepted.</p>}
    <div className="comparison-overhead"><div><span>Optimizer overhead</span><strong>{money(optimizerUsage.cost_usd)}</strong><small>{number(optimizerUsage.tokens)} tokens · {number(optimizerUsage.model_calls)} calls</small></div><div><span>Runs + optimizer total</span><strong>{money(totals.cost_usd)}</strong><small>{number(totals.tokens)} tokens · {number(totals.duration_seconds,' s')} summed duration</small></div></div>
    <p className="small muted">Unknown usage prevents a cost-win claim. Evaluator overhead is reported separately; summed run durations are not elapsed experiment time.</p>
    <JsonRecord value={report.evaluation_overhead??null} label="Measured evaluator overhead"/>
    {cases.length>0&&<details className="source-table"><summary>All assigned case outcomes · including failures ({cases.length})</summary><div className="table-scroll"><table><thead><tr><th>Case / split</th><th>Arm</th><th>Outcome</th><th>Required answers</th><th>Coverage</th><th>Stored run</th></tr></thead><tbody>{cases.map((item,index)=>{const score=record(item.score);return <tr key={index}><td>{String(item.case_id)}<br/>{String(item.split)}</td><td>{String(item.arm)}</td><td>{String(item.status)}</td><td>{number(score.required_correct)} / {number(score.required_total)}</td><td>{typeof score.coverage==='number'?`${Math.round(score.coverage*100)}%`:'Unknown'}</td><td>{typeof item.run_id==='string'?<a href={`/?run=${encodeURIComponent(item.run_id)}`}>Inspect run ↗</a>:'Not executed'}</td></tr>;})}</tbody></table></div></details>}
    {Array.isArray(report.limitations)&&<details className="raw-record"><summary>Scope and limitations</summary>{report.limitations.map((item,index)=><p className="report-limitation" key={index}>{String(item)}</p>)}</details>}
    <JsonRecord value={report} label="Exact comparison report, cases and usage"/>
  </section>;
}

export function Harness({versions,evaluations,hash,onClose}:{versions:HarnessVersion[];evaluations:Evaluation[];hash?:string;onClose:()=>void}) {
  const [experimentId,setExperimentId]=useState(()=>localStorage.getItem('safe-harbor-experiment')??'');
  const [experiment,setExperiment]=useState<SavedRecord|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState<string|null>(null),[mode,setMode]=useState<'real_model'|'deterministic'>('real_model'),[openId,setOpenId]=useState('');
  useEffect(()=>{
    let active=true,polling=false;setExperiment(null);setError(null);
    if(!experimentId)return;
    async function poll(){if(polling||!active)return;polling=true;try{const next=await request<SavedRecord>(`/experiments/${encodeURIComponent(experimentId)}`);if(active){setExperiment(next);setError(null);}}catch(e){if(active)setError(e instanceof Error?e.message:String(e));}finally{polling=false;}}
    void poll();const timer=setInterval(()=>void poll(),1000);return()=>{active=false;clearInterval(timer);};
  },[experimentId]);
  const openExperiment=(id:string)=>{if(!id.trim())return;setExperimentId(id.trim());localStorage.setItem('safe-harbor-experiment',id.trim());};
  const start=async()=>{setBusy(true);setError(null);try{const created=await request<SavedRecord>('/experiments',{mode});const id=String(created.experiment_id??created.evaluation_id??'');if(!id)throw new Error('Experiment creation returned no record ID');openExperiment(id);}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}};
  const liveVersions=records(experiment?.harness_versions).filter(value=>Array.isArray(value.roles)) as unknown as HarnessVersion[];
  const availableVersions=[...new Map([...versions,...liveVersions].map(version=>[version.harness_hash,version])).values()];
  const acceptedReports=evaluations.filter(evaluation=>evaluation.type==='harness_comparison_report').map(evaluation=>record(evaluation.report));
  const liveReport=record(experiment?.report);
  return <aside className="harness-drawer" role="dialog" aria-modal="true" aria-label="Harness evolution">
    <div className="drawer-head"><div><span className="eyebrow">The workflow is part of the experiment</span><h2>Harness evolution</h2></div><button onClick={onClose} aria-label="Close harness comparison">×</button></div>
    <p className="muted">Versions are frozen per run. A real model proposes one bounded structural patch from development traces. Validation selects or rejects it; final cases stay outside selection.</p>
    <section className="experiment-controls"><div className="artifact-heading"><h3>Comparison experiment</h3><span className="pill live">Separate live record</span></div><p className="small muted">H0: competent fixed agent · R0: all checks + synthesis · H1: automatic proposal. This experiment record is separate from the investigation replay position.</p><div className="experiment-actions"><select aria-label="Experiment execution mode" value={mode} onChange={event=>setMode(event.target.value as 'real_model'|'deterministic')}><option value="real_model">Real model comparison</option><option value="deterministic">Deterministic operational only</option></select><button disabled={busy} onClick={()=>void start()}>{busy?'Starting…':'Start comparison'}</button></div><form className="experiment-actions" onSubmit={event=>{event.preventDefault();openExperiment(openId);}}><input aria-label="Saved experiment ID" placeholder="Open a saved experiment ID" value={openId} onChange={event=>setOpenId(event.target.value)}/><button disabled={!openId.trim()}>Open</button></form>{error&&<p role="alert" className="notice amber">{error}</p>}{experiment&&<div className="notice"><strong>{String(experiment.status??'Pending').replaceAll('_',' ')}</strong><p>{String(experiment.blocked_reason??experiment.reason??(Array.isArray(experiment.blockers)?experiment.blockers.join(' '):'Every assigned case and actual usage remains inspectable.'))}</p><span className="hash-line">{experimentId}</span></div>}</section>
    {Object.keys(liveReport).length>0&&<ComparisonReport report={liveReport}/>}
    {acceptedReports.filter(report=>!liveReport.experiment_id||report.experiment_id!==liveReport.experiment_id).map((report,index)=><ComparisonReport key={index} report={report}/>)}
    {availableVersions.length?availableVersions.map(version=><section className="harness-version" key={version.harness_hash}><div className="artifact-heading"><h3>{version.name}</h3><span className="pill">{version.harness_hash===hash?'This run':'Saved experiment version'}</span></div><p className="small">Proposal: {version.proposal_mode} · {version.roles.length} executable roles</p><div className="harness-roles">{version.roles.map(role=><div key={role.role_id}><strong>{role.role_id}</strong><span>{role.kind.replaceAll('_',' ')}</span><small>After: {role.depends_on.join(', ')||'Start'}</small><small>Context: {role.context_policy}</small><small>Tools: {role.allowed_tools.join(', ')||'Synthesis only'}</small></div>)}</div>{version.patch?<JsonRecord value={version.patch} label="Exact structural patch"/>:<p className="small muted">Fixed baseline · no proposed patch</p>}<JsonRecord value={version.immutable_constraints} label="Frozen scientific and evaluation constraints"/><div className="hash-line">{version.harness_hash}</div></section>):<p className="empty-state">No committed harness specification at this event or in the selected experiment.</p>}
    {!acceptedReports.length&&!Object.keys(liveReport).length&&<div className="notice">No comparison report has been accepted. No improvement is claimed.</div>}
    {experiment&&<><JsonRecord value={experiment.optimizer_response_artifact??null} label="Original optimizer response and exact proposal input"/><JsonRecord value={experiment} label="Complete saved experiment record"/></>}
  </aside>;
}

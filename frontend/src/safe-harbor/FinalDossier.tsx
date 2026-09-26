import type {Artifact, Assessment, Candidate, Run, Task} from '../../../shared/contracts';

const object=(value:unknown):Record<string,unknown>=>value&&typeof value==='object'&&!Array.isArray(value)?value as Record<string,unknown>:{};
const human=(value:unknown)=>typeof value==='string'?value.replaceAll('_',' '):'Not recorded';

// The report stage stores a separate validated summary inside an immutable
// dossier artifact. It does not update the earlier assessment collection.
export function FinalDossier({run,candidate,tasks,artifacts,assessment,onInspect}:{run?:Run;candidate?:Candidate;tasks:Task[];artifacts:Artifact[];assessment?:Assessment;onInspect:(artifact:Artifact)=>void}) {
  if(!run||!candidate)return null;
  const dossier=artifacts.filter(artifact=>artifact.kind==='versioned_dossier'&&artifact.run_id===run.run_id&&artifact.data.candidate_id===candidate.candidate_id)
    .sort((a,b)=>b.created_at.localeCompare(a.created_at)||b.artifact_id.localeCompare(a.artifact_id))[0];
  if(!dossier)return null;
  const summary=object(dossier.data.validated_summary);
  const producer=tasks.find(task=>task.task_id===dossier.provenance.task_id);
  const versions=object(run.evidence_versions);
  const readSet=[...dossier.input_read_set,...(Array.isArray(summary.input_read_set)?summary.input_read_set.map(object):[])];
  const changed=readSet.filter(read=>typeof read.key!=='string'||!Object.hasOwn(versions,read.key)||versions[read.key]!==read.version);
  const producerCurrent=producer?.status==='complete'&&!producer.superseded_by&&producer.kind==='publish_shortlist'&&producer.result_artifact_ids?.includes(dossier.artifact_id)&&producer.harness_hash===run.harness_hash;
  const contextMatches=summary.run_id===run.run_id&&summary.candidate_id===candidate.candidate_id&&summary.assembly===run.assembly&&summary.cell_context===run.cell_context;
  const fresh=Boolean(producerCurrent&&contextMatches&&readSet.length&&changed.length===0&&summary.freshness==='current');
  const accepted=summary.model_proposal_accepted===true&&Array.isArray(summary.validation_errors)&&summary.validation_errors.length===0;
  const label=!fresh?'Historical dossier · current evidence not confirmed':accepted?'Final dossier · proposal accepted':'Final dossier · proposal rejected';
  return <section className="panel final-dossier-panel" aria-label="Stored final dossier summary" data-artifact-id={dossier.artifact_id} data-current={fresh} data-accepted={accepted}>
    <div className="panel-head"><div><span className="eyebrow">Separate final report stage</span><h2>{label}</h2></div><span className="pill">Summary revision {String(summary.assessment_revision??'unrecorded')}</span></div>
    <div className="final-dossier-body">
      <p className="final-dossier-stage">{assessment?`Earlier assessment stage remains revision ${assessment.assessment_revision}${assessment.model_proposal_accepted===false?' · proposal rejected / unresolved':''}.`:'No earlier assessment is recorded.'} The report-stage summary below is stored separately; it does not replace that history.</p>
      {fresh?<><div className="status-axes"><div><span>Computational screen</span><strong>{human(summary.screen_status)}</strong></div><div><span>Experimental evidence</span><strong>{human(summary.evidence_status)}</strong></div><div><span>Evidence freshness</span><strong>{human(summary.freshness)}</strong></div></div>
        <p className="final-dossier-conclusion">{typeof summary.conclusion==='string'?summary.conclusion:'No conclusion was recorded.'}</p>
        {Array.isArray(summary.unresolved_questions)&&summary.unresolved_questions.length>0&&<details><summary>Remaining questions ({summary.unresolved_questions.length})</summary><ul>{summary.unresolved_questions.map((question,index)=><li key={index}>{String(question)}</li>)}</ul></details>}
      </>:<p className="notice amber">This stored dossier is not presented as a current conclusion. {changed.length?`${new Set(changed.map(read=>String(read.key))).size} consumed input versions are changed or unavailable at this commit.`:'Its producer, context or freshness is no longer confirmed at this commit.'} Inspect the exact historical artifact below.</p>}
      <button onClick={()=>onInspect(dossier)}>Inspect exact final dossier artifact</button>
      <p className="scientific-footnote">Proposal acceptance records schema and evidence validation. It does not establish biological safety. Current eligibility uses only this replay state's producer and consumed input versions.</p>
      <code className="artifact-id">{dossier.artifact_id}</code>
    </div>
  </section>;
}

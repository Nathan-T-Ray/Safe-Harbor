"""Read-only actual API/ledger-output audit, independent of worker validators."""
import argparse, json
from pathlib import Path
import requests
from safe_harbor.evaluation.reference_answers import load_reference
parser=argparse.ArgumentParser(description='Read-only E2E audit of actual accepted API/Mongo investigation records against independent references; performs no model calls or writes.')
parser.add_argument('--base-url',required=True)
target=parser.add_mutually_exclusive_group(required=True)
target.add_argument('--experiment-id')
target.add_argument('--run-id',help='Audit a separate full-source demonstration; never contributes comparison scores.')
parser.add_argument('--output',required=True)
args=parser.parse_args()
p={'base_url':args.base_url.rstrip('/'),'experiment_id':args.experiment_id,'output':args.output}
Path(p['output']).mkdir(parents=True,exist_ok=True)
if args.experiment_id:
 e=requests.get(p['base_url']+'/experiments/'+p['experiment_id'],timeout=15).json()
else:
 snapshot=requests.get(p['base_url']+'/runs/'+args.run_id+'/snapshot',timeout=15).json()
 for candidate in snapshot['run']['candidate_ids']:
  if snapshot['run'].get('evidence_availability',{}).get(candidate,{}).get('control_evidence') is not True:
   parser.error('The standalone demonstration audit requires full control availability.')
 e={'evaluation_id':None,'status':snapshot['run']['status'],'results':[{'run_id':args.run_id,'candidate_id':candidate,'case_id':candidate+'--full_sources','arm':'selected_harness_demonstration'} for candidate in snapshot['run']['candidate_ids']]}
required={'outside_gene_body','tss_distance','mirna_distance','lncrna_distance','cancer_gene_distance','outside_dhs_buffer','outside_ultraconserved_regions'}
findings=[];checked=[]
for row in e['results']:
 if not row.get('run_id'):continue
 s=requests.get(p['base_url']+'/runs/'+row['run_id']+'/snapshot',timeout=15).json()
 ref=load_reference(row['case_id']);tasks={t['task_id']:t for t in s['tasks']};artifacts={a['artifact_id']:a for a in s['artifacts']}
 records = [('assessment_collection', a) for a in s.get('assessments',[])] + [('validated_final_dossier', x['data']['validated_summary']) for x in s['artifacts'] if x['kind']=='versioned_dossier' and x.get('data',{}).get('validated_summary')]
 for record_kind, a in records:
  if args.run_id and a['candidate_id']!=row['candidate_id']:continue
  errors=[];criteria={x['criterion_id']:x['status'] for x in a['criterion_results']}
  if len(criteria)!=len(a['criterion_results']):errors.append('duplicate criterion IDs')
  values=[criteria.get(k,'incomplete') for k in required]
  aggregate='incomplete' if 'incomplete' in values else 'fail' if 'fail' in values else 'pass'
  if a['screen_status']!=aggregate:errors.append('aggregate contradicts required criteria')
  if a['evidence_status']!='unknown':errors.append('unsupported endpoint status in current casepack')
  if a['candidate_id']!=row['candidate_id'] or a['assembly']!='GRCh38' or a['cell_context']!='H1 human embryonic stem cells':errors.append('candidate/assembly/context mismatch')
  proposal_artifacts=[x for x in s['artifacts'] if (x['kind']=='assessment_proposal' and x['data'].get('assessment',{}).get('assessment_id')==a['assessment_id']) or (x['kind']=='versioned_dossier' and x['data'].get('validated_summary',{}).get('assessment_id')==a['assessment_id'])]
  if not proposal_artifacts:errors.append('accepted assessment missing immutable proposal artifact')
  closure=set();frontier=[x['provenance']['task_id'] for x in proposal_artifacts];visited=set()
  while frontier:
   tid=frontier.pop();t=tasks.get(tid)
   if not t or tid in visited:continue
   visited.add(tid);closure.update(t.get('result_artifact_ids',[]));frontier.extend(t.get('depends_on',[]))
  permitted={f"{row['run_id']}:source-manifest",f"{row['run_id']}:reference:{row['candidate_id']}"}|closure
  known=set(permitted)
  for aid in permitted:
   x=artifacts.get(aid,{})
   known.update(x.get('evidence_ids',[]));known.update(x.get('data',{}).get('evidence_ids',[]))
  unknown=set(a.get('evidence_ids',[]))-known
  if unknown:errors.append('assessment cites IDs outside own dependency/source scope: '+','.join(sorted(unknown)))
  if a.get('freshness')=='current':
   if any(s['run']['evidence_versions'].get(read['key'])!=read['version'] for read in a.get('input_read_set',[])):errors.append('current assessment consumes stale versions')
   for key,value in a.get('numerical_findings',{}).items():
    if value is None:continue
    expected=ref['required_numbers'].get(key)
    if expected is None or type(value) not in (int,float) or abs(value-expected)>ref.get('tolerances',{}).get(key,0):errors.append('reported number disagrees with independently recomputed case reference: '+key)
    citations=a.get('numerical_evidence',{}).get(key,[])
    if not citations or set(citations)-known:errors.append('numerical finding lacks scoped evidence: '+key)
  if not a.get('model_proposal_accepted') and (a.get('exclusion_decision')!='unresolved' or any(v is not None for v in a.get('numerical_findings',{}).values())):errors.append('rejected proposal escaped conservative unknown fallback')
  if a.get('model_proposal_accepted') and a.get('validation_errors'):errors.append('accepted proposal carries validation errors')
  item={'record_kind':record_kind,'case_id':row['case_id'],'arm':row['arm'],'run_id':row['run_id'],'assessment_id':a['assessment_id'],'model_proposal_accepted':a.get('model_proposal_accepted'),'screen_status':a['screen_status'],'evidence_status':a['evidence_status'],'independently_expected_aggregation':aggregate,'errors':errors}
  checked.append(item)
  if errors:findings.append(item)
report={'audit_kind':'read_only_actual_accepted_assessment_integrity','experiment_id':e['evaluation_id'],'run_id':args.run_id,'experiment_status':e['status'] if args.experiment_id else None,'run_status':e['status'] if args.run_id else None,'complete_experiment_audit':bool(args.experiment_id and e['status'] in ['complete','operational_complete']),'complete_demonstration_audit':bool(args.run_id and e['status'] in ['complete','failed','budget_exhausted','stopped']),'accepted_assessments_checked':len(checked),'assessment_collection_records':sum(a['record_kind']=='assessment_collection' for a in checked),'validated_final_dossiers':sum(a['record_kind']=='validated_final_dossier' for a in checked),'valid_model_proposals':sum(a['model_proposal_accepted'] is True for a in checked),'findings':findings,'passed_so_far':not findings,'assessments':checked,'scope':'Independent seven-criterion aggregation, context, own-run dependency/source IDs, evidence versions, independent raw-file numerical references and rejected-proposal fallback. No production validator or arithmetic tool imported.','limitations':['No complete semantic audit of freeform prose.','This read-only record audit does not itself demonstrate rejection of forged submissions; the independent transactional acceptance E2E verifies that boundary.','Standalone demonstration records are excluded from frozen comparison scores.']}
Path(p['output'],'assessment-integrity-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('assessments','scope','limitations')}))

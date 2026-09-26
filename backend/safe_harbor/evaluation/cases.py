"""Frozen public scenario assignments; numerical answer records are evaluator-only."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVALUATOR = ROOT/'data/safe_harbor/evaluator'
OBJECTIVE = 'Do these measured expression changes justify excluding this candidate region?'


def load_cases(split: str | None = None) -> list[dict]:
    package = json.loads((EVALUATOR/'splits.json').read_text())
    if split not in (None,'development','validation','final'):
        raise ValueError('Unknown evaluation split')
    return [case for case in package['cases'] if split is None or case['split']==split]


def freeze() -> dict:
    # Three loci, nine audit cases. Variants of a locus never cross splits.
    manifest = json.loads((ROOT/'data/safe_harbor/normalized/manifest.json').read_text())
    criteria = ROOT/'data/safe_harbor/normalized/criteria.json'
    scenarios = {
        'full_sources':'Use the available H1 tables, untargeted controls and GRCh38 annotations. State what the calculations can and cannot establish.',
        'controls_withheld':'The original untargeted-control evidence is unavailable under a prepared availability revision. Missing control results are not zero biological changes. Investigate the remaining H1 evidence and preserve uncertainty.',
        'h1_context_only':'The question is about H1. H9 is a different experimental context and cannot automatically establish an H1 endpoint. Use H1 evidence and state this applicability limit.',
    }
    cases = []
    for candidate,split in [('pansio-1','development'),('olonne-18','validation'),('keppel-19','final')]:
        for scenario,instruction in scenarios.items():
            cases.append({'case_id':f'{candidate}--{scenario}','candidate_id':candidate,'scenario_id':scenario,
                'split':split,'group_id':f'published-locus:{candidate}','assembly':'GRCh38',
                'cell_context':'H1 human embryonic stem cells','data_version':manifest['data_version'],
                'objective':OBJECTIVE,'question':OBJECTIVE+' '+instruction,'instructions':instruction,
                'controls_available':scenario!='controls_withheld',
                'evidence_revision_fixture':'withhold-control-evidence' if scenario=='controls_withheld' else None})
    payload = {'schema_version':1,'cases':cases,'source_family':'Autio eLife79592 shared-source audit',
               'grouping':'All variants of each candidate locus stay together; only one distinct locus per split.',
               'limitations':['Nine audit cases are not nine independent biological studies.',
                   'Three source loci are insufficient for broad biological generalization.',
                   'No human reference-answer review has been performed.'],
               'criteria_sha256':hashlib.sha256(criteria.read_bytes()).hexdigest(),
               'promotion_rule':{'no_decline':['required_answer_accuracy','support','coverage'],
                   'additional_benefit':'more correct required decisions OR >=15% provider-reported cost reduction at equal quality',
                   'cost_reduction_fraction':0.15,'require_complete_usage_for_cost':True,
                   'deterministic_runs_eligible_for_model_improvement':False,'single_paired_cost_result':'provisional'}}
    payload['split_hash'] = hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return payload


if __name__=='__main__':
    EVALUATOR.mkdir(parents=True,exist_ok=True)
    package = freeze()
    path = EVALUATOR/'splits.json'
    if path.exists() and json.loads(path.read_text()) != package:
        raise SystemExit('Refusing to overwrite frozen case assignments; version explicitly before changing comparisons')
    path.write_text(json.dumps(package,indent=2)+'\n')
    print(json.dumps({'cases':len(package['cases']),'split_hash':package['split_hash'],'groups_per_split':1}))

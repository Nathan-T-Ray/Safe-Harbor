#!/usr/bin/env python3
"""SH-Q12 read-only claim audit over committed data and artifacts.

Data-integrity check only: imports no production code, makes no model calls,
writes nothing except its own report. Run from the repository root:

    python3 artifacts/safe_harbor/claim-audit/verify_claims.py
"""
import collections
import glob
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

OUT = Path('artifacts/safe_harbor/claim-audit/read-only-integrity.json')
CMP = 'artifacts/safe_harbor/real-model-comparison'
EXP_OLD = f'{CMP}/experiment-5d8ef28995924af7b65ab6ef4deb3273'
EXP_NEW = f'{CMP}/experiment-a879d0fa4f5e499b89a43ed8b7f7f400'
R0_RUN = 'artifacts/safe_harbor/real-model-preflight/run-1c38545496844fcb858df0892a3df064'
H0_RUN = 'artifacts/safe_harbor/real-model-preflight/run-fd79f621f4444f47aae814434998c3b9'
RECOVERY = 'artifacts/safe_harbor/pr66-runtime-repair/recovery-after'


def load(path):
    with open(path) as stream:
        return json.load(stream)


report = {
    'journey': 'SH-Q12 read-only claim audit',
    'mode': 'read_only_artifact_audit',
    'model_calls': 0,
    'imports_production_code': False,
    'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'recorded_at': datetime.now(timezone.utc).isoformat(),
    'checks': [],
}


def check(name, passed, detail):
    report['checks'].append({'name': name, 'passed': bool(passed), 'detail': detail})


# --- Science inputs -------------------------------------------------------
cands = {c['candidate_id']: c for c in load('data/safe_harbor/normalized/candidates.json')}
refs = load('data/safe_harbor/normalized/reference_assets.json')
expr = load('data/safe_harbor/normalized/expression.json')
manifest = load('data/safe_harbor/normalized/manifest.json')
source_hashes = {s['source_id']: s['sha256'] for s in manifest['sources']}

for cid, cand in cands.items():
    src = cand['source_coordinates']
    check(f'coordinates:{cid}',
          cand['start'] == src['start'] - 1 and cand['end'] == src['end'] and src['width'] == cand['end'] - cand['start'],
          {'internal_half_open': [cand['chromosome'], cand['start'], cand['end']],
           'source_one_based_closed': [src['start'], src['end']], 'width': src['width']})
    check(f'source_hash_chain:{cid}', source_hashes.get(src['source_id']) == src['sha256'],
          {'source': src['source_id'], 'sheet': src['sheet'], 'row': src['row']})

for cid, ref in refs.items():
    seq = ref['sequence']
    bases = seq['sequence']
    cand = cands[cid]
    digests = {hashlib.sha256(bases.encode()).hexdigest(), hashlib.sha256(bases.upper().encode()).hexdigest()}
    check(f'reference_window:{cid}',
          len(bases) == seq['end'] - seq['start'] and seq['start'] <= cand['start'] and seq['end'] >= cand['end']
          and seq['chromosome'] == cand['chromosome'] and set(bases.lower()) <= set('acgtn')
          and seq['sha256'] in digests and seq['personalized_h1_genome'] is False,
          {'length': len(bases), 'window': [seq['start'], seq['end']],
           'sha256_matches_bases': seq['sha256'] in digests, 'personalized_h1_genome': seq['personalized_h1_genome']})

check('source_manifest', len(source_hashes) == 15,
      {'sources': len(source_hashes), 'raw_source_bytes_committed': bool(glob.glob('data/safe_harbor/raw/*')),
       'note': 'Raw bytes are not in git, so original-file hashes cannot be re-derived from this checkout.'})

controls = {g['gene_id_version'] for g in expr['H1']['untargeted']}
counts = {}
for cid in ('pansio-1', 'olonne-18', 'keppel-19'):
    ids = {g['gene_id_version'] for g in expr['H1'][cid]}
    counts[cid] = {'de': len(ids), 'shared_with_untargeted': len(ids & controls), 'untargeted': len(controls)}
check('h1_counts_recomputed_from_normalized_tables',
      [counts[c]['de'] for c in counts] == [96, 111, 139]
      and [counts[c]['shared_with_untargeted'] for c in counts] == [31, 40, 48] and len(controls) == 260, counts)

thresholds = manifest['input_contract']['thresholds']
violations = sum(1 for key in expr['H1'] for g in expr['H1'][key]
                 if not (abs(g['log2_fold_change']) >= thresholds['abs_log2_fold_change_gte'] and g['fdr'] <= thresholds['fdr_lte']))
check('h1_tables_significant_only', violations == 0, {'rows_outside_thresholds': violations, 'thresholds': thresholds})

splits = load('data/safe_harbor/evaluator/splits.json')
by_split = collections.defaultdict(set)
for case in splits['cases']:
    by_split[case['split']].add(case['candidate_id'])
check('split_one_locus_each', len(splits['cases']) == 9 and all(len(v) == 1 for v in by_split.values()),
      {k: sorted(v) for k, v in by_split.items()})

# --- Real-model preflights ------------------------------------------------
for label, path, arm in (('r0', R0_RUN, 'R0'), ('h0', H0_RUN, 'H0')):
    rep = load(f'{path}/report.json')
    bud, score = rep['budget'], rep['score']
    check(f'{label}_preflight_recorded', rep['mode'] == 'real_model' and rep['arm'] == arm,
          {'purpose': rep['purpose'], 'tokens': bud['tokens_used'], 'model_calls': bud['model_calls'],
           'tool_calls': bud['tool_calls'], 'cost_usd': bud['cost_usd'],
           'required_correct': f"{score['required_correct']}/{score['required_total']}",
           'support_ok': score['support_ok'], 'unsupported': score['unsupported_findings']})

export = load(f'{R0_RUN}/run-export.json')
seqs = [e['sequence'] for e in export['events']]
check('r0_export_event_order',
      seqs == list(range(1, len(seqs) + 1)) and [e['sequence'] for e in export['events'] if e['upserts'].get('assessments')] == [9],
      {'events': len(seqs), 'assessment_first_at': [e['sequence'] for e in export['events'] if e['upserts'].get('assessments')],
       'causes': [e['cause'] for e in export['events']]})
check('coordinator_recovered_is_startup_not_crash',
      export['events'][1]['cause'] == 'coordinator.recovered'
      and {t.get('coordinator_epoch') for e in export['events'] for t in e['upserts'].get('tasks', []) if t.get('coordinator_epoch')} == {1},
      {'note': 'Every exported run records coordinator.recovered at startup (epoch 1). It is not evidence of crash recovery.'})

# --- Comparison experiments ----------------------------------------------
for path in (EXP_OLD, EXP_NEW):
    exp = load(f'{path}/latest-experiment.json')
    scored = [{'case': r['case_id'], 'arm': r['arm'], 'status': r['status'],
               'required': f"{r['score']['required_correct']}/{r['score']['required_total']}",
               'decisions': f"{r['score']['required_decisions_correct']}/{r['score']['required_decisions_total']}",
               'completed': r['score']['completed'], 'support_ok': r['score']['support_ok'],
               'tokens': r['usage'].get('tokens'), 'cost_usd': r['usage'].get('cost_usd')}
              for r in exp['results'] if r.get('score')]
    check(f"experiment_has_no_candidate:{exp['experiment_id']}",
          exp['arms'].get('H1') is None and exp.get('optimizer') is None and exp.get('promotion') is None,
          {'status_in_latest_record': exp['status'], 'updated_at': exp['updated_at'],
           'result_status_counts': dict(collections.Counter(f"{r['split']}/{r['arm']}/{r['status']}" for r in exp['results'])),
           'scored': scored})

aborted = load(f'{EXP_OLD}/experiment-aborted.json')
latest_old = load(f'{EXP_OLD}/latest-experiment.json')
check('old_experiment_abort_recorded', aborted['status'] == 'aborted_configuration_failure',
      {'aborted_record_status': aborted['status'], 'latest_experiment_status': latest_old['status'],
       'note': 'latest-experiment.json still says running_development; experiment-aborted.json is the terminal record.'})

frozen = load(f'{EXP_NEW}/frozen-manifest.json')
check('new_experiment_manifest_unchanged', frozen == load(f'{EXP_NEW}/latest-experiment.json')['comparison_manifest'],
      {'comparison_manifest_hash': load(f'{EXP_NEW}/latest-experiment.json')['comparison_manifest_hash']})

# Model tool choices inside the fixed H0 graph, and the H0 controls-withheld failure.
choices = {}
for run_path in sorted(glob.glob(f'{EXP_NEW}/runs/*.json')):
    run = load(run_path)
    snap = run['snapshot']
    if snap['run'].get('baseline_arm') != 'H0':
        continue
    case = snap['run']['case_context']['case_id']
    choices[case] = {
        'status': snap['run']['status'],
        'replan_rounds': snap['run'].get('replan_rounds'),
        'roles': {a['data'].get('role_id'): [c.get('tool') or c.get('name') or c.get('tool_name') for c in a['data'].get('tool_calls', []) if isinstance(c, dict)]
                  for a in snap['artifacts'] if a['kind'] in ('worker_trace', 'worker_failure_trace')},
        'failures': [str(a['data'].get('error'))[:160] for a in snap['artifacts'] if a['kind'] == 'worker_failure_trace'],
    }
check('h0_model_tool_choices',
      bool(choices) and all(name for c in choices.values() for calls in c['roles'].values() for name in calls),
      choices)

# --- Recovery -------------------------------------------------------------
rec = load(f'{RECOVERY}/report.json')
sigkill = load(f'{RECOVERY}/e2e-recovery-cd5628af28f64646a4695f0dba0a6d58.export.json')
epochs = sorted({t.get('coordinator_epoch') for e in sigkill['events'] for t in e['upserts'].get('tasks', []) if t.get('coordinator_epoch')})
kill = next(c for c in rec['checks'] if c['check'] == 'sigkill:killed_mid_execution')
stale_paths = [r['export'] for r in rec['runs'].values() if not Path(r['export']).exists()]
check('recovery_sigkill_export',
      rec['passed'] and rec['model_calls'] == 0 and kill['evidence']['exit_code'] == -9 and epochs == [1, 2]
      and [e['sequence'] for e in sigkill['events']] == list(range(1, len(sigkill['events']) + 1))
      and sigkill['snapshot']['run']['status'] == 'complete',
      {'mode': rec['mode'], 'exit_code': kill['evidence']['exit_code'], 'epochs': epochs, 'events': len(sigkill['events']),
       'report_paths_missing_in_checkout': stale_paths,
       'note': 'Exports exist beside the report; the report still names the pre-rename pr66-review directory and process logs are not committed.'})

# --- Harness adaptation ---------------------------------------------------
opt = load(f'{EXP_OLD}/optimizer-attempt.json')
check('optimizer_attempt_rejected', opt.get('status') == 'rejected_invalid_proposal' and not opt.get('candidate_hash'),
      {'status': opt.get('status'), 'error': opt.get('error'),
       'tokens': opt['usage']['tokens'], 'cost_usd': opt['usage']['cost_usd']})
adapt = load('artifacts/safe_harbor/adaptation-e2e/report.json')
check('adaptation_e2e_blocked_on_genuine_proposal', adapt['summary']['failed'] == 0 and adapt['summary']['blocked'] == 2,
      {'mode': adapt['execution_mode'], 'passed': adapt['summary']['passed'], 'blocked': adapt['summary']['blocked_checks']})

check('no_q11_canonical_artifact', not glob.glob('artifacts/**/*q11*', recursive=True) and not glob.glob('artifacts/**/canonical*', recursive=True),
      {'note': 'No canonical Q11 recording is committed.'})

report['passed'] = all(c['passed'] for c in report['checks'])
report['summary'] = {'checks': len(report['checks']), 'failed': [c['name'] for c in report['checks'] if not c['passed']]}
OUT.write_text(json.dumps(report, indent=2) + '\n')
for c in report['checks']:
    print('PASS' if c['passed'] else 'FAIL', c['name'])
print(json.dumps(report['summary']))

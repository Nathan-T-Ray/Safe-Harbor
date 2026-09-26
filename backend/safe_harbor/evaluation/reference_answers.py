"""Evaluator-only reference recomputation directly from original files.

This module does not import production science calculations or use normalized
answers. Workers cannot invoke it through their approved tool interfaces.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / 'data/safe_harbor/raw'
EVALUATOR = ROOT / 'data/safe_harbor/evaluator'
LIM = ['significant_only_tables', 'reference_not_personal_h1', 'control_overlap_not_causality',
       'distance_not_safety', 'missing_cancer_regulatory_evidence', 'unmapped_de_ids']
SHEETS = {'pansio-1': 'Pansio-1 (113339961-113340514)',
          'olonne-18': 'Olônne-18 (56534775-56536439)',
          'keppel-19': 'Keppel-19 (5400761-5402139)'}


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _gap(a, b, c, d):
    """Empty coordinate gap for two half-open intervals; independent integer arithmetic."""
    return max(c-b, a-d, 0)


def _base_distance(a, b, p):
    return a-p if p < a else p-b+1 if p >= b else 0


def recompute() -> dict:
    workbook = openpyxl.load_workbook(RAW/'elife-79592-supp5.xlsx', read_only=True, data_only=True)
    source_loci = openpyxl.load_workbook(RAW/'elife-79592-supp1.xlsx', read_only=True, data_only=True)['overlap safe-active']
    source_rows = list(source_loci.values)
    def read_sheet(name):
        sheet = workbook[name]
        rows = list(sheet.values)
        assert rows[0][0] == 'ensembl_gene_id_version'
        assert str(rows[0][1]).endswith('_DEseq_LFC') and str(rows[0][3]).endswith('_DEseq_FDR')
        selected = {}
        raw_ids = []
        for row_number, row in enumerate(rows[1:], 2):
            if not row[0]:
                continue
            raw_ids.append(row[0])
            if abs(float(row[1])) >= 1 and float(row[3]) <= 0.01:
                selected[row[0]] = {'lfc': float(row[1]), 'fdr': float(row[3]), 'row': row_number}
        return selected, [key for key, count in Counter(raw_ids).items() if count > 1]
    controls, control_duplicates = read_sheet('WT H1')
    attributes = {}
    with gzip.open(RAW/'wgEncodeGencodeAttrsV36.txt.gz', 'rt') as stream:
        for line in stream:
            fields = line.rstrip('\n').split('\t')
            if len(fields) != 14:
                raise ValueError('Unexpected GENCODE attributes schema')
            attributes[fields[4]] = (fields[0].split('.')[0], fields[1], fields[2])
    canonical = {f'chr{x}' for x in range(1,23)} | {'chrX','chrY','chrM'}
    genes, tss = {}, []
    for source in ['wgEncodeGencodeCompV36.txt.gz','wgEncodeGencodePseudoGeneV36.txt.gz']:
        with gzip.open(RAW/source, 'rt') as stream:
            for line_number, line in enumerate(stream,1):
                f = line.rstrip('\n').split('\t')
                if len(f) != 16:
                    raise ValueError('Unexpected GENCODE transcript schema')
                if f[2] not in canonical:
                    continue
                gene, name, kind = attributes[f[1]]
                start, end = int(f[4]), int(f[5])
                key = (gene,f[2])
                if key in genes:
                    genes[key]['start'] = min(genes[key]['start'], start)
                    genes[key]['end'] = max(genes[key]['end'], end)
                else:
                    genes[key] = {'gene_id':gene,'chromosome':f[2],'name':name,'start':start,'end':end,'gene_type':kind}
                tss.append({'chromosome':f[2],'position':start if f[3]=='+' else end-1,
                            'gene_id':gene,'transcript_id':f[1], 'source':source,'row':line_number})
    raw_names = ['elife-79592-supp1.xlsx','elife-79592-supp5.xlsx','wgEncodeGencodeAttrsV36.txt.gz',
                 'wgEncodeGencodeCompV36.txt.gz','wgEncodeGencodePseudoGeneV36.txt.gz']
    source_hashes = {name:_hash(RAW/name) for name in raw_names}
    answers = {}
    for candidate_id, sheet in SHEETS.items():
        chromosome, start1, end = re.search(r'-(\d+) \((\d+)-(\d+)\)', sheet).groups()
        start, end = int(start1)-1, int(end)
        chromosome = 'chr'+chromosome
        matches = [(i+1,row) for i,row in enumerate(source_rows) if row[0]==chromosome[3:] and row[1]==start+1 and row[2]==end]
        assert len(matches)==1 and matches[0][1][3] == end-start, 'Coordinates do not cross-match source width'
        target, duplicates = read_sheet(sheet)
        shared = set(target) & set(controls)
        stable = {key.split('.')[0] for key in target}
        mapped = {key[0] for key in genes if key[0] in stable}
        local = [g for g in genes.values() if g['chromosome']==chromosome]
        de_local = [g for g in local if g['gene_id'] in stable]
        nearest = min(local, key=lambda g:(_gap(start,end,g['start'],g['end']),g['start'],g['gene_id']))
        nearest_de = min(de_local, key=lambda g:(_gap(start,end,g['start'],g['end']),g['start'],g['gene_id']))
        nearest_tss = min((t for t in tss if t['chromosome']==chromosome), key=lambda t:(_base_distance(start,end,t['position']),t['position'],t['transcript_id']))
        numbers = {'de_count':len(target),'control_de_count':len(controls),'shared_de_count':len(shared),
                   'targeted_only_count':len(set(target)-set(controls)),'overlap_fraction':len(shared)/len(target),
                   'min_gene_body_gap_bp':_gap(start,end,nearest['start'],nearest['end']),
                   'min_tss_base_distance_bp':_base_distance(start,end,nearest_tss['position']),
                   'mapped_de_count':len(mapped),
                   'nearest_mapped_de_gene_gap_bp':_gap(start,end,nearest_de['start'],nearest_de['end'])}
        answers[candidate_id] = {'candidate_id':candidate_id, 'assembly':'GRCh38', 'cell_context':'H1 human embryonic stem cells',
            'required_numbers':numbers,'source_hashes':source_hashes,
            'source_rows':{'candidate_sheet':sheet,'candidate_rows':[v['row'] for v in target.values()],
                           'control_sheet':'WT H1','control_rows':[v['row'] for v in controls.values()],
                           'supplement_1_sheet':'overlap safe-active','supplement_1_row':matches[0][0]},
            'independent_diagnostics':{'duplicate_candidate_ids':duplicates,'duplicate_control_ids':control_duplicates,
                'gene_count':len(genes),'unmapped_de_ids':sorted(stable-mapped),'nearest_gene':nearest,
                'nearest_mapped_de_gene':nearest_de,'nearest_tss':nearest_tss,'shared_gene_ids':sorted(shared)},
            'review_status':'independently_computed_not_human_reviewed',
            'justification':['Counts and intersections recomputed from original XLSX rows without production science imports or source shared flags.',
                'Distances recomputed with independent integer interval formulas from both original UCSC transcript tables and attribute IDs.',
                'Significant-only tables have no full measured-gene denominator. Control overlap and mapped proximity do not establish causality or global safety.',
                'No source-backed DE-count threshold requires exclusion. Overall suitability remains uncertain because required screens lack evidence.']}
    return {'schema_version':1,'reference_method':'independent_raw_file_recomputation','source_hashes':source_hashes,
            'human_reviewed':False,'answers':answers}


def load_reference(case_id: str) -> dict:
    from .cases import load_cases
    case = next((case for case in load_cases() if case['case_id']==case_id), None)
    if case is None:
        raise KeyError('Unknown frozen evaluation case')
    package = json.loads((EVALUATOR/'reference_answers.json').read_text())
    base = package['answers'][case['candidate_id']]
    expected = json.loads(json.dumps(base))
    expected.update({key:case[key] for key in ['case_id','scenario_id','split','group_id']})
    expected['tolerances'] = {'overlap_fraction':1e-9}
    expected['required_limitations'] = LIM.copy()
    decisions = {'exclusion_decision':['not_justified_by_available_evidence','unresolved'],
                 'screen_status':'incomplete','evidence_status':['unknown','conflicting']}
    if case['scenario_id']=='controls_withheld':
        for name in ['control_de_count','shared_de_count','targeted_only_count','overlap_fraction']:
            expected['required_numbers'].pop(name)
        expected['unavailable_numbers'] = ['control_de_count','shared_de_count','targeted_only_count','overlap_fraction']
        expected['required_limitations'].append('controls_unavailable')
        decisions['exclusion_decision'] = ['unresolved']
    if case['scenario_id']=='h1_context_only':
        expected['required_limitations'].append('cell_context_not_transferable')
    if case['candidate_id']=='keppel-19':
        expected['required_limitations'].append('source_count_discrepancy')
    expected['required_decisions'] = decisions
    expected['rubric_notes'] = ['Unresolved and non-exclusion are both admissible with accurate calculations and explicit scope; no staged rank reversal.',
        'A conflicting label requires a named actual contradiction; a count discrepancy alone is not proof of a conflicting biological endpoint.']
    return expected


if __name__ == '__main__':
    EVALUATOR.mkdir(parents=True,exist_ok=True)
    package = recompute()
    (EVALUATOR/'reference_answers.json').write_text(json.dumps(package,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({key:value['required_numbers'] for key,value in package['answers'].items()},indent=2))

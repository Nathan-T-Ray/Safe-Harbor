# Automatic structure proof

The model-generated change is saved **and has executed**. Validation and promotion remain separate; consult the timestamped [report](report.json) for their observed status. This inspection made no model calls or ledger writes.

- Experiment: `experiment-a879d0fa4f5e499b89a43ed8b7f7f400`.
- [Parent](parent-harness.json): `2562bbd42027f9ec415163ca479978a862d087aed54be2c1d83ef28c63c58e5d`, six roles.
- [Candidate](candidate-harness.json): `453e57dd9f41b0cb35120608d3670cceaf8b15be4ce7e2c84684d65cb6097124`, seven roles.
- [Original optimizer response](optimizer-response.json): one actual model call, 11,969 tokens, $0.00342986, 83.994899 seconds. The raw JSON patch equals the saved candidate patch; content/request hashes and development-only provenance are checked in the report.
- First H1 validation run: `run-5134783b07da40f2b6ac5c6b053bf901`, Olônne-18, real model. [Stored export](run-5134783b07da40f2b6ac5c6b053bf901.export.json).
- Event **11** accepts the new `inspect_evidence` role. Event **12** starts the new `evidence_review` role; event **15** accepts it. Event **16** starts downstream `compare`.
- Reviewer trace `artifact-8b1749f667294b108ed8fc3e013d8a92` records two provider responses, `contradictions_first` context selection, and an actual model-requested `control_overlap` call. That tool was moved from `compare` to the new reviewer by the exact automatic patch.

This proves changed executable topology, role context, and tool assignment, not improved answer quality. The new role instructions contain literal `[shared_instruction:...]` markers copied by the model; the evidence preserves them exactly. The optimizer's rationale is a proposed explanation, not an established cause. No patch repair or extra retry was inserted into this recording.

[inspect_recorded_execution.py](inspect_recorded_execution.py) only reads existing MongoDB records and GET exports, then writes local audit copies. It does not invoke production compiler/worker functions, run unit/component tests, mutate a ledger, or dispatch a paid call. The report records pending execution checks until the corresponding committed traces exist.

# Independent comparison arithmetic audit

Read [report.json](report.json) for the timestamp and current status. `pending` is not an audit pass. The recorder waits for the experiment and its final report to be complete before comparing arithmetic.

[audit_recorded_report.py](audit_recorded_report.py) reads the actual experiment API and checks:

- Every frozen case/arm assignment remains present, including failures and invalid final answers.
- Per-arm required-answer counts, denominator, accuracy, unsupported claims, coverage, and supported completion agree with the stored case records.
- Per-arm and complete-run token/tool/model/cost/duration totals agree with stored usage; partial known totals and completeness flags remain distinct.
- Optimizer overhead is included in run-plus-optimizer totals, and evaluator overhead/duration remains separately inspectable.
- The selection's validation cost sums and reduction fraction agree arithmetically with its assigned rows; a rejected candidate does not acquire an improvement or cost-win claim in the report.

The inspection imports no evaluator, scorer, runtime, harness, or scientific module. It makes no model call, creates no run, and writes no ledger record. It independently aggregates existing numbers; it does not recompute biological answers or score them. Arithmetic agreement is not proof of scientific correctness, evidence support, generalization, or improvement. Raw workflow completion remains distinct from the evaluator's supported-completion field.

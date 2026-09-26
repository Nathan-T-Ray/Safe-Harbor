# Withheld-control trace review

**Observed outcome: H1 repeated the failure the optimizer intended to address.** This is a read-only review of recorded real-model execution, not a rescore or a new experiment. [Report and exact references](report.json).

| Role in review | Run | Failed inventory role | Failure time (UTC) |
|---|---|---|---|
| H0 development trace cited by optimizer | `run-dc78b257a27a4d7b967d7814cc7259f5` (Pansio-1) | `inspect` | 2026-09-26 19:42:25.550456 |
| H0 matched validation case | `run-d6e1befd83154d239fdfeab61b2eaefe` (Olônne-18) | `inspect` | 2026-09-26 19:53:41.351791 |
| H1 matched validation case | `run-e9b7d35c48e245a7ace4dce1f77e10d2` (Olônne-18) | `inspect_evidence` | 2026-09-26 19:53:56.884584 |

All three recorded paths have the same relevant sequence: commit **3** applies withheld availability before dispatch; **6** starts the inventory role; **10** records its failure; **12** stops the run as blocked. The initial context already says `control_evidence=false`, with expression scope version **2**.

The first provider response batches `list_evidence`, candidate `table_slice`, and untargeted `table_slice`. The first two tools return; the unavailable untargeted lookup raises `PermissionError`. The inventory result labels the control table unavailable, but the model selected all these requests in the same response. Do **not** claim it first read the inventory result and then ignored it in a later turn.

The failed request uses an allowed tool name with an unavailable contrast. It is not an unapproved tool, and the denied request returns no successful control measurement. The H1 added `evidence_review` task depends on the failed inventory, so it never starts. Both matched validation runs produce **zero assessments and zero versioned dossiers**. Structural execution was demonstrated on the separate full-source H1 case; this withheld-control case demonstrates a failure to avoid the intended stopping condition.

Matched H0/H1 records agree on case question/context, model/settings/provider-price hash, source/query/criteria versions, availability and assigned budget. Their harnesses differ. Derived artifact IDs remain run-specific. This one observed pair cannot identify the causal effect of individual instruction fragments, role splitting, model randomness, or tool-error handling, and it cannot establish population performance. No promotion decision or improvement claim is made here.

Each `*.failure-artifact.json` is the exact immutable failure artifact, including original context, provider requests, completed tool results and measured failed-call usage. Each `*.events-tasks.json` keeps exact event envelopes and task records; larger artifact contents are referenced by ID/hash. Original timestamps and hashes are preserved. Full Data-owned run exports were not duplicated. The capture script only reads GET endpoints and writes these local review artifacts; it does not score, dispatch, call a model, or mutate the ledger.

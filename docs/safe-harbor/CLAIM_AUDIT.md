# SH-Q12 adversarial claim audit

Audited 2026-09-26 against `main` at `7faa458` and the committed artifacts. The latest experiment snapshot is from 19:53:58 UTC. Auditor: `kiro-critic`, read-only. No production code was changed or imported, no model calls were made and no ledger was written. Machine-checkable findings are in [read-only-integrity.json](../../artifacts/safe_harbor/claim-audit/read-only-integrity.json). Rerun them with `python3 artifacts/safe_harbor/claim-audit/verify_claims.py` (30/30 checks pass; each check tests what the artifact *records*, not whether the claim is good).

**Verdict: NOT SIGNED OFF.** SH-Q11 has produced no canonical recording, so no final pitch exists to certify. Of the specification's seven demo segments, six are supported within stated scope. The seventh (automatic patch plus measured promotion) is **half supported**. A genuine model-generated structural change exists and really executed. **No promotion, selection, held-out result or improvement exists.** Validation is still running, and so far the proposed version (H1) has not outperformed the fixed baselines.

**Independence:** other Kiro sessions authored the SH-Q06 and SH-Q10 journeys. Those rows are therefore not independent certification. The auditor wrote no runtime, science, harness or UI code.

## The four questions

| Question | Answer from the artifacts |
|---|---|
| Did the harness change? | **Yes, automatically. Retention is undecided.** The first optimizer call was [rejected](../../artifacts/safe_harbor/real-model-comparison/experiment-5d8ef28995924af7b65ab6ef4deb3273/optimizer-attempt.json) with empty output. The second is [`candidate_ready`](../../artifacts/safe_harbor/automatic-structure-proof/optimizer-attempt.json): mode `real_model`, 11,969 tokens, $0.00342986, and a response ending with `finish_reason: stop` that contains both operations (`split_role` on `inspect`, `reassign_tools`). Independent checks confirm the binding. The candidate hash `453e57dd…` can be re-derived from the saved specification with canonical JSON. That hash equals the experiment's `H1` arm. Its parent equals `H0`, and the immutable constraints are byte-identical to the parent's. The new roles' instructions contain literal `[shared_instruction:…]` markers copied by the model. They are preserved rather than repaired, as [the demo notes](AUTOMATIC_HARNESS_DEMO.md) disclose. |
| Did the change affect execution? | **Yes.** Run `run-5134783b…` (Olônne-18 validation, real model) carries the candidate hash on the run and on every task. Its executed dependencies equal the candidate specification's. The ordered commits are 11 `inspect_evidence` complete → 12 `evidence_review` running → 15 complete → 16 `compare` running. The reviewer trace is real-model output with context policy `contradictions_first`, and it called `control_overlap`. All 32 events are contiguous. |
| Did the agent make a consequential investigation decision? | **Only a harmful one is evidenced.** R0 is a fixed set of deterministic checks plus one synthesis call. H0 and H1 are fixed role graphs, and within each role the model chooses tools from an allowlist. Those choices varied between cases, but no artifact shows that a choice improved a conclusion. The consequential choice is a failure that repeats. In every `controls_withheld` case recorded so far (H0 on Pansio-1, H0 and H1 on Olônne-18), an inspection worker requested the withheld control table. It received `PermissionError`, and the run ended `blocked` with a score of 0. R0 completed both of those cases. |
| Was evaluation fair? | **The design is sound, but there is one open concern.** The frozen manifest equals the live record: same model, pinned provider, low reasoning, 8,192 output tokens, budget, sources, criteria and split hash. The answer key is independently computed but **not human-reviewed**. Each split holds one locus from one paper, so there is no generalization. **Concern for the H03/H05/H06 owners:** the permission-denial failure hits every arm that has an inspection role and never hits R0. The owners must decide, and disclose, whether that is a legitimate failure to respect withheld evidence or a runtime design that makes one denied query end the case. Either way, the 0 scores must stay in the report. |
| Was recovery real? | **Yes, for the operational runtime only.** [Recovery 15/15](../../artifacts/safe_harbor/pr66-runtime-repair/recovery-after/report.json) records real exits 86 and 87 plus an external SIGKILL (−9). The committed SIGKILL export has 30 contiguous events across coordinator epochs 1→2 and completes. It used the deterministic adapter with 0 model calls. No paid-model run was interrupted. **Warning:** every run, including the R0 and H1 demo runs, logs `coordinator.recovered` during normal startup (epoch 1). Do not narrate that event as a recovery. |

## Pitch segments (specification three-minute demo)

| Segment / spoken claim | Status | Evidence and limit |
|---|---|---|
| Context: three published GRCh38 candidates, H1 context, real sources | **Supported** | Independent checks confirm three things. Source→internal coordinate conversion is correct for all three loci. Each candidate's supplement-1 sheet/row hash matches the 15-source manifest. Each reference window's SHA-256 matches its bases, and `personalized_h1_genome` is false. The raw source bytes are **not in git**, so hashes of the original files can only be re-derived where `data/safe_harbor/raw/` exists. These are published candidates, not a discovery. |
| Real genome zoom | **Supported (operational)** | [Q09 frames 73/73](../../artifacts/safe_harbor/genome-e2e/2026-09-26-q09-frames/report.json), [readability 49/49](../../artifacts/safe_harbor/pr64-review/readability-final/report.json) and the [R0 replay journey 10/10](../../artifacts/safe_harbor/baseline-replay/report.json). Earlier failing readability runs are kept. |
| Expression investigation: "96 targeted DE genes, 260 untargeted, 31 shared" | **Supported, with scope** | Recomputed from the normalized tables without production code: 96/111/139 DE genes, 31/40/48 shared, 260 controls. Every row meets \|log2FC\|≥1 and FDR≤0.01, so these are significant-only tables. The 18/18 [R0 preflight](../../artifacts/safe_harbor/real-model-preflight/run-1c38545496844fcb858df0892a3df064/report.json) is **one development run and did not reproduce**. The same case and arm in the frozen experiment scored 17/18 with 2/3 decisions and `completed: false`. |
| Evidence revision reopens dependents | **Supported (operational)** | [Revision 10/10](../../artifacts/safe_harbor/pr66-runtime-repair/revision-after/report.json), with the earlier failure kept in [revision-before](../../artifacts/safe_harbor/pr66-runtime-repair/revision-before/report.json). This is a separate deterministic recording. Do not splice it into a model run. |
| Real recovery | **Supported (operational)** | See the recovery row above. The report's `runs[*].export` paths still name the old `pr66-review/` directory, although the exports are committed beside the report. The process logs it names are not committed. |
| Actual structural patch executes | **Supported** | See the harness-change and execution rows above. The saved change is structural (six → seven roles, new dependency, reassigned tool) and was generated by a model. |
| Measured promotion/rejection | **Not supported yet** | `promotion` is `null`. The experiment is `running_validation`, and all final rows are `pending` or `awaiting_proposal`. The first H1 run's workflow finished, but its **final answer was not validated**: the dossier has `model_proposal_accepted: false` ("cites evidence outside its consumed manifest"), and the latest assessment is `unresolved`. H1 scored 18/18 on numbers but `completed`/`support_ok` are false, costing 228,113 tokens ($0.0341). On the same case R0 scored 17/18 with 3/3 decisions and `completed: true`, costing 19,198 tokens ($0.0037). No improvement or cost win has been shown; 15% is a threshold, not a measurement. |
| Versioned dossier with preserved uncertainty | **Supported** | The R0 export has 10 contiguous events, with the first assessment at 9. The historical dossier at event 1 contains no assessment. The conclusion keeps the axes *incomplete / unknown / current*. |

## Results that must be reported, not hidden

These are real-model results from `experiment-a879d0fa…`, one run per arm, as of the committed snapshot:

| Split / case | H0 | R0 | H1 |
|---|---|---|---|
| dev Pansio full_sources | 14/18, 3/3 dec, ~187k tok | 17/18, 2/3 dec, ~21k tok | — (proposal source) |
| dev Pansio controls_withheld | **blocked, 0/15** | 14/15, 2/3 dec | — |
| dev Pansio h1_context_only | 19/19, 3/3 dec, only fully supported dossier | 17/19, 2/3 dec | — |
| val Olônne full_sources | 12/18, 3/3 dec, ~195k tok | 17/18, 3/3 dec, completed, ~19k tok | 18/18, 3/3 dec, final not validated, ~228k tok |
| val Olônne controls_withheld | **blocked, 0/15** | 14/15, 2/3 dec | **blocked, 0/15** |
| val Olônne h1_context_only | running | pending | awaiting |

Other results to keep visible:

- **`experiment-5d8ef289…`:** all four scored rows scored 0 because output was truncated. `latest-experiment.json` still says `running_development`. The terminal record is `experiment-aborted.json` (`aborted_configuration_failure`).
- **H0 preflight [run-fd79…](../../artifacts/safe_harbor/real-model-preflight/run-fd79f621f4444f47aae814434998c3b9/report.json):** 16/18 with an unsupported `control_de_count`, using 206,150 tokens and $0.033226.
- **SH-Q07:** the committed [adaptation report](../../artifacts/safe_harbor/adaptation-e2e/report.json) predates the genuine proposal and still records 2 blocked checks. The genuine candidate and its execution now exist. A run under a *promoted* version still does not.

## Safe wording for Q11

Use this wording until the gates below close:

> "Safe Harbor investigates three published GRCh38 candidate regions in an H1 context, using real source tables and reference annotations. In recorded runs, a real model's synthesis matched the independently computed numbers while keeping missing evidence open. Recovery and selective revision are shown in separate operational recordings. The model proposed a structural change to its own workflow: it split evidence inspection and added a reviewer. That saved change really executed. Validation has not selected it, its first final answer failed citation validation, and no improvement has been measured."

Always keep the labels *real model*, *deterministic operational*, *mock* and *recorded replay* visible. Never present the R0 preflight next to the H1 validation run as a matched comparison. Never claim global safety, causality, novel sites, generalization, a cost win or billion-token validation.

## What would change the verdict

1. H05/H07/H08: complete validation and final rows under this freeze and publish the promotion record, whatever it decides, including optimizer overhead. Resolve and disclose how the `controls_withheld` permission denial is treated.
2. H07/Q07: if a version is selected, record a later run under that version and rerun `e2e/safe_harbor/adaptation.py` against it.
3. Q11: a committed canonical recording. Rerun this audit against its narration. Sign-off also requires a reviewer independent of the UI, harness, Q06 and Q10 authors.

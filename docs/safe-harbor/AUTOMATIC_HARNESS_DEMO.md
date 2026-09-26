# Real automatic harness change — 30 seconds

This segment demonstrates an actual model-generated structural change executing, followed by **validation rejection and reuse of the retained parent version**. It does not claim improvement, promotion of H1, or a validated final answer from the first H1 run. Selection is recorded in experiment `experiment-a879d0fa4f5e499b89a43ed8b7f7f400`; final-case comparison runs remain in progress at this inspection.

## Prepare the two real recordings

- [Genuine R0 baseline in the UI](http://127.0.0.1:5176/?run=run-1c38545496844fcb858df0892a3df064): use Presentation and recorded replay. Its [10/10 replay report](../../artifacts/safe_harbor/baseline-replay/report.json) supports the existing genome-to-answer segment. This separate development preflight is not a paired comparison result against H1.
- [First genuine H1 run in the UI](http://127.0.0.1:5176/?run=run-5134783b07da40f2b6ac5c6b053bf901): select **Olônne-18**, use recorded replay, and expand the actual task graph. Seek using the timeline to commits **11, 12, 15, 16**; the URL opens the run, not a predefined cursor.
- [Subsequent retained-parent run in the UI](http://127.0.0.1:5176/?run=run-0142454a0a6b4976bd380c6eeeddec99): Keppel-19, a final case created after selection. Its [selection/reuse proof](../../artifacts/safe_harbor/selected-harness-proof/report.json) passed 20 actual API/MongoDB checks, including an accepted genuine worker trace.
- Open [the exact model response](../../artifacts/safe_harbor/automatic-structure-proof/optimizer-response.json), [saved patch and candidate](../../artifacts/safe_harbor/automatic-structure-proof/candidate-harness.json), and [independent execution proof](../../artifacts/safe_harbor/automatic-structure-proof/report.json) in prepared tabs. The live [experiment record](http://127.0.0.1:8016/experiments/experiment-a879d0fa4f5e499b89a43ed8b7f7f400) is separate from either replay cursor.

## Spoken walkthrough

| Time | Show | Say |
|---|---|---|
| 0–8 s | Exact automatic patch: `split_role(inspect)` and `reassign_tools(control_overlap)` | “From recorded development traces, the model proposed splitting evidence inspection and moving the control-overlap tool to a new reviewer.” |
| 8–20 s | H1 commits **11 → 12 → 15 → 16**, highlighting the new roles and dependency | “The saved change really executed: inspection finished, the new reviewer used its contradictions-first context and called control overlap, then downstream comparison began.” |
| 20–30 s | Saved rejection and subsequent parent-run worker trace | “Validation rejected the candidate because support and completion declined. A later real-model run reused the retained parent. The change executed; improvement was not established.” |

Do not present the baseline preflight and this validation case as a matched quality/cost comparison: they use different candidates and different roles in the experiment. Use the frozen experiment's own paired cases for that comparison after its results are available.

## Exact execution references

Parent `2562bbd42027f9ec415163ca479978a862d087aed54be2c1d83ef28c63c58e5d` has six roles. Candidate `453e57dd9f41b0cb35120608d3670cceaf8b15be4ce7e2c84684d65cb6097124` has seven. The optimizer made one real call: **11,969 tokens / $0.00342986 / 83.994899 seconds**. These are proposal overhead, not an improvement measurement.

The exact patch replaces `inspect` with `inspect_evidence → evidence_review`, moves `control_overlap` from `compare` to `evidence_review`, and routes former inspect dependents through the reviewer. Its policy is `contradictions_first`; the rest of the run retains the frozen model, evidence, criteria, and assigned budget. The raw new-role instructions contain literal `[shared_instruction:...]` markers copied by the model. They were preserved exactly, not expanded or repaired; mandatory runtime context/output requirements remain separately enforced. The model's rationale is a hypothesis, not an established diagnosis.

The separately persisted MongoDB record `promotion:experiment-a879d0fa4f5e499b89a43ed8b7f7f400` rejected H1 at **2026-09-26 19:59:24.410037 UTC**. It used exactly the three assigned Olônne-18 validation scenarios, with the frozen rule and manifest. Recorded reasons: **“olonne-18--h1_context_only: evidence support declined”** and **“olonne-18--h1_context_only: completion declined.”** The selected saved hash remains parent `2562bbd42027f9ec415163ca479978a862d087aed54be2c1d83ef28c63c58e5d`.

Final run `run-0142454a0a6b4976bd380c6eeeddec99` was created at **19:59:24.470245 UTC**, after that decision. Its creation event committed the exact selected saved specification. Accepted screen trace [artifact-09d5eff2c1714c4db1d4c9a675247a9a](http://127.0.0.1:8016/runs/run-0142454a0a6b4976bd380c6eeeddec99/artifacts/artifact-09d5eff2c1714c4db1d4c9a675247a9a) binds a complete task, real-model mode, and that hash in both provenance and context; it records **two provider responses / 12,722 tokens / $0.0017063984**. This is actual retained-parent reuse, not promotion or successful self-improvement. Final cases were not inputs to selection.

For run `run-5134783b07da40f2b6ac5c6b053bf901`:

- Commit **11** accepts `inspect_evidence`, trace [artifact-0e28613c841049439be895a03be3ecec](http://127.0.0.1:8016/runs/run-5134783b07da40f2b6ac5c6b053bf901/artifacts/artifact-0e28613c841049439be895a03be3ecec).
- Commit **12** starts `evidence_review` after that dependency completed; **15** accepts it. Its [trace artifact-8b1749f667294b108ed8fc3e013d8a92](http://127.0.0.1:8016/runs/run-5134783b07da40f2b6ac5c6b053bf901/artifacts/artifact-8b1749f667294b108ed8fc3e013d8a92) records two provider responses, the changed policy, and the actual `control_overlap` call `chatcmpl-tool-9eed52dea01328bb`.
- Commit **16** starts `compare` with the new reviewer as its dependency. Thus the changed graph is execution evidence, not presentation metadata.

## Terminal assessment audit — preserve these failures

Read-only inspection of the [terminal export](http://127.0.0.1:8016/runs/run-5134783b07da40f2b6ac5c6b053bf901/export) found all seven tasks complete through commit **32**, with **14 real model calls**, **228,113 tokens**, **22 tool calls**, and **$0.0341092472** recorded. Model-call totals agree with worker traces; reservations and uncertainty are zero. Workflow completion does not mean every model proposal validated.

| Commit | Stored result | Interpretation |
|---|---|---|
| 15 | New reviewer assessment revision **1**, schema errors including missing required fields | Preserved as `unresolved`, `incomplete`, `unknown`; the role still really executed. |
| 23 | Assessment revision **2**, no validation errors | A valid intermediate assessment remains inspectable. It does not replace the later terminal result. |
| 27 | Review assessment revision **3**, `limitations` supplied as a string instead of a list | Latest candidate assessment is conservatively unresolved. |
| 31 | Dossier [artifact-73d7557ad8084563b25225b6d590ba25](http://127.0.0.1:8016/runs/run-5134783b07da40f2b6ac5c6b053bf901/artifacts/artifact-73d7557ad8084563b25225b6d590ba25), validated summary revision **4** | `model_proposal_accepted=false`; error: “Proposal cites evidence outside its consumed manifest.” Summary remains `unresolved`, `incomplete`, `unknown`. |
| 32 | `run.stopped`, all current tasks accepted | Execution finished; it did not produce a validated final answer. |

The three assessment records match their retained immutable revisions. The dossier content hash and consumed artifact hashes match stored bytes, and events 1–32 are contiguous. This audit checked provenance/state consistency only: it did not rerun the evaluator, change scores, or modify Data's experiment records. Keep the failed final result and the recorded rejection visible; final comparison results remain separate. No paid calls or production changes were made for this document.

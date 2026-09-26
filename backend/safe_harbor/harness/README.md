# Frozen executable harness specifications

H01/H02 implementation. `get_harness()` returns the developer-authored, control-aware H0 baseline. It does not imply model use, optimizer invention, or measured improvement. Explicit saved hashes load from the same MongoDB `harness_versions` collection as the runtime ledger. There is no in-memory fallback for saved versions.

Every specification hashes its exact canonical JSON, excluding only `harness_hash`. `save_harness()` uses an immutable insert, validates the parent, and rejects conflicting content. It does not promote a candidate. Passing a selected saved hash to a subsequent run freezes that version for the run. Selection and default-version promotion belong to H07.

The baseline compiles six roles per candidate, eighteen tasks for the initial three candidates. Its deterministic operational adapter can call all declared tools in 39 calls, within the initial 40-call cap. Real-model token/cost availability remains separately bounded by the run ledger; this is not a measured cost claim.

## Patch API for H06

`apply_patch(parent, patch, proposal_mode=..., proposal_metadata=...)` returns a validated unsaved candidate. `patch` must contain exactly `operations`, a list of one to four operations. The exact content is retained; no mutation is selected automatically.

- `insert_reviewer`: `op`, `after_role_id`, `role`. A new `review_candidate` role is inserted and downstream dependencies are rewired through it.
- `split_role`: `op`, `role_id`, `roles` (exactly two new role records). The first inherits old dependencies; the second depends on the first. Downstream dependencies move to the second. Original tool capabilities remain available.
- `change_context`: `op`, `role_id`, `context_policy`.
- `reassign_tools`: `op`, `from_role_id`, `to_role_id`, `tools`. Approved tools move between existing roles; the overall available tool set is unchanged.

New role records require `role_id`, `kind`, `question`, and `allowed_tools`. Optional fields are `context_policy`, `instructions`, `decision_target`, and `completion_condition`. The compiler owns dependencies and execution caps; the optimizer cannot supply them. Role instructions are bounded. Context policies are `relevant_evidence`, `numerical_first`, or `contradictions_first`.

`proposal_mode` is `unverified_proposal`, `deterministic_operational`, or `real_model`. A real-model label additionally requires `proposal_metadata.model_id` and `proposal_metadata.response_artifact_id`. These references must be substantiated by H06's real saved optimizer trace; schema acceptance alone is not evidence that a model generated the patch.

## Executed context behavior

The runtime invokes `select_context_artifacts(records, policy, max_characters=28000)`. The helper selects real upstream records and returns exact evidence, omitted IDs, and `selection_trace`. Relevant evidence preserves dependency order. Numerical-first prioritizes deterministic scientific calculation results. Contradictions-first prioritizes explicitly flagged conflicts and unavailable/incomplete calculations; it does not infer biological contradictions.

Mandatory question, objective, candidate, assembly, cell context, data version, criteria, allowlist, dependency read set, and budget remain outside this selection and cannot be removed. All policies use the same maximum context bound. When all records fit, a policy may reorder without reducing resource use; no benefit is guaranteed.

## Comparison compatibility

The independently authored H04 all-checks baseline can use `baseline_arm: R0`, `parent_hash: null`, `patch: null`, and `proposal_mode: developer_authored_fixed_baseline`. Its schema requires deterministic analysis and synthesis, but does not force six agent roles. It retains the same approved tools and immutable constraints. This package does not invent the R0 implementation or its measurements.

Operational `mode: mock` / `proposal_mode: mock` registry fixtures are excluded from production listing. Invalid non-mock saved records fail validation rather than silently appearing valid.

Only syntax, build, schema and complete operational/browser E2E verification are allowed. No unit or component tests.

## Executed operational proof

From the standalone repository root, with its MongoDB replica set running:

```sh
PYTHONPATH=.:backend .venv/bin/python e2e/safe_harbor/harness_execution.py
```

The journey launches a fresh real API/coordinator process against an isolated MongoDB database, saves both specifications, calls the actual API, runs real source-backed Pansio-1 calculations, checks the committed tasks and artifacts, and exports both runs. The API subprocess is stopped afterward; the database remains inspectable.

The recorded successful journey has six completed H0 roles and thirteen scientific tool calls; the manually authored candidate has seven completed roles and fourteen tool calls. Its additional `controls_audit` reviewer executed `control_overlap`, consumed `numerical_first` context, and appeared between assessment and the existing review in the saved task dependencies. The assigned limits were identical (60,000 tokens, 40 tool calls, $5). Actual model calls and tokens were zero in both runs. This proves structural execution and version isolation; it does not establish automatic architecture invention, scientific interpretation, or improvement. The added reviewer cost an additional tool call.

Evidence in the standalone repository:

- [Operational E2E implementation](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/e2e/safe_harbor/harness_execution.py)
- [Measured operational report](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/artifacts/safe-harbor/harness-operational/report.json)
- [Baseline committed export](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/artifacts/safe-harbor/harness-operational/fixed_baseline.json)
- [Manually patched committed export](https://github.com/Nathan-T-Ray/Safe-Harbor/blob/main/artifacts/safe-harbor/harness-operational/manual_structural_patch.json)

An earlier script attempt completed both runs but looked up the context trace using the wrong field name; its failed report is retained. The corrected E2E inspects the runtime's actual `context_selection_trace` field and passes.

# Genuine R0 baseline replay segment

This is a **completed genuine baseline segment awaiting the comparison**, not the full canonical Q11 demonstration. It replays one actual Pansio-1 investigation: deterministic analyses followed by one real synthesis call. It does not demonstrate adaptive tool selection, an automatic executable H1, or improvement.

Open the existing local recording: **[Pansio-1 baseline](http://127.0.0.1:5176/?run=run-1c38545496844fcb858df0892a3df064)**. This requires the running frontend on port 5176, its API proxy to port 8016, and the existing MongoDB run. Opening it only reads saved state. The startup screen says LIVE because it shows the latest stored record; switch to replay before narrating recorded execution. Do not start a new investigation or apply an evidence revision for this segment.

Suggested 90-second walkthrough:

1. Click **Presentation**, then **Reset to start**. Show **RECORDED REPLAY / REAL MODEL**. Before event 1, the catalog is explicitly a neutral preview and there is no assessment or dossier. The execution-mode selector configures a future run; the recorded run's mode is the REAL MODEL badge.
2. Scroll to the replay timeline, turn **Follow camera** off for manual navigation, and seek to **1 / 10**. Return to the genome panel. Click **Genome → chr1 → Locus → Sequence**. Selection remains Pansio-1 at `chr1:113,339,961–113,340,514` (display coordinates); the stored interval is `[113339960,113340514)`. The annotations are frozen GENCODE v36 and the bases are actual GRCh38 reference bases, not a personalized H1 sequence. Neutral genome regions were not scanned by this investigation.
3. Seek to **5 / 10** and open **Inspect evidence & calculations**. The `control overlap` and `gene proximity` records contain the actual numbers, evidence IDs, source versions and exact calculation records. No assessment exists yet. Say: “These significant-only tables contain 96 targeted DE genes and 260 in the independent untargeted comparison; 31 are shared. This contextualizes the concern without establishing cause or safety.”
4. Close evidence and seek to **10 / 10**. Show the recorded conclusion and its three independent axes: **incomplete computational screen / unknown experimental evidence / current evidence**. The real synthesis says these measured expression changes do not justify exclusion on the available evidence, while required cancer-gene, DHS and ultraconserved-region evidence remains absent. Open **Dossier at this commit** to inspect the matching versioned record. This baseline does not claim an experimentally safe locus.
5. Close the dossier and seek backward to **8 / 10**: the future conclusion disappears. Seek to **1 / 10**, reopen **Dossier at this commit**, and show that it contains no assessment. Its JSON download includes only that historical state and the reference assets. Return to event 10 to finish. Optional playback at 4× advances **four events per second**; recorded timestamps remain visible and do not become playback time.

The saved execution occurred from **19:30:02 to 19:30:35 UTC on 2026-09-26**, across 10 ordered commits. Its assessment first appears at commit 9. It used model `deepseek/deepseek-v4.1-flash`, pinned provider `deepinfra/fp8`, low reasoning and an 8,192-token output allowance. Actual use was **18,200 tokens, eight tool calls, one model call and $0.00363608**, with no unsettled token reservation. Assigned caps were 400,000 tokens / 40 tools / $5; those are limits, not spend.

Evidence for this segment:

- [Source run export](../../artifacts/safe_harbor/real-model-preflight/run-1c38545496844fcb858df0892a3df064/run-export.json) and [development preflight report](../../artifacts/safe_harbor/real-model-preflight/run-1c38545496844fcb858df0892a3df064/report.json): 18/18 required outputs supported under the evaluator; reference answers are independently computed but not human-reviewed.
- [Read-only replay browser report](../../artifacts/safe_harbor/baseline-replay/report.json): four coordinate-linked zoom levels, exact bases/hash, backward replay, historical dossier download, playback and unchanged authoritative state. No model calls or ledger writes by verification.
- Screenshots: [overview](../../artifacts/safe_harbor/baseline-replay/01-recorded-overview.png), [locus](../../artifacts/safe_harbor/baseline-replay/02-frozen-locus.png), [bases](../../artifacts/safe_harbor/baseline-replay/03-actual-reference-bases.png), [recorded answer](../../artifacts/safe_harbor/baseline-replay/04-recorded-baseline-answer.png), [historical dossier](../../artifacts/safe_harbor/baseline-replay/05-historical-dossier.png).
- [Downloaded event-1 dossier](../../artifacts/safe_harbor/baseline-replay/historical-through-1.json): no future assessments or events.

Repeat this read-only browser journey from the repository root:

```sh
node e2e/safe_harbor/baseline_replay.mjs
```

Recovery and evidence-revision demonstrations remain **separate deterministic operational recordings**; neither occurs in this R0 run. The earlier optimizer produced an empty, rejected response. A new frozen comparison, executable H1, validation selection and full Q11 rehearsal remain outstanding; see [claim review](CLAIM_REVIEW.md). Do not splice those separate records into an invented continuous investigation or describe this baseline segment as successful self-improvement.


---

## SH-Q11 canonical real-model run (claude-opus)


Canonical run: `run-0d71fb0b3f94441fb89bc5cf042eb6f5` in MongoDB database `safe_harbor_q11_demo_20260926T153329` (local replica set `safe-harbor-dev`, port 27021). Mode **REAL MODEL** (`real_model`, OpenRouter `deepseek/deepseek-v4.1-flash`). It covers the three published candidates Pansio-1, Olônne-18 and Keppel-19. Presentation is a **RECORDED REPLAY** of its 80 committed events. Report, derived cues and 1280×720 stills are in `artifacts/safe_harbor/demo/20260926T160032/`. The 12 MB export was left uncommitted. To regenerate it, run `GET /runs/{id}/export` against that database. The summary is in `artifacts/manifests/safe-harbor-demo.json`.

Driver: `PYTHONPATH=backend:. .venv/bin/python scripts/safe_harbor_demo.py` (API 8060, UI 5200). To rehearse the presentation without any model call, add `--present-only RUN_ID --database DB`.

### Measured

- Run budget: explicit 1,000,000 tokens, 120 tools and USD 0.60. The 200k default cannot fit three candidates, because one candidate used about 139k tokens in SH-Q01.
- Usage: 557,395 provider-reported tokens, 36 model calls, 55 tool calls, USD 0.0305 known plus USD 0.0030 uncertain (interrupted by the crash).
- Recorded wall time: 1,490 s from the first to the last event. The provider endpoint took about 2.5–3 minutes per task.
- Full replay, measured in Playwright: 80.1 s at 1× and 40.1 s at 2×. A fresh client was ready in 2.2 s.
- Spend across all attempts: about USD 0.062 known plus USD 0.009 uncertain.

### Beats against the three-minute outline

| Beat (target) | Status | Backing in the canonical record |
|---|---|---|
| Context (20 s) | Demonstrated | Commit 1 `run.created`: GRCh38, H1, REAL MODEL label. The narration must fill time; the replay span is 1 commit. |
| Real genome zoom (25 s) | Demonstrated | First locus tool result at commit 9 and reference bases at commit 30. Cues come from `deriveCues` (focus chromosome, zoom locus, show bases). |
| Expression investigation (30 s) | Demonstrated | Expression result at commit 38 and first assessment at commit 50. Every model-requested tool result recomputes identically. All three candidates end `incomplete`/`unknown` (revision 2); none is labeled safe. |
| Evidence revision (25 s) | **Not demonstrated in the canonical run** | See the revision attempt below. |
| Real recovery (20 s) | Demonstrated | The API was SIGKILLed at commit 18 while two workers ran. `coordinator.recovered` at commit 19 (epoch 2) re-queued both tasks, which then completed, and the uncertain expenditure is recorded. This is a single commit, so the presenter should pause on it. |
| Structural patch + measured promotion (40 s) | **Not demonstrated / untested** | No real-model `POST /experiments` was run. Even a minimal split needs about 6 full runs at about 25 min each at the observed latency. No proposal, promotion or improvement is claimed. |
| Versioned dossier (20 s) | Demonstrated | The dossier's four screen-agreement checks pass, and the latest assessment for each candidate equals the export. |

At 2×, the backed beats replay in about 40 s against the 180 s outline. The remaining time is narration, pauses, and the two undemonstrated beats, which must be presented as not demonstrated.

### Revision attempt (separate real run, not canonical)

`run-c402f7440d05414ea1d008c7bb414d28` (same database, REAL MODEL, USD 0.0322 known plus 0.0061 uncertain). All 18 tasks completed, including a SIGKILL recovery at commit 20. `POST /evidence-revisions {withhold-control-evidence}` then committed `evidence.revised`. It reopened only the five dependent Pansio-1 tasks, superseded the originals and marked the prior assessment stale. The reopened `inspect_evidence` task failed with `PermissionError: Untargeted control table is unavailable under the current evidence revision` (`backend/safe_harbor/science/tools.py:139`; `control_overlap` degrades gracefully at `backend/safe_harbor/runtime/worker.py:104`, but `table_slice` does not). The run ended `blocked` at commit 87 and no post-revision assessment exists. This is a runtime issue for codex-runtime.

### Attempts and process notes

1. The first driver invocation created `run-c402…` and injected the SIGKILL. The driver itself was then SIGKILLed on purpose, because its 1,200 s deadline would have started a second attempt concurrently. The API kept running, and the driver was reattached with `--attach`.
2. The reattached driver saw `run-c402…` block after the revision, so it created `run-0d71…`. That driver was stopped before its crash step. It was then reattached with `--crash-on-attach --no-revision`, which completed the run and ran the browser phase.

The report's single FAIL line ("revision: … new current assessment") comes from the code as it stood then, which still required a revision in the canonical run. The current script records the revision as not exercised under `--no-revision` and reports `--revision-run` separately. The rerun with that code was not executed. The browser check "evidence-revision cue" passed vacuously, because there is no revision event.

### Browser acceptance (Playwright, 1280×720, fresh context)

These all passed:

- `?run=` opens in presentation mode with 80 events preloaded.
- The labels LIVE plus REAL MODEL show on the live record, and RECORDED REPLAY plus REAL MODEL during replay.
- Reset to start returns to commit 0 with no assessment and the dossier disabled.
- The full 2× replay reaches 80/80, and the camera cues seen during playback match the derived cues.
- The final conclusion shown equals the export.
- No assessment appears before commit 50.
- A second reset returns to commit 0.
- There were no non-GET requests and no page errors.

### Limitations

- No real harness proposal or promotion.
- The evidence-revision beat is blocked by a runtime issue.
- Recovery occupies a single commit.
- Replay pacing is uniform per event, so beats cannot be timed individually.
- The run uses an explicit, non-default budget.
- Raw-JSON conclusion envelopes and the assessment-revision ID race were not observed in these runs.

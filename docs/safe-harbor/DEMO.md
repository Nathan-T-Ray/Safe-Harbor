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

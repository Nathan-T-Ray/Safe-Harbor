# Continuity demonstration — 60 seconds

Use these saved operational recordings alongside the genuine-model baseline demonstration. These are **deterministic operational fixtures executing actual API processes, scientific tools, and MongoDB transactions, with zero model calls**. Process termination and recovery really occurred. Delays and token reservations were injected to make interruption boundaries observable. No biological measurement was changed and no real-model recovery is claimed.

## Spoken walkthrough

| Time | Show | Say |
|---|---|---|
| 0–8 s | Mode labels in the recovery/revision reports | “This is a recorded operational demonstration using real source data and MongoDB. It uses a deterministic adapter, with no model calls.” |
| 8–25 s | Acceptance export, events **8 → 9 → 16**; recovery report's checkpoint evidence and process PIDs | “The process exited after committing this result, before its completed checkpoint. A new process recovered from MongoDB. The same artifact hashes remain, this task was not repeated, and downstream work finished.” |
| 25–40 s | Reservation export, events **7 → 8 → 10** | “A second process died after reserving work. Recovery kept that expenditure uncertain instead of treating it as free. These thousand units are an operational fixture, not measured model tokens.” |
| 40–60 s | Revision export, events **12 → 13 → 19 → 32 → 41** | “Here control evidence becomes unavailable during work. The stale result is rejected, affected branches reopen, and unrelated work stays valid. Restoring availability creates another version. Earlier evidence and assessments remain inspectable.” |

The exports are from isolated databases, not the production model run. Open the linked JSON records in prepared tabs or a JSON viewer; do not assume their run IDs exist in the active production API. Events show committed transitions, not a fabricated crash event. Process death is established by the corresponding process/checkpoint report. Recorded elapsed times differ from this accelerated walkthrough.

## Exact evidence references

**After acceptance, before checkpoint:** [recovery report](../../artifacts/safe_harbor/pr66-runtime-repair/recovery-after/report.json), checks prefixed `accept_crash:`; [run export](../../artifacts/safe_harbor/pr66-runtime-repair/recovery-after/run-12c05643bd264f7892f9d7734f302799.export.json).

- Run `run-12c05643bd264f7892f9d7734f302799`, database `sh_e2e_recovery_1790451056_fbf40d`.
- PID **3658** terminated with exit **86** at `SAFE_HARBOR_CRASH_AFTER_ACCEPT=compute_features`; PID **3666** restarted fresh. The hook calls `os._exit(86)` after acceptance. This precise-boundary crash is not an externally issued SIGKILL.
- Event **8**, `task.completed`, accepts `pansio-1:compare:r0`, operation `accept:run-12c05643bd264f7892f9d7734f302799:pansio-1:compare:r0:1:1`. The report records durable acceptance but no completed-node `accepted_sequence` checkpoint for that task.
- Event **9**, `coordinator.recovered`, changes epoch **1 → 2**. Compare remains attempt **1**, with identical artifact IDs/hashes. One example is `artifact-4441ea559e22485d946956a9374b54dc`, hash `95aef60e92f21cbeb7dd521328e940f66a87917b537a887aa5063b1034b0f9ac`.
- Events **10–15** complete downstream work under epoch 2; event **16** stops the completed run. The recorded restart-to-terminal interval was **12.71 seconds**, including lease expiry.

**After reservation:** same recovery report, checks prefixed `reserve_crash:`; [reservation export](../../artifacts/safe_harbor/pr66-runtime-repair/recovery-after/e2e-recovery-be00907a8900442b83e39a7e8de2ce77.export.json).

- Run `e2e-recovery-be00907a8900442b83e39a7e8de2ce77`. PID **3798** exited **87** using `SAFE_HARBOR_CRASH_AFTER_RESERVE=compute_features`; PID **3799** restarted.
- Event **7**, `task.started`, durably reserves **1,000 artificial token units / 3 tool calls** for compare attempt 1. Event **8**, `coordinator.recovered`, moves those reservations to `uncertain_tokens=1000` and `uncertain_tool_calls=3`, queues interrupted work, and advances epoch **1 → 2**.
- Events **9–10** execute and accept compare attempt **2**. Event **17** finishes with uncertainty still retained. Actual `tokens_used=0`, `model_calls=0`, and measured scientific `tool_calls=13`. The artificial units must never be presented as measured inference usage.

**Externally issued OS kill, if challenged:** same recovery report, `sigkill:` checks and `processes`; [SIGKILL export](../../artifacts/safe_harbor/pr66-runtime-repair/recovery-after/e2e-recovery-cd5628af28f64646a4695f0dba0a6d58.export.json).

- Run `e2e-recovery-cd5628af28f64646a4695f0dba0a6d58`, PID **3894**, actual **SIGKILL / exit −9**, replaced by PID **3899**.
- Events **5–6** completed both screen tasks; **7–8** started two inspect tasks before the kill. Event **9** recovers epoch 2, preserving completed artifacts and retaining 1,000 artificial units / 6 tool calls as uncertain. Events **10–13** retry both interrupted tasks; event **30** finishes. Maximum simultaneous running tasks remained two.

**Evidence revision during active work:** [revision report](../../artifacts/safe_harbor/pr66-runtime-repair/revision-after/report.json) (10 recorded service checks); [revision export](../../artifacts/safe_harbor/pr66-runtime-repair/revision-after/e2e-revision-8be2c2b2923f46b7aa78a418d7747ecd.export.json).

- Run `e2e-revision-8be2c2b2923f46b7aa78a418d7747ecd`, database `sh_e2e_revision_1790451056_c0c16c`, PID **3657**. Its operational harness deliberately permits concurrent branches.
- Event **12** starts Pansio compare consuming `scope:pansio-1:expression` version **1**. Event **13** applies `withhold-control-evidence` through the API, changes this scope to **2**, supersedes five Pansio tasks, and adds five successors. Availability artifact: `evidence-availability-affbd9054a064550894b065822e95d03`.
- The export's `operations` includes rejection of original operation `accept:e2e-revision-8be2c2b2923f46b7aa78a418d7747ecd:pansio-1:compare:r0:1:1`, reason **“Consumed evidence changed: scope:pansio-1:expression”**. No artifact from that stale attempt was accepted. Rejection is an operation record; it is not a fabricated successful commit.
- Event **19** accepts successor overlap artifact `artifact-9469619e559f4b04811d086479cbf21a`, status **unavailable**, consuming scope version 2. Missing control evidence is not a negative biological result.
- Event **32** applies `restore-control-evidence`, scope **2 → 3**, artifact `evidence-availability-f69efbfc3d0f4ac2a4edb8d665104485`. Pansio assessment revisions **1 and 2** become stale; immutable historical revisions remain. Event **38** records the restored calculation in `artifact-76a91ca4237644f7bd645dfac9ad0b16`. Events **40–41** accept current assessment revisions **3 and 4**. Event **44** finishes.
- All six Olônne-18 tasks and Pansio's screen retain their original tasks/artifacts with one acceptance each; Olônne-18 assessments stay current. These fixtures change availability only: `biological_measurement_changed=false`.

These reports were generated against the isolated runtime repair subsequently integrated into main. Their embedded `pr66-review/...` export/log strings are original execution paths; the links above identify the retained `pr66-runtime-repair/...` files. This document inspected existing records only; it does not add a new test pass, claim recovery of a paid model call, or turn these separate runs into the canonical real-model demonstration.

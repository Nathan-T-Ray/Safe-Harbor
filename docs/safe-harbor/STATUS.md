# Implementation status — 2026-09-26

Work lands directly on `main`. [Live ticket board](https://github.com/Nathan-T-Ray/Safe-Harbor/issues/1) shows current owners and accepted tickets. This is the standalone Safe Harbor project, with a dedicated local MongoDB replica set; it does not use the old project database.

**UI is implemented and running at http://localhost:5176.** API:8016, dedicated MongoDB:27021. [Open the completed real R0 investigation](http://localhost:5176/?run=run-1c38545496844fcb858df0892a3df064).

| Work | Demonstrated state |
|---|---|
| Real source pack and calculations | Five actual supplements, 15 original source hashes, verified GRCh38 intervals and reference bases, GENCODE v36 Comp/PseudoGene annotations; independent calculations agree |
| Browser | Four coordinate-correct zoom levels, graph, evidence, replay and presentation integrated; 49/49 readability/keyboard/motion checks; six live/historical candidate zoom journeys passed |
| Genuine vertical slice | R0 Pansio development preflight completed with 18/18 supported required outputs; browser conclusion, axes, revision and evidence agree with MongoDB, 7/7 checks |
| Persistence | Authoritative transactional MongoDB ledger and separate LangGraph checkpoints; actual process death/restart verified; original artifacts remain accessible |
| Runtime repairs | Authoritative criterion/evidence validation integrated. External E2Es exposed concurrent revision allocation and stop/resume races; isolated fixes are undergoing actual-service verification |
| Harness | Saved structural patches compile and execute changed task graphs. Manual operational proof is complete; a successful automatically generated executable patch is still required |
| Actual comparison | First attempt preserved and explicitly aborted after empty model outputs and rejected optimizer proposal. Nine runs started; nine later arms blocked before dispatch; six H1 assignments lacked a candidate. No improvement claim |
| Next model work | Same model/provider, explicit low reasoning and 8192 completion allowance. R0 development preflight passes; H0 development preflight underway. New held-out comparison waits for these checks and runtime fixes |

The completed R0 preflight used 18,200 measured tokens, one model call, eight deterministic tools and USD0.00363608. It is configuration preflight on development data, not a generalization or cost-win result. Model identity remains `deepseek/deepseek-v4.1-flash` via pinned `deepinfra/fp8`. Credentials stay in ignored chmod0600 `.env`.

The first comparison spent 668,316 measured run tokens/USD0.108032232 plus 8,672 optimizer tokens/USD0.00205408; failed attempts remain visible. Its original manifest, results, exports and explicit abort record are under `artifacts/safe_harbor/real-model-comparison/experiment-5d8ef28995924af7b65ab6ef4deb3273/`. Final assessment audit found no aggregate/evidence violations in its 11 accepted records; most model proposals were invalid and retained unresolved states.

Scientific context is H1 human embryonic stem cells against the GRCh38 reference, not a personalized H1 genome. All three candidates are publication-derived. Keppel's workbook count139 versus article119 remains unresolved. Missing cancer/regulatory evidence keeps the overall screen incomplete. Neither control overlap nor distance proves biological safety or causality.

Current evidence: `artifacts/safe_harbor/real-model-preflight/run-1c38545496844fcb858df0892a3df064/`, `artifacts/safe_harbor/pr64-review/readability-final/`, `artifacts/safe_harbor/pr67-review/selector-compatible/`, `artifacts/safe_harbor/ledger-aggregate-repair/`, and `artifacts/manifests/replay-integrity.json`. Each report labels real-model versus deterministic operational execution. SVG locus fallback is explicit; no fabricated tracks are used.

Remaining release gates: finish runtime race verification, execute an automatic structural proposal, run a fair H0/R0/H1 comparison, produce the canonical genuine recording, and complete independent claim review. No novel safe sites, global safety, whole-genome search, measured improvement or billion-token performance is claimed.

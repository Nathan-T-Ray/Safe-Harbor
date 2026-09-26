# Safe Harbor implementation specification

Safe Harbor uses real genome data to investigate candidate DNA insertion sites and tests changes to its own workflow to improve those investigations. The user sees candidate genomic regions, evidence, an investigation graph and an inspectable record of harness changes. This is the completed concept; implement it incrementally. Do not restart exploration or write a giant bootstrap script.

**NO UNIT TESTS. NO COMPONENT TESTS. E2E ONLY.** Build/type/syntax/schema/data-integrity checks are allowed. Actual source data, MongoDB authoritative persistence, an automatically proposed executable harness change, competent fixed baselines, and honest mode labels are essential. No fabricated biological/evaluation results. Max root plus three local subagents; tickets are bounded packages, not 60 simultaneous agents.

## Scientific contract

Initial scope: human GRCh38 reference, H1 human embryonic stem cells. Start with publication-derived Pansio-1, Olônne-18 and Keppel-19; expand toward 8–12 only after ingestion works. This is not a novel whole-genome discovery or a newly sequenced/personalized H1 genome.

Independent axes: `screen_status: pass|fail|incomplete`, `evidence_status: supported_for_endpoint|conflicting|unknown`, `freshness: current|stale`. A screen pass covers named criteria only. Experimental support names endpoint, assay and cell context. Never globally label a region safe. Every assessment includes candidate_id, assembly, cell_context, criterion_results, experimental_endpoint_results, evidence_ids, unresolved_questions, limitations, assessment_revision and freshness. Missing required evidence means incomplete; absent experimental results are not negative biological results.

First question: **Do these measured expression changes justify excluding this candidate region?** Start unresolved. Supply numerical tables, methods and reference annotations; allow differential-expression counting, untargeted-control variation comparison, gene-set overlaps, genomic distances and reconciliation. Do not stage an intentionally wrong conclusion or guarantee a rank reversal. Control overlap/distance cannot establish safety or causality. Exclude the paper's interpretive conclusion paragraphs from scored worker input.

Sources: Autio et al., eLife article 79592, supplements 1 (candidates/filtering), 3 (screening), 4 (qPCR), 5 (H1 expression), 6 (H9 expression, different context). Inspect actual sheets and columns. Reference GENCODE v36, UCSC hg38 `wgEncodeGencodeCompV36.txt.gz`, `wgEncodeGencodeAttrsV36.txt.gz`, matching SQL, sequence API. Preserve bytes/hashes and original row/coordinate provenance. GENCODE v36 is a new versioned analysis, not exact reproduction of original annotations. Cancer-gene criteria remain unavailable or explicitly publication-reported until data/licensing resolved. Optional H1 cCRE ENCSR597SZL and DHS ENCFF503GCK must have verified child assets/assembly/coverage before use; core must not depend on large tracks. Preserve licenses for copied code; GEG-SH/SHIP are prior work, not blanket permission to vendor.

## Architecture and bounded execution

React + TypeScript + React Flow + igv.js → FastAPI → one persistent coordinator → at most two workers → bounded approved tools/model adapter → MongoDB acceptance transaction. LangGraph provides execution and MongoDBSaver checkpoints; MongoDB Atlas or transaction-capable local replica set stores authoritative application state. Use Bioframe for interval operations. Adapt LLMCompiler dependency-aware planner/executor/replanner pattern, not its old dependency stack.

Approved tasks: screen_regions, inspect_evidence, compute_features, assess_candidate, review_candidate, publish_shortlist. Every task carries task_id, run_id, candidate_id if applicable, kind, question, canonical_question_key, decision_target, depends_on, input_read_set, role_id, harness_hash, allowed_tools, completion_condition, budget, status, attempt. Validate whole DAG before dispatch. Limit two workers, 24 task nodes, three replanning rounds, one transient retry; enforce run token/tool/cost budgets and no-progress stop. Prioritize mandatory unknowns, then tasks capable of changing assessment, with deterministic tie-breaking; no invented numerical information-gain scores.

Saved HarnessVersion contains role instances/dependencies, context selection, approved tools, review routing, bounded instructions. Allowed structural mutations: split role, insert reviewer, change evidence selection, reassign approved tools. Exact patch must compile into changed executed task topology and role/context traces. Immutable: scientific criteria, reference answers, evaluation rules, input data, model identity, total assigned budget, outer permission boundary. Freeze each run's version; promotion changes subsequent runs only.

## Persistence and API

Collections: runs, tasks, artifacts, assessments, harness_versions, evaluations, operations, events, plus MongoDBSaver collections. Large sequence/track files external with immutable references/hashes. GRCh38 internal coordinates: canonical chromosome, zero-based start, exclusive end; retain source notation/conversion and never silently lift assemblies.

Acceptance transaction checks operation ID/content hash, coordinator epoch, consumed versions; accepts artifacts/assessments, updates task/budget, appends ordered event, marks operation accepted together. Identical duplicate returns accepted result; conflicting content rejects. No model calls in transactions. Checkpoints commit separately; ledger wins recovery. Include query scopes and evidence availability in read sets even for empty queries so newly available evidence invalidates absence conclusions.

Event v1: schema_version, run_id, sequence, event_id, operation_id, occurred_at, type `state.committed`, cause, run_revision, full small-record upserts. Large output referenced by artifact ID. Snapshot has through_sequence. One-second ordered polling, no second messaging platform.

Required API: GET /catalog; POST /runs; GET /runs/{id}/snapshot; GET /runs/{id}/events?after_sequence=N; GET /runs/{id}/artifacts/{artifact_id}; POST /runs/{id}/resume; POST /runs/{id}/evidence-revisions (prepared fixture ID only); POST /experiments; GET /experiments/{id}; GET /runs/{id}/export. See shared/contracts.ts and shared/contracts.py.

## UI and truthful replay

Make selected region, active question, and changed conclusion immediately clear. Context/run mode/progress/replay bar; candidate rail; coordinated genome+conclusion+numeric evidence; DAG; separate harness/evaluation drawer. Exact assembly, experimental context, data version and LIVE/RECORDED/MOCK/deterministic mode visible.

Four linked zoom levels: chromosome bars using real lengths and actual candidate markers; selected chromosome; locus with frozen exact annotations/boundaries/features; short coordinate-labeled actual reference bases. Shared candidate/interval and persistent breadcrumb, smooth purposeful transitions, neutral uninvestigated background. igv.js for locus tracks; custom SVG overview and bounded sequence strip. A cropped FASTA cannot silently retain chromosome offsets. Timebox igv integration; real coordinate-correct SVG fallback acceptable. No fabricated tracks/bases or whole-genome scanned animation.

Stable left-to-right read-only graph, Screen → Investigate → Compare → Review → Report, expandable actual task names. Queued/running/complete/blocked/reopened/superseded states. Completed nodes reveal exact inputs/results/evidence; reopened nodes explain changed input; shared evidence links multiple tasks.

Replay reconstructs stored history, never final data leaking into earlier frames. Camera cues keyed to real sequence numbers are presentation-only. Play/pause, speed, seek, next meaningful event, follow-camera toggle, return-to-candidate, live/replay indicator. Distinguish recorded event time and playback time. Restore historical assessment/artifact versions backward. Dark navy, readable type, restrained cyan/amber, words/icons with status, reduced motion and 1280×720 projection check. No 3D genome/force graph/particles/workflow editor.

## Fair evaluation and release gates

H0 competent fixed agent; R0 all deterministic relevant checks plus competent synthesis; H1 automatically revised harness. Match model/evidence/tools/criteria/budgets/assigned cases/cache policy. Development informs proposal, validation selects, final held out. Aim twelve audit cases split 4/4/4 but smaller feasible grouped split allowed. Keep related loci/variants grouped; disclose shared-source nature. Independent numerical recomputation and source-backed rubrics; no human-reviewed label without human review. Evaluator answers inaccessible to workers. Report all cases including failures, required-output correctness, unsupported conclusions, completion, tokens/calls/duration/cost and optimizer/evaluator overhead.

Freeze promotion before results: no correctness/support/coverage regression plus more correct decisions or predefined resource reduction at equal quality (15% cost is proposed threshold, not measured result). Unknown usage bars cost wins. Repeat paired runs if affordable; otherwise stochastic costs provisional. All-checks baseline may win; rejected proposal demonstrates selection, not successful improvement.

Preserve six gates: verified source bytes/schema/coordinates/hashes; independently checked numerical investigation; actual crash recovery and selective revision; automatic saved structural change executes/evaluates separately; competent baselines/all cases reported; zoom/graph/replay/export agree. Real model key is pending, so deterministic operational success cannot satisfy model gates.

Build first vertical slice: source → real calculation → worker decision → MongoDB → browser conclusion → evidence inspection. Then recovery/revisions/automatic experiment, then zoom/graph/replay polish and final E2Es. If behind, cut candidate count/optional tracks/transitions/settings/optimization attempts; preserve calculations/provenance/persistence/executable harness/fair comparison/honest replay. Defer distributed queues, arbitrary organisms, live harness migration, full-genome ingestion, workflow editing, extensive optimization searches/vector search.

Three-minute demo: 20s context, 25s real genome zoom, 30s expression investigation, 25s evidence revision/reopened dependencies, 20s real recovery, 40s actual structural patch and measured promotion/rejection, 20s versioned dossier/uncertainty. Clearly label genuine recorded replay; cues cannot invent scientific work. Never claim novel safe sites, established biological safety/causality, broad generalization, whole-genome search, unmeasured improvement, or billion-token validation. Genome bases are not model tokens.

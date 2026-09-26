Safe Harbor runtime acceptance, 2026-09-26

Changed implementation paths: `backend/safe_harbor/api.py` and `backend/safe_harbor/runtime/{ledger,compiler,coordinator,worker,revisions,context,assessments,pricing}.py`. No unit or component tests were added or run.

- R01–R04: MongoDB indexes, transactional acceptance, operation hash idempotency, epoch/read-set checks, full-record ordered events, consistent historical snapshots, and bounded dependency compilation are implemented. Actual-service evidence: `artifacts/safe_harbor/runtime-e2e/standalone-current/report.json`.
- R05–R09: one coordinator and two workers, bounded plans/retries, reservations, LangGraph/MongoDBSaver, actual process death after acceptance and after reservation, and selective evidence-availability revisions are implemented. The recovery report records real process IDs, exit codes 86/87, fresh-process epochs, and retained uncertainty. The 512-token reservation fixture is artificial operational accounting; it is not measured model usage. Active revision evidence: `artifacts/safe_harbor/revision-e2e/context-assessment-integrated/report.json`, with two rejected in-flight branches, preserved unrelated reference work, stale historical assessments, and completed successor work.
- R10: context packets retain mandatory metadata and source IDs, select bounded summaries, preserve exact original artifacts, and enforce a 60 KB packet cap. Mandatory `retrieve_evidence` is separate from configurable scientific tools and permits only the same run's accepted ancestors and frozen source assets. Every available artifact hash enters the task read set; missing subtrees retain the artifact dependency. E2E measured 39,182 context bytes and rejected evaluator-only, unknown-manifest, other-run, and withdrawn historical control reads.
- R11: assessments preserve independent screen/evidence/freshness axes, named frozen criterion outputs, nine structured numerical fields, citation maps, exclusion decision, unresolved questions, and limitations. Numeric values are checked against the consumed scientific outputs. Invalid model proposals remain inspectable and result in unresolved/null accepted output with validation errors. The read-only validation endpoint labels its output `deterministic_validation` and never calls a model or changes scientific state. E2E accepted a structurally valid operational fixture and rejected incorrect numbers, unsupported citations, H9 context, and an exclusion conclusion without current control evidence.
- R12: run creation freezes selected reference assets and the source/criteria manifest. Export includes ordered events, the matching snapshot watermark, bounded audit history, immutable assessment revisions, and frozen source assets. E2E checked artifact hashes, historical-state equality, and exact reconstruction of exported current state from events. Original experimental workbooks remain external files with recorded immutable byte hashes and source URLs.

R10–R12 proof: `artifacts/safe_harbor/context-assessment-e2e/2026-09-26-proof/report.json`, run `run-aba04242b1ce4e5689db2f7c136e4c28`, real API process 90358, isolated MongoDB database `safe_harbor_operational_1790449084`. Its complete export is adjacent to the report.

Reproduce from the standalone repository:

```sh
PYTHONPATH=backend:. .venv/bin/python e2e/safe_harbor/runtime_operations.py
PYTHONPATH=backend:. .venv/bin/python e2e/safe_harbor/revision_operations.py
PYTHONPATH=backend:. .venv/bin/python e2e/safe_harbor/context_assessment_export.py
```

These are actual API/process/MongoDB journeys using deterministic operational adapters. Recovery and revision fixtures use explicitly mock harness topologies; the context/assessment/export journey executes the developer-authored fixed baseline on real genomic inputs. None establishes model quality or improvement. The real OpenRouter adapter, model/provider/settings/pricing freeze, per-request conservative token/dollar reservation, and strict evidence validation are implemented, but paid inference remains unverified until credentials are configured. Public endpoint pricing preflight was verified without a model call. A price or usage uncertainty cannot establish a cost win.

Next dependencies: complete real-model R06/Q01 execution after configuration; independent Q03–Q10 journeys remain owned by their external ticket assignees; H03–H08 own fair model evaluation, automatic proposals and promotion. No automatic harness or model-performance result is claimed by this report.

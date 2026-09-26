# Safe Harbor — implementation instructions

The user's Safe Harbor handoff is the specification. This is the standalone Safe Harbor repository. No Living Atlas runtime is included. Work from main; inspect live SH-* issue claims before editing.

NO UNIT TESTS. NO COMPONENT TESTS. E2E ONLY. Build, type, syntax, schema and data-integrity checks are allowed.

Integrator owns shared/, root configuration, dependency manifests, startup, and integration. Data owns backend/safe_harbor/science/ and data/safe_harbor/. Runtime owns backend/safe_harbor/runtime/ and backend/safe_harbor/api.py. UI owns frontend/src/ excluding contracts (import shared/contracts.ts). Ask integrator before changing shared interfaces. Small integrated increments; no parallel edits to another lane's files.

GRCh38 reference; H1 human embryonic stem cell context. Published shortlist, not newly discovered. Never label a locus globally safe. Separate screen_status, evidence_status and freshness. Missing required evidence means incomplete; missing experimental evidence is not a negative result. Use actual files, hashes, source rows, verified coordinates and real reference sequence. Preserve H9 as a different context. Cancer-gene evidence unavailable unless documented. GENCODE v36 is a new annotation analysis.

MongoDB application ledger is authoritative. Accept application state and ordered events transactionally. Checkpoints are a separate recovery aid. Max two workers, 24 nodes, three replans, one transient retry; enforce durable budgets. Identical operation IDs deduplicate, conflicting hashes reject. Record query scope dependencies including empty results.

Harness changes must be saved, bounded, executable structural patches. Fixed scientific criteria, evaluation, input data, model and budgets. Freeze per run. Distinguish mock, deterministic operational, real model, recorded replay. No fabricated improvements. Only E2E checks and honest measured results.

Ticket reports: changed paths; what works; acceptance evidence; limitations; next dependent ticket. No secrets in commits or outputs. Do not send messages or publish externally without user instruction.

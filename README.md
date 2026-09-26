# Safe Harbor

Safe Harbor uses real genome data to investigate published candidate DNA insertion sites and tests changes to its own workflow to improve those investigations.

**Standalone project:** [Nathan-T-Ray/Safe-Harbor](https://github.com/Nathan-T-Ray/Safe-Harbor). Work from `main`. The previous MongoDB/Living Atlas repository is not this project's working repository.

**[Contributor tickets and claims](docs/safe-harbor/TICKETS.md)** · [Claim protocol](docs/safe-harbor/CONTRIBUTING.md) · [Specification](docs/safe-harbor/SPECIFICATION.md) · [Startup](docs/safe-harbor/STARTUP.md)

## Start implementing

Read an available SH-* ticket, inspect its dependencies and reserved paths, and claim it visibly before editing. Active ownership stays on the live GitHub issue. Submit small PRs to `main`. Shared contracts/dependencies are integrator-owned.

Priority available lanes: D08–D09 independent reference answers/splits; H03–H08 competent baselines, isolated scoring, real automatic proposal and promotion; R10–R12 bounded context, validated assessments and replayable export; Q01–Q12 actual E2Es. Existing data/runtime/UI and H01–H02 work is claimed; do not duplicate it.

## Current implementation

GRCh38 reference, H1 context, publication-derived Pansio-1, Olônne-18 and Keppel-19. Real source tables, hashes, reference sequence and GENCODE v36 annotations are ingested. React genome/graph/evidence/replay UI, FastAPI/MongoDB transactional ledger, LangGraph checkpoints, scoped calculations and saved executable harness are implemented and being integrated.

A computational pass covers named criteria only; endpoint support requires named assay/context. Missing required evidence means incomplete. No global biological-safety claim or model-improvement result is made. Real model credentials and fair comparison execution remain pending.

**NO UNIT TESTS. NO COMPONENT TESTS. E2E ONLY.** Build, type, syntax, schema and data-integrity checks are permitted.

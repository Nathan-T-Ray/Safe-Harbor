# Safe Harbor

Safe Harbor uses real genome data to investigate published candidate DNA insertion sites and tests changes to its own workflow to improve those investigations.

**Standalone project:** [Nathan-T-Ray/Safe-Harbor](https://github.com/Nathan-T-Ray/Safe-Harbor). Work from `main`. The previous MongoDB/Living Atlas repository is not this project's working repository.

**[Contributor tickets and claims](docs/safe-harbor/TICKETS.md)** · [Claim protocol](docs/safe-harbor/CONTRIBUTING.md) · [Specification](docs/safe-harbor/SPECIFICATION.md) · [Startup](docs/safe-harbor/STARTUP.md)

## Start implementing

Read an available SH-* ticket, inspect its dependencies and reserved paths, and claim it visibly before editing. Active ownership stays on the live GitHub issue. Push small verified increments directly to `main`; the user has explicitly requested direct integration. Shared contracts/dependencies are integrator-owned.

The live board marks accepted work DONE and shows the remaining automatic-harness/comparison and final demonstration work. Check it before starting; do not duplicate completed implementation or overlap an active file claim. Scientific/runtime/scoring code is frozen during a comparison, while documentation and UI integrations can continue.

## Current implementation

GRCh38 reference, H1 context, publication-derived Pansio-1, Olônne-18 and Keppel-19. Real source tables, hashes, reference sequence and GENCODE v36 annotations are ingested. React genome/graph/evidence/replay UI, FastAPI/MongoDB transactional ledger, LangGraph checkpoints, scoped calculations and saved executable harness are implemented and being integrated.

A computational pass covers named criteria only; endpoint support requires named assay/context. Missing required evidence means incomplete. No global biological-safety claim is made.

A genuine R0 investigation completed with 18/18 required outputs and verified browser/replay state. A real model also proposed an executable structural change: it added an upstream reviewer and moved a tool. Validation rejected that version for support/completion regressions; the system retained and reused the original saved workflow. This demonstrates tested adaptation and honest selection, without a measured improvement. Final comparison cases are still running.

See [the baseline walkthrough](docs/safe-harbor/DEMO.md), [automatic change and rejection](docs/safe-harbor/AUTOMATIC_HARNESS_DEMO.md), [actual process/revision proof](docs/safe-harbor/CONTINUITY_DEMO.md), [comparison limitations](docs/safe-harbor/COMPARISON_LIMITATIONS.md), and [current status](docs/safe-harbor/STATUS.md).

**NO UNIT TESTS. NO COMPONENT TESTS. E2E ONLY.** Build, type, syntax, schema and data-integrity checks are permitted.

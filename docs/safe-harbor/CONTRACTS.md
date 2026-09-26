# Version 1 contract

`shared/contracts.ts` and `shared/contracts.py` define the same v1 records. Root alone changes them; request additive changes by message.

Coordinates are GRCh38, canonical chr identifiers, zero-based half-open. No guessed candidates in the live catalog. Missing data returns explicit unavailable/unknown, never invented intervals/bases. Fixtures have mode mock.

Collections: runs/tasks/artifacts/assessments/harness_versions/evaluations/operations/events, plus MongoDBSaver collections. Artifacts and assessment revisions remain immutable; current pointers/live entities are materialized from committed events. Full small-record upserts. Large bytes remain external, immutable/hashes.

GET /catalog returns Catalog. POST /runs accepts CreateRun and returns {run_id}. GET /runs/{id}/snapshot returns Snapshot with a consistent through_sequence. GET /runs/{id}/events?after_sequence=N returns {events,through_sequence,has_more}. GET /runs/{id}/artifacts/{artifact_id} returns scoped Artifact. POST /runs/{id}/resume returns {run_id,status}. POST /runs/{id}/evidence-revisions accepts {fixture_id}; fixed fixtures only. POST /experiments accepts {mode,candidate_ids?}; GET /experiments/{id} returns stored experiment. GET /runs/{id}/export returns full versioned records/events/manifests. Additional /health allowed.

Every event: schema_version 1, run_id, sequence, event_id, operation_id, occurred_at, type state.committed, cause, run_revision, upserts. Upsert maps use collection names and arrays, including runs. Snapshot uses singular run. Replay starts with empty entities and applies events sequentially; seek rebuilds from immutable events, never final snapshots.

Science interface: backend.safe_harbor.science (installed safe_harbor.science): get_catalog(), inspect_candidate(candidate_id), run_tool(tool_name,candidate_id,arguments={}). Results are JSON-compatible dicts, bounded, evidence IDs and source/provenance attached. Root/runtime must not infer scientific verdicts from frontend calculations.

Every run freezes harness_hash and budget limits. Role task compilation creates actual dependencies. Application acceptance validates operation content hash, coordinator epoch, read-set version (including query scope versions even when empty), commits outputs/tasks/budget/event/operation together. No inference in transactions. Max 2 workers, 24 nodes, 3 replans, 1 transient retry.

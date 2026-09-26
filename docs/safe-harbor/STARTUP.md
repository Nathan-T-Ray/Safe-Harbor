# Startup

Configuration is server-side in ignored `.env`. The authoritative MongoDB deployment is MongoDB Atlas, selected by `MONGODB_URI`; there is no silent localhost fallback. Never commit credentials.

Prerequisites: Python 3.11 or newer, Node.js 22.12 or newer, and a MongoDB Atlas cluster (see below). `mongod` on PATH is only needed for the explicit offline fallback. `pip` installs the MongoDB client; it does not install the database server. Contributors do not need a model key for deterministic operational E2Es.

Run from this checkout's root:

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.lock
.venv/bin/pip install --no-deps -e backend
npm ci --prefix frontend
.venv/bin/python scripts/safe_harbor_dev.py
```

## MongoDB Atlas setup

1. In MongoDB Atlas, create a project and a cluster (M0 works for development; it is limited to 512 MB storage, about 100 databases and 500 collections, and every E2E journey creates its own scratch database).
2. Database Access: create a database user with read/write access (for example `readWriteAnyDatabase`, since journeys create and drop isolated `sh_e2e_*` databases).
3. Network Access: add your current public IP to the IP Access List. Connections from unlisted IPs time out at server selection.
4. Connect -> Drivers: copy the `mongodb+srv://` connection string. Copy `.env.example` to `.env` if you have none, then set `MONGODB_URI` to that string with the real user and URL-encoded password, and keep `MONGODB_DATABASE=safe_harbor`. `.env` is ignored; never commit it.
5. Prove connectivity (ping, a majority-write-concern multi-document transaction with commit and abort, and one deterministic investigation through the real API on port 8096 with LangGraph checkpoints written to Atlas):

```sh
set -a; . ./.env; set +a
PYTHONPATH=backend:. .venv/bin/python e2e/safe_harbor/atlas_connectivity.py
```

   It fails if `MONGODB_URI` is not an Atlas (`*.mongodb.net`) host and writes `artifacts/safe_harbor/atlas-connectivity/<timestamp>/report.json` with latency and the credential-free target description.
6. Optional: copy existing data from the local replica set. The default is a dry run that prints databases, collections, counts, indexes and estimated size; `--execute` copies raw BSON (preserving `_id` and every document exactly), recreates indexes and verifies counts plus order-independent content digests per collection:

```sh
PYTHONPATH=backend:. .venv/bin/python scripts/migrate_to_atlas.py                          # plan only
PYTHONPATH=backend:. .venv/bin/python scripts/migrate_to_atlas.py --execute                # copy + verify MONGODB_DATABASE
PYTHONPATH=backend:. .venv/bin/python scripts/migrate_to_atlas.py --prefix safe_harbor --execute
```

   The source defaults to `mongodb://127.0.0.1:27021/?replicaSet=safe-harbor-dev` (override with `--source-uri` or `SOURCE_MONGODB_URI`). A non-empty target collection is refused unless `--mode skip` or `--mode replace` is given. Reports go to `artifacts/safe_harbor/atlas-migration/<timestamp>/report.json`; connection strings are always redacted.

Offline fallback only: `scripts/safe_harbor_dev.py --local-mongo` starts a dedicated `safe-harbor-dev` replica set on 127.0.0.1:27021 with ignored data files, for work without network access. Point `MONGODB_URI` at it explicitly; results from it are not Atlas evidence. Stop only processes you started.

UI: http://127.0.0.1:5174. API: http://127.0.0.1:8010/docs. Startup uses strict ports so an unrelated service cannot silently be mistaken for Safe Harbor. API startup includes the coordinator; no second queue platform is needed. Ctrl-C stops children started by this launcher.

The current integration session uses UI port 5176 and API port 8016. Override launcher ports with `--ui-port 5176 --api-port 8016` when they are free. Port selection is operational configuration, not part of the exported scientific provenance.

Committed normalized assets allow startup without re-downloading or regenerating the scientific pack. Copy `.env.example` to `.env` only if no existing file is present. Deterministic operational runs need no model key. For genuine runs, configure the key only in this ignored file; the example fixes the selected model/provider and the tested low-reasoning/8192-output settings. API request bodies carry assigned budgets; UI/comparison requests use400000tokens/40tools/USD5.

Optional scientific re-ingestion is a separate data-version operation: `.venv/bin/python -m safe_harbor.science.ingest`, then `.venv/bin/python -m safe_harbor.science.verify_data`. It downloads originals to ignored raw storage and can change raw response hashes, so do not run it during a frozen comparison. Read DATA.md and PROVENANCE.md for original sources, raw-byte versus reference-base identity and limitations. Current implementation status and incomplete release gates are in STATUS.md.

Model runs must use configured provider access and record model identity/usage. Deterministic operational mode is visibly labeled and is not model-improvement evidence.

## Backend and operational E2Es

After dependency installation and MongoDB startup, API-only execution is:

```sh
PYTHONPATH=backend:. .venv/bin/python -m uvicorn safe_harbor.api:app --host 127.0.0.1 --port 8010
```

In another terminal, these journeys create isolated databases and their own API processes. Choose unused ports; do not run two journeys on the same port. They use deterministic adapters even if server credentials are configured.

```sh
PYTHONPATH=backend:. .venv/bin/python e2e/safe_harbor/runtime_operations.py --port 8021
PYTHONPATH=backend:. .venv/bin/python e2e/safe_harbor/revision_operations.py --port 8022
PYTHONPATH=backend:. .venv/bin/python e2e/safe_harbor/context_assessment_export.py --port 8023
```

The reproducible evaluation operational journey uses an already running API and never invokes a configured real model:

```sh
.venv/bin/python e2e/safe_harbor/evaluation_operational.py --base-url http://127.0.0.1:8010
```

All commands above exercise actual HTTP/process/MongoDB behavior. If an independent contributor cannot run a database in their environment, push the executable E2E and its invocation to main with an explicit unexecuted status. The integrator runs it locally and attaches measured results; unexecuted scripts are not accepted as passing tests. Synthetic-provider journeys must explicitly clear real credentials in their child-process environment and label their usage as synthetic.

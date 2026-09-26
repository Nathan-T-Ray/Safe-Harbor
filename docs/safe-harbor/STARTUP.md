# Startup

Configuration is server-side in ignored `.env`. Initial target is a local transaction-capable MongoDB replica set; Atlas can be selected with MONGODB_URI. Never commit credentials.

Run from this checkout's root:

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.lock
.venv/bin/pip install --no-deps -e backend
npm ci --prefix frontend
.venv/bin/python -m safe_harbor.science.ingest
.venv/bin/python -m safe_harbor.science.verify_data
.venv/bin/python scripts/safe_harbor_dev.py --local-mongo
```

The optional `--local-mongo` starts a dedicated `safe-harbor-dev` replica set on 127.0.0.1:27021 with ignored data files. Without that flag, MONGODB_URI selects the database. This project's operational E2Es use the dedicated Safe Harbor replica set; no previous project's database is required. Stop only processes you started.

UI: http://127.0.0.1:5174. API: http://127.0.0.1:8010/docs. Startup uses strict ports so an unrelated service cannot silently be mistaken for Safe Harbor. API startup includes the coordinator; no second queue platform is needed. Ctrl-C stops children started by this launcher.

The current integration session uses UI port 5176 and API port 8016. Override launcher ports with `--ui-port 5176 --api-port 8016` when they are free. Port selection is operational configuration, not part of the exported scientific provenance.

Committed normalized assets allow immediate catalog inspection; reproducible ingestion fetches the hashed originals to ignored raw storage. Read DATA.md for original source URLs and limitations. Current implementation status and incomplete release gates are in STATUS.md.

Model runs must use configured provider access and record model identity/usage. Deterministic operational mode is visibly labeled and is not model-improvement evidence.

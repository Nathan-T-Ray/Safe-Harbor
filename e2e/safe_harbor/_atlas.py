"""MongoDB target plumbing shared by the Safe Harbor E2E journeys and scripts.

MongoDB Atlas is the authoritative target. Every journey talks to whatever MONGODB_URI names
(via ``safe_harbor.mongo``); there is no localhost fallback and child API processes inherit
MONGODB_URI from the environment unchanged. Journeys create one isolated database per run, so:

* every journey database is named ``sh_e2e_<label>_<unix time>_<hex>`` (``E2E_DB_PREFIX``),
  which ``scripts/atlas_cleanup.py`` can list and drop (Atlas shared tiers cap databases and
  collections);
* journeys drop their own database when they finish unless ``--keep-db`` is given; the JSON
  report and exports on disk remain the evidence;
* reports record ``mongo_target`` (credential-free ``describe_target()``) so evidence shows
  whether a run used Atlas or a self-managed deployment.
"""
from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _path in (ROOT / "backend", ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from safe_harbor.mongo import (  # noqa: E402,F401  (re-exported for journeys and scripts)
    DEFAULT_DATABASE, database_name, describe_target, is_atlas, make_client, mongo_uri, redact,
)

E2E_DB_PREFIX = "sh_e2e_"
PROTECTED_DATABASES = {"admin", "config", "local"}
_MAX_DB_NAME = 63  # MongoDB database names must be shorter than 64 bytes


def e2e_database(label: str) -> str:
    """A fresh, prefixed database name for one journey run."""
    suffix = f"_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    label = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in label)
    return E2E_DB_PREFIX + label[: _MAX_DB_NAME - len(E2E_DB_PREFIX) - len(suffix)] + suffix


def main_database() -> str:
    """The application's primary database, which cleanup must never drop."""
    return os.getenv("MONGODB_DATABASE", DEFAULT_DATABASE)


def child_env(database: str, **extra: str) -> dict:
    """Environment for a spawned API/coordinator process.

    MONGODB_URI is inherited as-is (fails fast here if it is missing); only the isolated
    database name and PYTHONPATH are set, plus any journey-specific ``extra`` values.
    """
    mongo_uri()
    env = dict(os.environ)
    env.update(PYTHONPATH=f"{ROOT / 'backend'}:{ROOT}", MONGODB_DATABASE=database)
    env.update(extra)
    return env


def target(database: str) -> dict:
    """Credential-free description of the deployment plus the journey's own database."""
    return {**describe_target(), "database": database}


def add_keep_db_flag(parser) -> None:
    parser.add_argument("--keep-db", action="store_true",
                        help="keep the isolated journey database after the run (default: drop it; Atlas caps database/collection counts)")


def drop_journey_database(database: str, keep: bool, client=None) -> dict:
    """Drop the journey's isolated database unless kept. Never touches non-prefixed databases."""
    if keep:
        return {"database": database, "dropped": False, "reason": "--keep-db"}
    if not database.startswith(E2E_DB_PREFIX) or database == main_database() or database in PROTECTED_DATABASES:
        return {"database": database, "dropped": False, "reason": "not an sh_e2e_ journey database"}
    owned = client is None
    client = client or make_client()
    try:
        client.drop_database(database)
        return {"database": database, "dropped": True}
    except Exception as exc:  # cleanup must never turn a recorded result into a crash
        return {"database": database, "dropped": False, "reason": f"{exc.__class__.__name__}: {exc}"}
    finally:
        if owned:
            client.close()

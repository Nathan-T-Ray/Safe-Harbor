"""Single source of MongoDB connection settings. MongoDB Atlas is the authoritative target.

Every process (API, coordinator, harness store, scripts, E2E journeys) must obtain its client
through here so TLS, write concern and timeouts are identical everywhere. There is deliberately
no localhost fallback: a missing MONGODB_URI is a configuration error, not a silent switch to a
different database.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import certifi
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)

DEFAULT_DATABASE = "safe_harbor"


class MongoConfigurationError(RuntimeError):
    pass


def mongo_uri() -> str:
    uri = (os.getenv("MONGODB_URI") or "").strip()
    if not uri:
        raise MongoConfigurationError(
            "MONGODB_URI is not set. Put the MongoDB Atlas connection string "
            "(mongodb+srv://<user>:<password>@<cluster>.mongodb.net/...) in the ignored .env file."
        )
    return uri


def database_name(default: str = DEFAULT_DATABASE) -> str:
    return os.getenv("MONGODB_DATABASE", default)


def is_atlas(uri: str | None = None) -> bool:
    host = urlsplit(uri or mongo_uri()).hostname or ""
    return host.endswith(".mongodb.net")


def describe_target(uri: str | None = None) -> dict:
    """Credential-free description of the configured deployment, safe to log or return from /health."""
    parts = urlsplit(uri or mongo_uri())
    host = parts.hostname or ""
    return {
        "scheme": parts.scheme,
        "host": host,
        "kind": "atlas" if host.endswith(".mongodb.net") else "self_managed",
        "database": database_name(),
    }


def redact(uri: str) -> str:
    return re.sub(r"//([^@/]+)@", "//<credentials>@", uri)


def client_options(uri: str) -> dict:
    options = {
        "serverSelectionTimeoutMS": int(os.getenv("MONGODB_SERVER_SELECTION_TIMEOUT_MS", "15000")),
        "tz_aware": True,
        "appname": "safe-harbor",
        "retryWrites": True,
        "w": "majority",
    }
    if uri.startswith("mongodb+srv://") or "tls=true" in uri.lower() or "ssl=true" in uri.lower():
        options["tlsCAFile"] = certifi.where()
    return options


def make_client(uri: str | None = None, **overrides) -> MongoClient:
    uri = uri or mongo_uri()
    return MongoClient(uri, **{**client_options(uri), **overrides})

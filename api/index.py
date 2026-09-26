"""Vercel serverless entry point: read-only Safe Harbor API mounted at /api.

Serves the catalog and recorded runs (snapshot, events, artifacts, export) from MongoDB Atlas.
The coordinator never runs here; POST requests return 503. Configure MONGODB_URI and
MONGODB_DATABASE as Vercel environment variables.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]
os.environ["SAFE_HARBOR_READ_ONLY"] = "1"

from fastapi import FastAPI  # noqa: E402

from safe_harbor.api import app as safe_harbor_api  # noqa: E402

app = FastAPI(title="Safe Harbor (read-only)", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/api", safe_harbor_api)

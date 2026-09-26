#!/usr/bin/env python3
"""List, and with --yes drop, per-run E2E databases on the MONGODB_URI deployment (MongoDB Atlas).

Atlas shared tiers cap the number of databases and collections, and every Safe Harbor journey
creates one isolated database named ``sh_e2e_<label>_<unix time>_<hex>``. Default is a dry run
that prints what would be dropped. The application database (MONGODB_DATABASE) and the
admin/config/local databases are never dropped, whatever the prefix.

  set -a; . ./.env; set +a
  PYTHONPATH=backend:. .venv/bin/python scripts/atlas_cleanup.py                       # dry run
  PYTHONPATH=backend:. .venv/bin/python scripts/atlas_cleanup.py --older-than-hours 6 --yes
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "e2e" / "safe_harbor")]

from _atlas import E2E_DB_PREFIX, PROTECTED_DATABASES, describe_target, main_database, make_client  # noqa: E402

STAMP = re.compile(r"_(\d{10})_[0-9a-f]{6}$")


def created_at(name: str) -> int | None:
    match = STAMP.search(name)
    return int(match.group(1)) if match else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prefix", default=E2E_DB_PREFIX, help=f"database name prefix to match (default {E2E_DB_PREFIX!r})")
    parser.add_argument("--older-than-hours", type=float, default=None,
                        help="only databases whose embedded creation time is older than this; names without a timestamp are skipped")
    parser.add_argument("--yes", action="store_true", help="actually drop the matched databases (default: dry run)")
    args = parser.parse_args()
    if not args.prefix.strip():
        raise SystemExit("Refusing an empty prefix.")

    protected = PROTECTED_DATABASES | {main_database()}
    client = make_client()
    try:
        databases = client.list_databases()
        now = time.time()
        matched, skipped = [], []
        for info in databases:
            name = info["name"]
            if not name.startswith(args.prefix):
                continue
            if name in protected:
                skipped.append({"database": name, "reason": "protected"})
                continue
            stamp = created_at(name)
            age_hours = None if stamp is None else round((now - stamp) / 3600, 2)
            if args.older_than_hours is not None and (age_hours is None or age_hours < args.older_than_hours):
                skipped.append({"database": name, "reason": "younger than --older-than-hours or no timestamp", "age_hours": age_hours})
                continue
            matched.append({"database": name, "age_hours": age_hours, "size_on_disk": info.get("sizeOnDisk")})
        target = describe_target()  # database = the protected application database
        print(json.dumps({"target": target, "prefix": args.prefix, "protected": sorted(protected),
                          "mode": "drop" if args.yes else "dry_run", "matched": matched, "skipped": skipped}, indent=2))
        if not args.yes:
            print(f"Dry run: {len(matched)} database(s) would be dropped. Re-run with --yes to drop them.")
            return 0
        for entry in matched:
            client.drop_database(entry["database"])
            print(f"dropped {entry['database']}", flush=True)
        print(f"Dropped {len(matched)} database(s).")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())

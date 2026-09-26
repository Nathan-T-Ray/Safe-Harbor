#!/usr/bin/env python3
"""Copy Safe Harbor application data from a source MongoDB deployment to MongoDB Atlas, then verify it.

Default is a DRY RUN: it only reads the source (and inspects the target) and prints the plan.
Nothing is written unless --execute is given.

  set -a; . ./.env; set +a
  PYTHONPATH=backend:. .venv/bin/python scripts/migrate_to_atlas.py                 # dry run
  PYTHONPATH=backend:. .venv/bin/python scripts/migrate_to_atlas.py --execute       # copy + verify

Source: --source-uri, else SOURCE_MONGODB_URI, else the local replica set
        mongodb://127.0.0.1:27021/?replicaSet=safe-harbor-dev.
Target: --target-uri, else MONGODB_URI (.env). Must be Atlas (*.mongodb.net) unless --allow-non-atlas.
Databases: --databases a,b | --prefix p | default MONGODB_DATABASE only.
Every collection is copied (application ledger, LangGraph runtime_checkpoints /
runtime_checkpoint_writes and anything else present) as raw BSON, so _id and every field, type and
field order are preserved byte for byte. Secondary indexes are recreated with their names and options.
Verification per collection: count equality plus an order-independent digest, sha256 over the sorted
list of (bson(_id), sha256(raw document bytes)) pairs, computed independently on source and target.
The JSON report goes to artifacts/safe_harbor/atlas-migration/<timestamp>/report.json. Connection
strings are always redacted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

import bson  # noqa: E402
from bson.codec_options import CodecOptions  # noqa: E402
from bson.raw_bson import RawBSONDocument  # noqa: E402
from pymongo import ReplaceOne  # noqa: E402
from pymongo.errors import BulkWriteError, OperationFailure, PyMongoError  # noqa: E402

from safe_harbor.mongo import database_name, describe_target, is_atlas, make_client, mongo_uri, redact  # noqa: E402

DEFAULT_SOURCE_URI = "mongodb://127.0.0.1:27021/?replicaSet=safe-harbor-dev"
SYSTEM_DATABASES = {"admin", "local", "config"}
RAW = CodecOptions(document_class=RawBSONDocument)
# MongoDB Atlas M0 (free) limits: https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/
M0_STORAGE_BYTES = 512 * 1024 * 1024
M0_MAX_DATABASES = 100
M0_MAX_COLLECTIONS = 500
# Index options that list_indexes() reports but create_index() must not receive.
INDEX_SKIP_KEYS = {"key", "v", "ns"}


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def human(n: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if abs(n) < 1024 or unit == "GiB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GiB"


# --------------------------------------------------------------------------- inspection
def list_user_collections(db) -> list[dict]:
    """Collections and views, excluding system.* namespaces."""
    found = []
    for info in db.list_collections():
        if info["name"].startswith("system."):
            continue
        found.append({"name": info["name"], "type": info.get("type", "collection"), "options": dict(info.get("options") or {})})
    return sorted(found, key=lambda item: item["name"])


def collection_stats(db, name: str) -> dict:
    try:
        stats = next(db[name].aggregate([{"$collStats": {"storageStats": {}}}]))["storageStats"]
        return {"size": int(stats.get("size", 0)), "storage_size": int(stats.get("storageSize", 0)), "index_size": int(stats.get("totalIndexSize", 0))}
    except (PyMongoError, StopIteration, KeyError):
        return {"size": None, "storage_size": None, "index_size": None}


def index_specs(collection) -> list[dict]:
    specs = []
    for index in collection.list_indexes():
        spec = dict(index)
        specs.append({"name": spec["name"], "key": list(spec["key"].items()), "options": {k: v for k, v in spec.items() if k not in INDEX_SKIP_KEYS and k != "name"}})
    return sorted(specs, key=lambda item: item["name"])


def digest(collection) -> dict:
    """Order-independent content digest: sha256 over sorted (bson(_id), sha256(raw doc)) pairs."""
    pairs = []
    for document in collection.with_options(codec_options=RAW).find({}):
        raw = document.raw
        id_bytes = bson.encode({"_id": document["_id"]})
        pairs.append((id_bytes, hashlib.sha256(raw).digest()))
    pairs.sort()
    outer = hashlib.sha256()
    for id_bytes, doc_hash in pairs:
        outer.update(len(id_bytes).to_bytes(4, "big"))
        outer.update(id_bytes)
        outer.update(doc_hash)
    return {"count": len(pairs), "sha256": outer.hexdigest()}


def resolve_databases(client, args) -> list[str]:
    available = sorted(set(client.list_database_names()) - SYSTEM_DATABASES)
    if args.databases:
        return [name.strip() for name in args.databases.split(",") if name.strip()]
    if args.prefix:
        return [name for name in available if name.startswith(args.prefix)]
    return [database_name()]


def target_name(source: str, args, count: int) -> str:
    if args.target_database:
        if count != 1:
            raise SystemExit("--target-database needs exactly one source database; use --target-database-suffix for several.")
        return args.target_database
    return source + (args.target_database_suffix or "")


# --------------------------------------------------------------------------- copying
def ensure_collection(target_db, spec: dict) -> None:
    if spec["name"] in target_db.list_collection_names():
        return
    options = {k: v for k, v in spec["options"].items() if k not in {"uuid"}}
    try:
        target_db.command({"create": spec["name"], **options})
    except OperationFailure as exc:
        if exc.code != 48:  # NamespaceExists
            raise


def copy_collection(source_coll, target_coll, mode: str, batch_size: int) -> dict:
    written = skipped = replaced = 0
    batch: list[RawBSONDocument] = []

    def flush():
        nonlocal written, skipped, replaced
        if not batch:
            return
        if mode == "replace":
            result = target_coll.bulk_write([ReplaceOne({"_id": doc["_id"]}, doc, upsert=True) for doc in batch], ordered=False)
            written += result.upserted_count
            replaced += result.matched_count
        else:
            try:
                # RawBSONDocument batches do not populate InsertManyResult.inserted_ids.
                target_coll.insert_many(batch, ordered=False)
                written += len(batch)
            except BulkWriteError as exc:
                errors = exc.details.get("writeErrors", [])
                non_duplicate = [error for error in errors if error.get("code") != 11000]
                if non_duplicate or mode == "fail":
                    raise
                written += exc.details.get("nInserted", 0)
                skipped += len(errors)
        batch.clear()

    for document in source_coll.with_options(codec_options=RAW).find({}, batch_size=batch_size, no_cursor_timeout=False):
        batch.append(document)
        if len(batch) >= batch_size:
            flush()
    flush()
    return {"inserted": written, "skipped_existing": skipped, "replaced": replaced}


def recreate_indexes(source_specs: list[dict], target_coll) -> list[str]:
    existing = {index["name"] for index in target_coll.list_indexes()}
    created = []
    for spec in source_specs:
        if spec["name"] == "_id_" or spec["name"] in existing:
            continue
        target_coll.create_index(spec["key"], name=spec["name"], **spec["options"])
        created.append(spec["name"])
    return created


# --------------------------------------------------------------------------- main
def build_plan(source, target, databases: list[str], args) -> tuple[dict, list[str]]:
    problems: list[str] = []
    plan = {"databases": [], "totals": {"databases": 0, "collections": 0, "documents": 0, "data_bytes": 0, "storage_bytes": 0, "index_bytes": 0}}
    for source_name in databases:
        destination = target_name(source_name, args, len(databases))
        if source_name not in source.list_database_names():
            problems.append(f"source database {source_name!r} does not exist")
            plan["databases"].append({"source": source_name, "target": destination, "exists": False, "collections": []})
            continue
        entry = {"source": source_name, "target": destination, "exists": True, "collections": []}
        source_db = source[source_name]
        target_existing = set()
        if target is not None:
            try:
                target_existing = set(target[destination].list_collection_names())
            except PyMongoError as exc:
                problems.append(f"cannot inspect target database {destination!r}: {type(exc).__name__}")
        for spec in list_user_collections(source_db):
            item = {"name": spec["name"], "type": spec["type"]}
            if spec["type"] == "collection":
                stats = collection_stats(source_db, spec["name"])
                item.update(documents=source_db[spec["name"]].count_documents({}), estimated_bytes=stats["size"], storage_bytes=stats["storage_size"], index_bytes=stats["index_size"],
                            indexes=[index["name"] for index in index_specs(source_db[spec["name"]])])
                target_count = target[destination][spec["name"]].count_documents({}) if target is not None and spec["name"] in target_existing else 0
                item["target_documents_before"] = target_count
                if target_count and args.mode == "fail":
                    problems.append(f"target {destination}.{spec['name']} already holds {target_count} documents (use --mode skip|replace)")
                totals = plan["totals"]
                totals["collections"] += 1
                totals["documents"] += item["documents"]
                totals["data_bytes"] += item["estimated_bytes"] or 0
                totals["storage_bytes"] += item["storage_bytes"] or 0
                totals["index_bytes"] += item["index_bytes"] or 0
            else:
                item["options"] = {k: v for k, v in spec["options"].items() if k in {"viewOn", "pipeline"}}
            entry["collections"].append(item)
        plan["totals"]["databases"] += 1
        plan["databases"].append(entry)
        same_deployment = redact(args.source_uri) == redact(args.target_uri)
        if same_deployment and destination == source_name:
            problems.append(f"source and target are the same deployment and database ({source_name}); refusing to copy onto itself")
    return plan, problems


def m0_warnings(plan: dict, target) -> list[str]:
    warnings = []
    totals = plan["totals"]
    footprint = totals["data_bytes"] + totals["index_bytes"]
    if footprint > M0_STORAGE_BYTES * 0.8:
        warnings.append(f"Data+index size {human(footprint)} is over 80% of the Atlas M0 512 MiB storage limit.")
    target_dbs = None
    if target is not None:
        try:
            target_dbs = len(set(target.list_database_names()) - SYSTEM_DATABASES)
        except PyMongoError:
            pass
    planned_dbs = totals["databases"] + (target_dbs or 0)
    if planned_dbs > M0_MAX_DATABASES:
        warnings.append(f"About {planned_dbs} databases after migration exceeds the Atlas M0 limit of {M0_MAX_DATABASES}.")
    if totals["collections"] > M0_MAX_COLLECTIONS:
        warnings.append(f"{totals['collections']} collections exceeds the Atlas M0 limit of {M0_MAX_COLLECTIONS}.")
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source-uri", default=os.getenv("SOURCE_MONGODB_URI") or DEFAULT_SOURCE_URI)
    parser.add_argument("--target-uri", default=None, help="default: MONGODB_URI")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--databases", help="comma-separated source database names")
    group.add_argument("--prefix", help="copy every non-system source database whose name starts with this prefix")
    parser.add_argument("--target-database", help="rename the (single) source database on the target")
    parser.add_argument("--target-database-suffix", help="append this suffix to every target database name")
    parser.add_argument("--mode", choices=("fail", "skip", "replace"), default="fail",
                        help="existing target documents: fail (default; refuse if a target collection is non-empty), skip existing _id, replace existing _id")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--execute", action="store_true", help="actually write to the target (default is a dry run)")
    parser.add_argument("--dry-run", action="store_true", help="explicit dry run (the default)")
    parser.add_argument("--allow-non-atlas", action="store_true", help="permit a non-Atlas target (labelled stand-in runs only)")
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    if args.execute and args.dry_run:
        parser.error("--execute and --dry-run are mutually exclusive")
    args.target_uri = args.target_uri or mongo_uri()
    execute = args.execute

    target_is_atlas = is_atlas(args.target_uri)
    stamp = utc_stamp()
    output = args.output_dir or ROOT / "artifacts" / "safe_harbor" / "atlas-migration" / stamp
    suffix = 1
    while args.output_dir is None and (output / "report.json").exists():
        suffix += 1
        output = output.with_name(f"{stamp}-{suffix}")
    report = {
        "tool": "scripts/migrate_to_atlas.py", "started_at": datetime.now(timezone.utc).isoformat(),
        "mode": "execute" if execute else "dry_run", "existing_document_mode": args.mode,
        "source": {"uri": redact(args.source_uri), **describe_target(args.source_uri)},
        "target": {"uri": redact(args.target_uri), **describe_target(args.target_uri), "is_atlas": target_is_atlas},
        "stand_in": not target_is_atlas, "warnings": [], "problems": [],
    }
    for side in ("source", "target"):
        report[side].pop("database", None)
    if not target_is_atlas:
        message = "Target is not MongoDB Atlas (*.mongodb.net)."
        if execute and not args.allow_non_atlas:
            report["problems"].append(message + " Refusing --execute without --allow-non-atlas.")
        else:
            report["warnings"].append(message + (" Labelled stand-in run (--allow-non-atlas)." if args.allow_non_atlas else " --execute would refuse without --allow-non-atlas."))

    source = make_client(args.source_uri)
    target = None
    try:
        source.admin.command("ping")
    except PyMongoError as exc:
        report["problems"].append(f"source unreachable ({redact(args.source_uri)}): {type(exc).__name__}")
        return finish(report, output, 2)
    try:
        target = make_client(args.target_uri)
        started = time.perf_counter()
        target.admin.command("ping")
        report["target"]["ping_ms"] = round((time.perf_counter() - started) * 1000, 2)
    except PyMongoError as exc:
        report["problems"].append(f"target unreachable ({redact(args.target_uri)}): {type(exc).__name__}: {redact(str(exc))[:300]}")
        target = None

    databases = resolve_databases(source, args)
    if not databases:
        report["problems"].append("no source databases selected")
        return finish(report, output, 2)
    plan, problems = build_plan(source, target, databases, args)
    report["plan"] = plan
    report["problems"].extend(problems)
    report["warnings"].extend(m0_warnings(plan, target))
    print_plan(plan)

    if not execute:
        report["result"] = "dry_run_only"
        return finish(report, output, 1 if report["problems"] else 0)
    if report["problems"] or target is None:
        report["result"] = "refused"
        return finish(report, output, 2)

    report["collections"] = []
    all_ok = True
    for entry in plan["databases"]:
        source_db, target_db = source[entry["source"]], target[entry["target"]]
        specs = {spec["name"]: spec for spec in list_user_collections(source_db)}
        # Real collections first so views can resolve against them.
        for item in sorted(entry["collections"], key=lambda item: item["type"] != "collection"):
            name = item["name"]
            record = {"database": entry["source"], "target_database": entry["target"], "collection": name, "type": item["type"]}
            started = time.perf_counter()
            if item["type"] == "view":
                if name not in target_db.list_collection_names():
                    target_db.command({"create": name, "viewOn": specs[name]["options"]["viewOn"], "pipeline": specs[name]["options"].get("pipeline", [])})
                record["result"] = "view_recreated"
                report["collections"].append(record)
                continue
            ensure_collection(target_db, specs[name])
            record["copy"] = copy_collection(source_db[name], target_db[name], args.mode, args.batch_size)
            source_indexes = index_specs(source_db[name])
            record["indexes_created"] = recreate_indexes(source_indexes, target_db[name])
            record["copy_seconds"] = round(time.perf_counter() - started, 3)
            source_digest, target_digest = digest(source_db[name]), digest(target_db[name])
            target_indexes = index_specs(target_db[name])
            record["verify"] = {
                "source_count": source_digest["count"], "target_count": target_digest["count"],
                "source_sha256": source_digest["sha256"], "target_sha256": target_digest["sha256"],
                "count_match": source_digest["count"] == target_digest["count"],
                "digest_match": source_digest["sha256"] == target_digest["sha256"],
                "index_names_source": [index["name"] for index in source_indexes],
                "index_names_target": [index["name"] for index in target_indexes],
                "indexes_match": [(i["name"], i["key"]) for i in source_indexes] == [(i["name"], i["key"]) for i in target_indexes],
            }
            record["passed"] = all(record["verify"][key] for key in ("count_match", "digest_match", "indexes_match"))
            all_ok &= record["passed"]
            print(f"  {entry['source']}.{name} -> {entry['target']}.{name}: {record['copy']} "
                  f"count {source_digest['count']}/{target_digest['count']} digest {'OK' if record['verify']['digest_match'] else 'MISMATCH'} "
                  f"indexes {'OK' if record['verify']['indexes_match'] else 'MISMATCH'}")
            report["collections"].append(record)
    verified = [record for record in report["collections"] if "passed" in record]
    report["summary"] = {"collections_verified": len(verified), "collections_passed": sum(r["passed"] for r in verified),
                         "documents_copied": sum(r["copy"]["inserted"] + r["copy"]["replaced"] for r in verified)}
    report["result"] = "verified" if all_ok else "verification_failed"
    return finish(report, output, 0 if all_ok else 1)


def print_plan(plan: dict) -> None:
    print("Migration plan")
    for entry in plan["databases"]:
        print(f"  database {entry['source']} -> {entry['target']}" + ("" if entry["exists"] else "  (MISSING on source)"))
        for item in entry["collections"]:
            if item["type"] != "collection":
                print(f"    {item['name']}: {item['type']}")
                continue
            print(f"    {item['name']}: {item['documents']} docs, ~{human(item['estimated_bytes'] or 0)}, "
                  f"target before {item['target_documents_before']}, indexes {', '.join(item['indexes'])}")
    totals = plan["totals"]
    print(f"  totals: {totals['databases']} db, {totals['collections']} collections, {totals['documents']} docs, "
          f"data {human(totals['data_bytes'])}, indexes {human(totals['index_bytes'])}")


def finish(report: dict, output: Path, code: int) -> int:
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["exit_code"] = code
    output.mkdir(parents=True, exist_ok=True)
    path = output / "report.json"
    text = json.dumps(report, indent=2, default=str)
    path.write_text(text + "\n")
    print(text)
    for warning in report["warnings"]:
        print("WARNING:", warning, file=sys.stderr)
    for problem in report["problems"]:
        print("PROBLEM:", problem, file=sys.stderr)
    print(f"report: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())

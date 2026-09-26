"""Bounded context and same-run, ancestor-only immutable evidence retrieval."""
from __future__ import annotations

import copy
import json

from safe_harbor.runtime.ledger import LedgerError

RUNTIME_TOOLS = ["retrieve_evidence"]
RETRIEVAL_DEFINITION = {"type": "function", "function": {"name": "retrieve_evidence", "description": "Retrieve an exact immutable evidence artifact from this task's manifest only. Use pointer to select a JSON subtree, offset/limit for arrays. No arbitrary files, URLs, evaluator data or other runs.", "parameters": {"type": "object", "properties": {"artifact_id": {"type": "string"}, "pointer": {"type": "string", "description": "JSON pointer, e.g. /calculation/nearest_de_genes"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": 20}}, "required": ["artifact_id"], "additionalProperties": False}}}


def available_artifacts(ledger, run: dict, task: dict) -> list[dict]:
    ids = [f"{run['run_id']}:reference:{task['candidate_id']}", f"{run['run_id']}:source-manifest"]
    frontier, visited = list(task["depends_on"]), set()
    while frontier:
        parent_id = frontier.pop(0)
        if parent_id in visited:
            continue
        visited.add(parent_id)
        parent = ledger.db.tasks.find_one({"run_id": run["run_id"], "task_id": parent_id, "status": "complete"}, {"_id": 0})
        if parent:
            frontier.extend(parent["depends_on"])
            ids.extend(parent.get("result_artifact_ids", []))
    records = {artifact["artifact_id"]: artifact for artifact in ledger.db.artifacts.find({"run_id": run["run_id"], "artifact_id": {"$in": ids}, "kind": {"$ne": "worker_trace"}}, {"_id": 0})}
    return [records[key] for key in dict.fromkeys(ids) if key in records]


def compact_artifact(artifact: dict) -> dict:
    result = copy.deepcopy(artifact)
    # Keep computed scalar values and closest entries; full rows remain retrievable by ID.
    def bounded(value, path=""):
        if isinstance(value, dict):
            return {key: bounded(item, f"{path}/{key}") for key, item in value.items() if key not in ("sequence", "bases", "source_rows_preview", "shared_rows_preview", "unmapped_source_rows_preview", "shared_gene_ids", "unmapped_genes", "qpcr")}
        if isinstance(value, list):
            limit = 12 if path.endswith("criterion_results") else 2
            return [bounded(item, f"{path}/{index}") for index, item in enumerate(value[:limit])]
        return value
    result["data"] = bounded(result["data"])
    result.pop("input_read_set", None)
    result["original_read_set_recorded"] = True
    result["context_representation"] = "bounded summary of immutable artifact; full original is retrievable by artifact_id"
    return result


def retrieve(ledger, run: dict, task: dict, arguments: dict) -> dict:
    if set(arguments) - {"artifact_id", "pointer", "offset", "limit"}:
        raise LedgerError("Unapproved retrieval arguments", 403)
    artifact_id = arguments.get("artifact_id")
    manifest = {artifact["artifact_id"]: artifact for artifact in available_artifacts(ledger, run, task)}
    if artifact_id not in manifest:
        raise LedgerError("Artifact is outside the task's same-run ancestor manifest", 403)
    artifact = manifest[artifact_id]
    pointer = arguments.get("pointer", "")
    if not isinstance(pointer, str) or (pointer and not pointer.startswith("/")):
        raise LedgerError("Retrieval pointer must be a JSON pointer", 422)
    value = artifact["data"]
    try:
        for part in pointer.split("/")[1:]:
            part = part.replace("~1", "/").replace("~0", "~")
            value = value[int(part)] if isinstance(value, list) else value[part]
    except (KeyError, IndexError, ValueError, TypeError):
        return {"artifact_id": artifact_id, "content_hash": artifact["content_hash"], "pointer": pointer, "status": "missing_subtree", "input_read_set": [{"key": f"artifact:{artifact_id}", "version": artifact["content_hash"], "kind": "artifact"}]}
    offset, limit = arguments.get("offset", 0), arguments.get("limit", 20)
    if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 20:
        raise LedgerError("Retrieval offset/limit outside bounds", 422)
    total = len(value) if isinstance(value, list) else None
    value = value[offset:offset + limit] if isinstance(value, list) else value
    if len(json.dumps(value, ensure_ascii=False).encode()) > 24000:
        return {"artifact_id": artifact_id, "content_hash": artifact["content_hash"], "pointer": pointer, "status": "narrower_pointer_required", "available_keys": list(value) if isinstance(value, dict) else [], "total_items": total}
    return {"artifact_id": artifact_id, "content_hash": artifact["content_hash"], "revision": artifact["revision"], "pointer": pointer, "offset": offset, "total_items": total, "data": value, "input_read_set": [{"key": f"artifact:{artifact_id}", "version": artifact["content_hash"], "kind": "artifact"}]}

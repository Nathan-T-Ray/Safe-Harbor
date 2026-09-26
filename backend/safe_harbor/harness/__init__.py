"""Frozen baseline and authoritative saved harness registry."""
from __future__ import annotations

from copy import deepcopy
import json
from contextlib import contextmanager

from safe_harbor.mongo import database_name, make_client
from safe_harbor.runtime.ledger import LedgerError
from .specification import POLICIES, apply_patch, baseline_harness, canonical_hash, validate_harness


@contextmanager
def _database(database=None):
    if database is not None:
        yield database
        return
    client = make_client()
    try:
        yield client[database_name()]
    finally:
        client.close()


def get_harness(harness_hash: str | None = None, *, database=None) -> dict:
    baseline = baseline_harness()
    if harness_hash is None or harness_hash == baseline["harness_hash"]:
        return baseline
    if not isinstance(harness_hash, str) or len(harness_hash) != 64 or any(character not in "0123456789abcdef" for character in harness_hash):
        raise LedgerError("Harness hash must identify a saved immutable specification", 422)
    with _database(database) as db:
        record = db.harness_versions.find_one({"harness_hash": harness_hash}, {"_id": 0})
    if record is None:
        raise LedgerError("Unknown saved harness version", 404)
    return validate_harness(record)


def list_harnesses(*, database=None) -> list[dict]:
    baseline = baseline_harness()
    records = {baseline["harness_hash"]: baseline}
    with _database(database) as db:
        for record in db.harness_versions.find({"mode": {"$ne": "mock"}, "proposal_mode": {"$ne": "mock"}}, {"_id": 0}):
            validated = validate_harness(record)
            records[validated["harness_hash"]] = validated
    return [deepcopy(records[key]) for key in sorted(records)]


def save_harness(record: dict, *, database=None) -> dict:
    """Explicit immutable save; does not select, promote, or migrate a running run."""
    record = validate_harness(record)
    with _database(database) as db:
        db.harness_versions.create_index("harness_hash", unique=True)
        if record["parent_hash"]:
            get_harness(record["parent_hash"], database=db)
        db.harness_versions.update_one({"harness_hash": record["harness_hash"]}, {"$setOnInsert": record}, upsert=True)
        accepted = db.harness_versions.find_one({"harness_hash": record["harness_hash"]}, {"_id": 0})
    if accepted != record:
        raise LedgerError("Saved harness hash has conflicting content", 409)
    return deepcopy(record)


def select_context_artifacts(artifacts: list[dict], policy: str, max_characters: int = 28000) -> dict:
    """Select actual upstream records without changing mandatory outer metadata.

    Policy affects ordering and hence bounded inclusion; omitted exact IDs remain
    retrievable. The selection trace records every included and omitted record.
    """
    if policy not in POLICIES or type(max_characters) is not int or not 1000 <= max_characters <= 28000:
        raise LedgerError("Unknown context policy or unapproved context bound", 422)
    eligible = [artifact for artifact in artifacts if artifact.get("kind") != "worker_trace"]
    def priority(artifact):
        data = artifact.get("data", {})
        tool = data.get("tool_name", "")
        if policy == "numerical_first":
            return (0 if tool in {"expression_comparison", "control_overlap", "gene_proximity", "screen_candidate"} else 1, artifact["artifact_id"])
        if policy == "contradictions_first":
            calculation = data.get("calculation", {})
            flagged = bool(data.get("contradictions")) or data.get("evidence_status") == "conflicting" or isinstance(calculation, dict) and (bool(calculation.get("contradictions")) or calculation.get("status") in {"unavailable", "incomplete", "conflicting"})
            return (0 if flagged else 1, artifact["artifact_id"])
        return (0, artifact["artifact_id"])
    # Relevant policy preserves dependency order. Specialized policies reorder
    # deterministically, with artifact IDs as explicit stable tie breakers.
    ordered = eligible if policy == "relevant_evidence" else sorted(eligible, key=priority)
    evidence, omitted, selected_chars = [], [], 0
    for artifact in ordered:
        size = len(json.dumps(artifact, ensure_ascii=False, sort_keys=True))
        if selected_chars + size <= max_characters:
            evidence.append(deepcopy(artifact))
            selected_chars += size
        else:
            omitted.append(artifact["artifact_id"])
    return {"evidence": evidence, "omitted_artifact_ids": omitted, "selection_trace": {"policy": policy, "max_characters": max_characters, "selected_characters": selected_chars, "available_count": len(eligible), "included_artifact_ids": [artifact["artifact_id"] for artifact in evidence], "omitted_artifact_ids": omitted}}


__all__ = ["get_harness", "list_harnesses", "save_harness", "apply_patch", "validate_harness", "canonical_hash", "select_context_artifacts"]

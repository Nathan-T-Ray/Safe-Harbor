"""Transactional application ledger. No scientific or model calls occur here."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from pymongo import ASCENDING, MongoClient
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern
from shared.contracts import Artifact, Assessment


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def identifier(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


class LedgerError(Exception):
    def __init__(self, message: str, code: int = 409):
        super().__init__(message)
        self.code = code


class Ledger:
    def __init__(self, uri: str | None = None, database: str | None = None):
        self.uri = uri or os.getenv("MONGODB_URI") or "mongodb://127.0.0.1:27021/?replicaSet=safe-harbor-dev"
        self.client = MongoClient(self.uri, serverSelectionTimeoutMS=5000, tz_aware=True)
        self.db = self.client[database or os.getenv("MONGODB_DATABASE", "safe_harbor")]

    def initialize(self):
        hello = self.client.admin.command("hello")
        if not hello.get("setName") and hello.get("msg") != "isdbgrid":
            raise RuntimeError("Safe Harbor requires MongoDB transaction support (replica set or Atlas).")
        definitions = {
            "runs": [("run_id",)], "tasks": [("task_id",), ("run_id", "canonical_question_key")],
            "artifacts": [("artifact_id",)], "assessments": [("assessment_id",)],
            "harness_versions": [("harness_hash",)], "evaluations": [("evaluation_id",)],
            "operations": [("operation_id",)], "events": [("event_id",), ("run_id", "sequence")],
        }
        for collection, indexes in definitions.items():
            for keys in indexes:
                self.db[collection].create_index([(key, ASCENDING) for key in keys], unique=True)
        self.db.tasks.create_index([("run_id", ASCENDING), ("status", ASCENDING)])

    def _transaction(self, callback: Callable):
        with self.client.start_session() as session:
            return session.with_transaction(callback, read_concern=ReadConcern("snapshot"), write_concern=WriteConcern("majority"))

    def get_run(self, run_id: str, session=None) -> dict:
        run = self.db.runs.find_one({"run_id": run_id}, {"_id": 0}, session=session)
        if not run:
            raise LedgerError("Run not found", 404)
        return run

    def _write_event(self, session, run: dict, operation_id: str, cause: str, upserts: dict) -> dict:
        for artifact in upserts.get("artifacts", []):
            run["evidence_versions"][f"artifact:{artifact['artifact_id']}"] = artifact["content_hash"]
        run["run_revision"] += 1
        run["through_sequence"] += 1
        upserts = copy.deepcopy(upserts)
        upserts["runs"] = [copy.deepcopy(run)]
        event = {
            "schema_version": 1, "run_id": run["run_id"], "sequence": run["through_sequence"],
            "event_id": f"{run['run_id']}:{run['through_sequence']}", "operation_id": operation_id,
            "occurred_at": now(), "type": "state.committed", "cause": cause,
            "run_revision": run["run_revision"], "upserts": upserts,
        }
        self.db.runs.replace_one({"run_id": run["run_id"]}, copy.deepcopy(run), upsert=True, session=session)
        for name, records in upserts.items():
            if name in ("runs", "candidates"):
                continue
            key = {"tasks": "task_id", "artifacts": "artifact_id", "assessments": "assessment_id", "harness_versions": "harness_hash", "evaluations": "evaluation_id"}[name]
            for record in records:
                if name in ("artifacts", "assessments"):
                    # Original revisions are immutable; stale presentation state is carried by events.
                    existing = self.db[name].find_one({key: record[key]}, {"_id": 0}, session=session)
                    if not existing:
                        self.db[name].insert_one(copy.deepcopy(record), session=session)
                    elif name == "artifacts" and existing != record:
                        raise LedgerError("Immutable artifact identity reused with different content")
                    elif name == "assessments":
                        comparison = {field: value for field, value in record.items() if field not in ("freshness", "stale_reason")}
                        original = {field: value for field, value in existing.items() if field not in ("freshness", "stale_reason")}
                        if comparison != original:
                            raise LedgerError("Immutable assessment revision reused with different content")
                elif name == "harness_versions":
                    existing = self.db[name].find_one({key: record[key]}, {"_id": 0}, session=session)
                    if existing and existing != record:
                        raise LedgerError("Frozen harness identity reused with different content")
                    if not existing:
                        self.db[name].insert_one(copy.deepcopy(record), session=session)
                else:
                    self.db[name].replace_one({key: record[key]}, copy.deepcopy(record), upsert=True, session=session)
        self.db.events.insert_one(copy.deepcopy(event), session=session)
        return event

    def transact(self, operation_id: str, payload: dict, callback: Callable) -> dict:
        """All callbacks may repeat; they perform only database operations."""
        payload_hash = digest(payload)

        def work(session):
            previous = self.db.operations.find_one({"operation_id": operation_id}, {"_id": 0}, session=session)
            if previous:
                if previous["payload_hash"] != payload_hash:
                    raise LedgerError("Operation ID was already used with different content")
                return previous["accepted_result"]
            result = callback(session)
            self.db.operations.insert_one({
                "operation_id": operation_id, "run_id": payload.get("run_id"), "payload_hash": payload_hash,
                "status": "accepted", "accepted_at": now(), "accepted_result": copy.deepcopy(result),
            }, session=session)
            return result

        return self._transaction(work)

    def create(self, run: dict, candidates: list, tasks: list, harness: dict, artifacts: list | None = None) -> dict:
        artifacts = artifacts or []
        payload = {"run_id": run["run_id"], "run": run, "candidates": candidates, "tasks": tasks, "harness": harness, "artifacts": artifacts}

        def work(session):
            current = copy.deepcopy(run)
            event = self._write_event(session, current, f"create:{run['run_id']}", "run.created", {"candidates": candidates, "tasks": tasks, "harness_versions": [harness], "artifacts": artifacts})
            return {"run_id": run["run_id"], "sequence": event["sequence"]}

        return self.transact(f"create:{run['run_id']}", payload, work)

    def check_epoch(self, run: dict, epoch: int):
        if run["coordinator_epoch"] != epoch:
            raise LedgerError("Obsolete coordinator epoch")

    def check_read_set(self, run: dict, reads: list[dict]):
        for read in reads:
            if run["evidence_versions"].get(read["key"]) != read["version"]:
                raise LedgerError(f"Consumed evidence changed: {read['key']}")

    def claim(self, run_id: str, owner: str) -> int:
        operation_id = identifier("claim")

        def work(session):
            run = self.get_run(run_id, session)
            for artifact in self.db.artifacts.find({"run_id": run_id}, {"artifact_id": 1, "content_hash": 1}, session=session):
                run["evidence_versions"][f"artifact:{artifact['artifact_id']}"] = artifact["content_hash"]
            if run.get("coordinator_owner") != owner and run.get("lease_expires_at", 0) > time.time():
                raise LedgerError("Another coordinator holds an unexpired lease")
            # A fresh process takes an epoch; old processes are fenced at every commit.
            run["coordinator_epoch"] += 1
            run["coordinator_owner"] = owner
            run["status"] = "running"
            run["lease_updated_at"] = now()
            run["lease_expires_at"] = time.time() + 12
            changed = []
            for task in self.db.tasks.find({"run_id": run_id, "status": "running"}, {"_id": 0}, session=session):
                reservation = task.get("reservation", {})
                reserved = reservation.get("tokens", 0)
                run["budget"]["reserved_tokens"] = max(0, run["budget"]["reserved_tokens"] - reserved)
                run["budget"]["uncertain_tokens"] += reserved
                run["budget"]["reserved_tools"] = max(0, run["budget"].get("reserved_tools", 0) - reservation.get("tools", 0))
                run["budget"]["uncertain_tool_calls"] = run["budget"].get("uncertain_tool_calls", 0) + reservation.get("tools", 0)
                if run["mode"] == "real_model":
                    run["budget"]["uncertain_model_calls"] = run["budget"].get("uncertain_model_calls", 0) + task["budget"]["max_model_calls"]
                run["budget"]["reserved_cost_usd"] = max(0, run["budget"].get("reserved_cost_usd", 0) - reservation.get("cost_usd", 0))
                run["budget"]["uncertain_cost_usd"] = run["budget"].get("uncertain_cost_usd", 0) + reservation.get("cost_usd", 0)
                task["status"] = "queued" if task["attempt"] < 2 else "failed"
                task["recovery_reason"] = "Previous process ended with uncommitted work; reserved model expenditure remains uncertain."
                task["reservation"] = {}
                changed.append(task)
            self._write_event(session, run, operation_id, "coordinator.recovered", {"tasks": changed})
            return {"epoch": run["coordinator_epoch"]}

        return self.transact(operation_id, {"run_id": run_id, "owner": owner}, work)["epoch"]

    def heartbeat(self, run_id: str, epoch: int, owner: str) -> bool:
        # Lease liveness is coordination metadata, not scientific application state.
        result = self.db.runs.update_one({"run_id": run_id, "coordinator_epoch": epoch, "coordinator_owner": owner}, {"$set": {"lease_expires_at": time.time() + 12, "lease_updated_at": now()}})
        return result.matched_count == 1

    def reserve(self, run_id: str, task_id: str, epoch: int, reads: list, tokens: int, tools: int, cost: float) -> dict:
        operation_id = f"reserve:{task_id}:{epoch}:{identifier('attempt')}"
        payload = dict(run_id=run_id, task_id=task_id, epoch=epoch, reads=reads, tokens=tokens, tools=tools, cost=cost)

        def work(session):
            run = self.get_run(run_id, session)
            self.check_epoch(run, epoch)
            if run.get("budget_breach"):
                raise LedgerError("A recorded budget breach prevents further dispatch", 429)
            self.check_read_set(run, reads)
            task = self.db.tasks.find_one({"run_id": run_id, "task_id": task_id}, {"_id": 0}, session=session)
            if not task or task["status"] not in ("queued", "reopened"):
                raise LedgerError("Task is not ready for reservation")
            for dependency in task["depends_on"]:
                if not self.db.tasks.find_one({"run_id": run_id, "task_id": dependency, "status": "complete"}, session=session):
                    raise LedgerError("Dependency is incomplete")
            if self.db.tasks.count_documents({"run_id": run_id, "status": "running"}, session=session) >= 2:
                raise LedgerError("Two-worker concurrency cap reached")
            budget = run["budget"]
            if budget["tokens_used"] + budget["reserved_tokens"] + budget["uncertain_tokens"] + tokens > budget["token_limit"]:
                raise LedgerError("Token budget exhausted", 429)
            if budget["tool_calls"] + budget.get("reserved_tools", 0) + budget.get("uncertain_tool_calls", 0) + tools > budget["tool_limit"]:
                raise LedgerError("Tool budget exhausted", 429)
            if (budget.get("cost_usd") or 0) + budget.get("reserved_cost_usd", 0) + budget.get("uncertain_cost_usd", 0) + cost > budget["cost_limit_usd"]:
                raise LedgerError("Cost budget exhausted", 429)
            task.update(status="running", attempt=task["attempt"] + 1, input_read_set=reads, started_at=now(), coordinator_epoch=epoch)
            task["reservation"] = {"tokens": tokens, "tools": tools, "cost_usd": cost, "operation_id": operation_id}
            budget["reserved_tokens"] += tokens
            budget["reserved_tools"] = budget.get("reserved_tools", 0) + tools
            budget["reserved_cost_usd"] = budget.get("reserved_cost_usd", 0) + cost
            self._write_event(session, run, operation_id, "task.started", {"tasks": [task]})
            return task

        return self.transact(operation_id, payload, work)

    def accept(self, operation_id: str, payload: dict) -> dict:
        """Atomic identity, epoch, evidence-version, output, budget, task and event acceptance."""
        # Reject malformed outputs before entering a retriable database callback.
        for record in payload.get("artifacts", []):
            Artifact.model_validate(record)
            if record["content_hash"] != digest(record["data"]):
                raise LedgerError("Artifact content hash does not match its data", 422)
            if record["input_read_set"] != payload["input_read_set"]:
                raise LedgerError("Artifact input dependencies differ from the accepted attempt", 422)
        for record in payload.get("assessments", []):
            Assessment.model_validate(record)
            if record["input_read_set"] != payload["input_read_set"]:
                raise LedgerError("Assessment input dependencies differ from the accepted attempt", 422)
            if any(criterion.get("status") not in ("pass", "fail", "incomplete") for criterion in record["criterion_results"]):
                raise LedgerError("Invalid criterion status", 422)
            if any(endpoint.get("evidence_status") not in ("supported_for_endpoint", "conflicting", "unknown") for endpoint in record["experimental_endpoint_results"]):
                raise LedgerError("Invalid endpoint evidence status", 422)
        usage = payload.get("usage", {})
        if any(usage.get(field, 0) < 0 for field in ("tokens", "tool_calls", "model_calls")) or (usage.get("cost_usd") is not None and usage["cost_usd"] < 0):
            raise LedgerError("Negative resource usage rejected", 422)

        def work(session):
            run = self.get_run(payload["run_id"], session)
            self.check_epoch(run, payload["epoch"])
            self.check_read_set(run, payload["input_read_set"])
            task = self.db.tasks.find_one({"task_id": payload["task_id"], "run_id": run["run_id"]}, {"_id": 0}, session=session)
            if not task or task["status"] != "running" or task["attempt"] != payload["attempt"]:
                raise LedgerError("Attempt is no longer active")
            reservation = task.get("reservation", {})
            usage = payload.get("usage", {})
            budget = run["budget"]
            budget["reserved_tokens"] -= reservation.get("tokens", 0)
            budget["reserved_tools"] = max(0, budget.get("reserved_tools", 0) - reservation.get("tools", 0))
            budget["reserved_cost_usd"] = max(0, budget.get("reserved_cost_usd", 0) - reservation.get("cost_usd", 0))
            budget["tokens_used"] += usage.get("tokens", 0)
            if usage.get("tokens_uncertain"):
                budget["uncertain_tokens"] += max(0, reservation.get("tokens", 0) - usage.get("tokens", 0))
                budget["usage_uncertain"] = True
            budget["tool_calls"] += usage.get("tool_calls", 0)
            budget["model_calls"] += usage.get("model_calls", 0)
            if usage.get("cost_usd") is not None:
                budget["cost_usd"] = (budget.get("cost_usd") or 0) + usage["cost_usd"]
            elif usage.get("model_calls", 0):
                budget["usage_uncertain"] = True
                budget["uncertain_cost_usd"] = budget.get("uncertain_cost_usd", 0) + reservation.get("cost_usd", 0)
            artifacts = payload.get("artifacts", [])
            assessments = payload.get("assessments", [])
            for record in artifacts + assessments:
                if record["run_id"] != run["run_id"]:
                    raise LedgerError("Cross-run output rejected")
            for assessment in assessments:
                if assessment["candidate_id"] != task["candidate_id"]:
                    raise LedgerError("Cross-candidate assessment rejected")
            if budget["tokens_used"] + budget["uncertain_tokens"] > budget["token_limit"] or budget["tool_calls"] > budget["tool_limit"] or (budget.get("cost_usd") or 0) + budget.get("uncertain_cost_usd", 0) > budget["cost_limit_usd"]:
                run["budget_breach"] = "Provider-reported usage exceeded its reservation; further dispatch is forbidden."
            task.update(status="complete", completed_at=now(), result_artifact_ids=[a["artifact_id"] for a in artifacts], reservation={})
            event = self._write_event(session, run, operation_id, "task.completed", {"tasks": [task], "artifacts": artifacts, "assessments": assessments})
            return {"run_id": run["run_id"], "task_id": task["task_id"], "sequence": event["sequence"], "artifact_ids": task["result_artifact_ids"]}

        try:
            return self.transact(operation_id, payload, work)
        except LedgerError as exc:
            # A rejected transaction changes no scientific state. Keep an inspectable audit record.
            rejection_id = f"rejected:{operation_id}:{digest(payload)}"
            self.db.operations.update_one({"operation_id": rejection_id}, {"$setOnInsert": {
                "operation_id": rejection_id, "original_operation_id": operation_id, "run_id": payload["run_id"],
                "payload_hash": digest(payload), "status": "rejected", "reason": str(exc), "occurred_at": now(),
            }}, upsert=True)
            raise

    def extend_reservation(self, run_id: str, task_id: str, epoch: int, total_tokens: int, total_cost_usd: float | None = None) -> dict:
        """Reserve a conservative next-request bound before contacting a model provider."""
        operation_id = identifier("extend-reservation")

        def work(session):
            run = self.get_run(run_id, session)
            self.check_epoch(run, epoch)
            task = self.db.tasks.find_one({"run_id": run_id, "task_id": task_id, "status": "running"}, {"_id": 0}, session=session)
            if not task:
                raise LedgerError("Task is no longer active")
            self.check_read_set(run, task["input_read_set"])
            reservation = task["reservation"]
            delta = max(0, total_tokens - reservation["tokens"])
            cost_delta = max(0.0, (total_cost_usd or 0.0) - reservation.get("cost_usd", 0))
            budget = run["budget"]
            if budget["tokens_used"] + budget["uncertain_tokens"] + budget["reserved_tokens"] + delta > budget["token_limit"]:
                raise LedgerError("Next model request exceeds the remaining token budget", 429)
            if (budget.get("cost_usd") or 0) + budget.get("uncertain_cost_usd", 0) + budget.get("reserved_cost_usd", 0) + cost_delta > budget["cost_limit_usd"]:
                raise LedgerError("Next model request exceeds the remaining verified monetary budget", 429)
            if delta or cost_delta:
                reservation["tokens"] += delta
                reservation["cost_usd"] = reservation.get("cost_usd", 0) + cost_delta
                budget["reserved_tokens"] += delta
                budget["reserved_cost_usd"] = budget.get("reserved_cost_usd", 0) + cost_delta
                self._write_event(session, run, operation_id, "task.reservation_extended", {"tasks": [task]})
            return copy.deepcopy(reservation)

        return self.transact(operation_id, {"run_id": run_id, "task_id": task_id, "epoch": epoch, "total_tokens": total_tokens, "total_cost_usd": total_cost_usd}, work)

    def task_failed(self, run_id: str, task_id: str, epoch: int, error: str, transient: bool = False):
        operation_id = identifier("failure")

        def work(session):
            run = self.get_run(run_id, session)
            self.check_epoch(run, epoch)
            task = self.db.tasks.find_one({"task_id": task_id, "status": "running"}, {"_id": 0}, session=session)
            if not task:
                return {"status": "no_longer_active"}
            reservation = task.pop("reservation", {})
            budget = run["budget"]
            budget["reserved_tokens"] = max(0, budget["reserved_tokens"] - reservation.get("tokens", 0))
            budget["uncertain_tokens"] += reservation.get("tokens", 0)
            budget["reserved_tools"] = max(0, budget.get("reserved_tools", 0) - reservation.get("tools", 0))
            budget["uncertain_tool_calls"] = budget.get("uncertain_tool_calls", 0) + reservation.get("tools", 0)
            if run["mode"] == "real_model":
                budget["uncertain_model_calls"] = budget.get("uncertain_model_calls", 0) + task["budget"]["max_model_calls"]
            budget["reserved_cost_usd"] = max(0, budget.get("reserved_cost_usd", 0) - reservation.get("cost_usd", 0))
            budget["uncertain_cost_usd"] = budget.get("uncertain_cost_usd", 0) + reservation.get("cost_usd", 0)
            task.update(status="queued" if transient and task["attempt"] < 2 else "failed", error=error, failed_at=now())
            event = self._write_event(session, run, operation_id, "task.failed", {"tasks": [task]})
            return {"sequence": event["sequence"]}

        return self.transact(operation_id, {"run_id": run_id, "task_id": task_id, "epoch": epoch, "error": error}, work)

    def finish(self, run_id: str, epoch: int, status: str, reason: str):
        operation_id = identifier("finish")

        def work(session):
            run = self.get_run(run_id, session)
            self.check_epoch(run, epoch)
            run.update(status=status, stop_reason=reason, completed_at=now())
            run["lease_expires_at"] = 0
            event = self._write_event(session, run, operation_id, "run.stopped", {})
            return {"sequence": event["sequence"], "status": status}

        return self.transact(operation_id, {"run_id": run_id, "epoch": epoch, "status": status, "reason": reason}, work)

    def events(self, run_id: str, after: int = 0, limit: int = 200) -> dict:
        def read(session):
            run = self.get_run(run_id, session)
            events = list(self.db.events.find({"run_id": run_id, "sequence": {"$gt": after, "$lte": run["through_sequence"]}}, {"_id": 0}, session=session).sort("sequence", 1).limit(limit))
            return {"events": events, "through_sequence": run["through_sequence"], "has_more": bool(events and events[-1]["sequence"] < run["through_sequence"])}
        return self._transaction(read)

    def snapshot(self, run_id: str, through: int | None = None) -> dict:
        def read(session):
            current = self.get_run(run_id, session)
            watermark = current["through_sequence"] if through is None else min(through, current["through_sequence"])
            maps = {name: {} for name in ("runs", "candidates", "tasks", "artifacts", "assessments", "harness_versions", "evaluations")}
            for event in self.db.events.find({"run_id": run_id, "sequence": {"$lte": watermark}}, {"_id": 0}, session=session).sort("sequence", 1):
                for name, records in event["upserts"].items():
                    key = {"runs": "run_id", "candidates": "candidate_id", "tasks": "task_id", "artifacts": "artifact_id", "assessments": "assessment_id", "harness_versions": "harness_hash", "evaluations": "evaluation_id"}[name]
                    for record in records:
                        maps[name][record[key]] = record
            return {"schema_version": 1, "run_id": run_id, "through_sequence": watermark, "run": maps.pop("runs").get(run_id), **{key: list(values.values()) for key, values in maps.items()}}
        return self._transaction(read)

    def export(self, run_id: str) -> dict:
        snapshot = self.snapshot(run_id)
        watermark = snapshot["through_sequence"]
        events = list(self.db.events.find({"run_id": run_id, "sequence": {"$lte": watermark}}, {"_id": 0}).sort("sequence", 1))
        cutoff = events[-1]["occurred_at"] if events else snapshot["run"]["created_at"]
        operation_ids = [event["operation_id"] for event in events]
        operations = list(self.db.operations.find({"run_id": run_id, "$or": [{"operation_id": {"$in": operation_ids}}, {"accepted_at": {"$lte": cutoff}}, {"occurred_at": {"$lte": cutoff}}]}, {"_id": 0}))
        assessment_ids = [assessment["assessment_id"] for assessment in snapshot["assessments"]]
        return {"schema_version": 1, "exported_at": now(), "through_sequence": watermark, "mode": snapshot["run"]["mode"], "authoritative_store": "MongoDB application ledger", "snapshot": snapshot, "events": events, "operations": operations, "immutable_assessment_revisions": list(self.db.assessments.find({"run_id": run_id, "assessment_id": {"$in": assessment_ids}}, {"_id": 0})), "source_manifests": [artifact for artifact in snapshot["artifacts"] if artifact["kind"] == "source_manifest"], "reference_assets": [artifact for artifact in snapshot["artifacts"] if artifact["kind"] == "reference_assets"], "limitations": ["Runtime checkpoints are separate from application acceptance transactions.", "Genome base counts are not model token counts.", "Original experimental workbooks remain external immutable artifacts identified by their recorded URLs and byte hashes."]}

"""Prepared evidence-availability revisions with selective, versioned invalidation."""
from __future__ import annotations

import copy

from safe_harbor.runtime.compiler import MAX_REPLANS, MAX_TASKS, validate_plan
from safe_harbor.runtime.ledger import LedgerError, digest, identifier, now
from safe_harbor.runtime.worker import TOOL_SCOPES


def apply_revision(ledger, run_id: str, fixture_id: str) -> dict:
    if fixture_id not in ("withhold-control-evidence", "restore-control-evidence"):
        raise LedgerError("Unknown prepared fixture", 422)
    operation_id = identifier("evidence-revision")
    available = fixture_id == "restore-control-evidence"

    def work(session):
        run = ledger.get_run(run_id, session)
        candidate_id = run["candidate_ids"][0]
        current_availability = run["evidence_availability"][candidate_id]["control_evidence"]
        if current_availability == available:
            return {"run_id": run_id, "status": "unchanged", "through_sequence": run["through_sequence"]}
        if run["replan_rounds"] >= MAX_REPLANS:
            raise LedgerError("Three-replan limit reached", 429)
        all_tasks = list(ledger.db.tasks.find({"run_id": run_id}, {"_id": 0}, session=session))
        current_tasks = [task for task in all_tasks if task["status"] != "superseded"]
        scope = f"scope:{candidate_id}:expression"
        affected = {
            task["task_id"] for task in current_tasks
            if any(read["key"] == scope for read in task["input_read_set"])
            or (task.get("candidate_id") == candidate_id and any("expression" in TOOL_SCOPES.get(tool, ()) for tool in task["allowed_tools"]))
        }
        changed = True
        while changed:
            before = len(affected)
            affected.update(task["task_id"] for task in current_tasks if set(task["depends_on"]) & affected)
            changed = len(affected) != before
        if len(all_tasks) + len(affected) > MAX_TASKS:
            raise LedgerError("Evidence revision would exceed the 24-node episode limit", 429)
        run["replan_rounds"] += 1
        round_id = run["replan_rounds"]
        run["evidence_versions"][scope] += 1
        run["evidence_availability"][candidate_id]["control_evidence"] = available
        run["status"] = "revising"
        replacements = {task_id: f"{task_id}:revision{round_id}" for task_id in affected}
        upserts = []
        successors = []
        reason = f"Prepared {fixture_id}: {scope} changed to version {run['evidence_versions'][scope]}. No source measurement was altered."
        for task in current_tasks:
            if task["task_id"] not in affected:
                continue
            successor = copy.deepcopy(task)
            successor.update(
                task_id=replacements[task["task_id"]], canonical_question_key=f"{task['canonical_question_key']}:revision{round_id}",
                depends_on=[replacements.get(parent, parent) for parent in task["depends_on"]],
                input_read_set=[], status="reopened", attempt=0, plan_revision=round_id,
                reopen_reason=reason, supersedes_task_id=task["task_id"], result_artifact_ids=[], reservation={},
            )
            for key in ("started_at", "completed_at", "failed_at", "error", "coordinator_epoch"):
                successor.pop(key, None)
            reservation = task.get("reservation", {})
            if task["status"] == "running":
                budget = run["budget"]
                budget["reserved_tokens"] = max(0, budget["reserved_tokens"] - reservation.get("tokens", 0))
                budget["uncertain_tokens"] += reservation.get("tokens", 0)
                budget["reserved_tools"] = max(0, budget.get("reserved_tools", 0) - reservation.get("tools", 0))
                budget["uncertain_tool_calls"] = budget.get("uncertain_tool_calls", 0) + reservation.get("tools", 0)
                if run["mode"] == "real_model":
                    budget["uncertain_model_calls"] = budget.get("uncertain_model_calls", 0) + task["budget"]["max_model_calls"]
                budget["reserved_cost_usd"] = max(0, budget.get("reserved_cost_usd", 0) - reservation.get("cost_usd", 0))
                budget["uncertain_cost_usd"] = budget.get("uncertain_cost_usd", 0) + reservation.get("cost_usd", 0)
            task.update(status="superseded", superseded_by=successor["task_id"], reopen_reason=reason, reservation={})
            upserts.extend([task, successor])
            successors.append(successor)
        # Validate the complete resulting DAG, including dependencies on unaffected original tasks.
        final_tasks = [next((new for new in upserts if new["task_id"] == old["task_id"]), old) for old in all_tasks] + successors
        validate_plan(final_tasks)
        stale = []
        for assessment in ledger.db.assessments.find({"run_id": run_id, "candidate_id": candidate_id}, {"_id": 0}, session=session):
            if any(read["key"] == scope for read in assessment["input_read_set"]):
                assessment.update(freshness="stale", stale_reason=reason)
                stale.append(assessment)
        data = {"fixture_id": fixture_id, "candidate_id": candidate_id, "operational_revision": True, "biological_measurement_changed": False, "control_evidence_available": available, "query_scope": scope, "scope_version": run["evidence_versions"][scope], "affected_task_ids": sorted(affected), "unaffected_task_ids": sorted(task["task_id"] for task in current_tasks if task["task_id"] not in affected), "reason": reason}
        artifact = {"artifact_id": identifier("evidence-availability"), "run_id": run_id, "kind": "evidence_revision", "revision": round_id, "content_hash": digest(data), "data": data, "evidence_ids": [], "input_read_set": [{"key": scope, "version": run["evidence_versions"][scope], "kind": "query_scope"}], "provenance": {"mode": run["mode"], "fixture_id": fixture_id, "note": "Prepared operational availability update; original source artifacts remain immutable."}, "created_at": now()}
        event = ledger._write_event(session, run, operation_id, "evidence.revised", {"tasks": upserts, "assessments": stale, "artifacts": [artifact]})
        return {"run_id": run_id, "sequence": event["sequence"], "fixture_id": fixture_id, "affected_task_ids": sorted(affected), "successor_task_ids": sorted(replacements.values()), "unchanged_task_ids": data["unaffected_task_ids"]}

    return ledger.transact(operation_id, {"run_id": run_id, "fixture_id": fixture_id}, work)

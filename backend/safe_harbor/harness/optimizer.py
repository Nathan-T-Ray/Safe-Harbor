"""One bounded, real OpenRouter structural proposal from development traces.

No provider call happens inside a MongoDB transaction. A durable reservation is
created first; interrupted expenditure remains uncertain and is never retried as
free. This module never supplies a developer-authored winning candidate.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
import time
from typing import Any

from openai import OpenAI
from safe_harbor.harness import apply_patch, get_harness, save_harness
from safe_harbor.runtime.ledger import LedgerError, digest, now
from safe_harbor.runtime.pricing import request_cost_bound

MAX_DEVELOPMENT_CONTEXT_CHARACTERS = 28000
MAX_OPTIMIZER_RESERVED_TOKENS = 30000
SYSTEM_INSTRUCTIONS = """You propose one bounded executable change to the Safe Harbor investigation harness from DEVELOPMENT traces only.
Keep scientific criteria, reference answers, input data, model identity/settings, assigned total run budget, evaluation rules, and outer tool permissions unchanged. Do not invent measured benefits. A validation process will accept or reject your proposal independently.
Return exactly one JSON object with keys rationale (a concise string) and patch. The patch has exactly one key operations containing 1–4 supported operations. Include at least one insert_reviewer or split_role so executed topology genuinely changes; do not merely rename roles. You may additionally reassign approved tools or change context selection. Retain every original task kind and the complete approved tool set. There can be at most eight roles, four tools per role, four tool calls and two model calls per role. New review/assessment work must remain upstream of reporting.
Operation schemas:
insert_reviewer: {op:'insert_reviewer',after_role_id:string,role:{role_id:string,kind:'review_candidate',question:string,allowed_tools:string[],context_policy?:string,instructions?:string,decision_target?:string,completion_condition?:string}}
split_role: {op:'split_role',role_id:string,roles:[newRole,newRole]}. The first inherits original dependencies, second follows first; both require new IDs and together retain the original tools. A newRole has the same fields as above, but kind can be any approved task kind.
change_context: {op:'change_context',role_id:string,context_policy:'relevant_evidence'|'numerical_first'|'contradictions_first'}
reassign_tools: {op:'reassign_tools',from_role_id:string,to_role_id:string,tools:string[]}
Do not put depends_on, limits, model settings, scientific thresholds, criteria, reference answers, or evaluation rules in a patch. State why the observed development traces motivate the change, and what validation could disprove. A rejected proposal is an acceptable outcome. Never claim this proposal establishes biological safety or causal attribution.
"""


def _public_development_packet(ledger, results: list[dict]) -> tuple[list[dict], list[dict], list[str]]:
    if not results or any(result.get("split") != "development" for result in results):
        raise LedgerError("Optimizer input must consist exclusively of assigned development results", 422)
    from safe_harbor.evaluation.cases import load_cases
    assigned_development = {case["case_id"] for case in load_cases("development")}
    if any(result.get("case_id") not in assigned_development for result in results):
        raise LedgerError("Optimizer cannot read validation or final case traces", 403)
    packet, reads, omitted = [], [], []
    characters = 0
    for result in sorted(results, key=lambda item: (str(item.get("case_id")), str(item.get("arm")))):
        run_id = result.get("run_id")
        item = {key: deepcopy(result.get(key)) for key in ("case_id", "split", "arm", "run_id", "harness_hash", "status", "usage")}
        # Evaluator-only answers and detailed rubrics are intentionally omitted.
        score = result.get("score") or {}
        item["score_summary"] = {key: score.get(key) for key in ("required_correct", "required_total", "required_decisions_correct", "required_decisions_total", "unsupported_count", "coverage", "completed", "support_ok")}
        item["tasks"] = []
        if run_id:
            run = ledger.db.runs.find_one({"run_id": run_id}, {"_id": 0})
            if not run or run.get("mode") != "real_model":
                raise LedgerError("A real optimizer proposal requires real-model development runs", 422)
            if run.get("experiment_id") != result.get("experiment_id") or run.get("comparison_manifest_hash") != result.get("comparison_manifest_hash") or run.get("case_context", {}).get("case_id") != result.get("case_id") or run.get("evaluation_arm") != result.get("arm"):
                raise LedgerError("Development traces do not match the actual frozen run binding", 403)
            tasks = list(ledger.db.tasks.find({"run_id": run_id}, {"_id": 0}).sort("task_id", 1))
            for task in tasks:
                summary = {key: task.get(key) for key in ("task_id", "role_id", "kind", "question", "depends_on", "allowed_tools", "context_policy", "status", "attempt")}
                summary["worker_observations"] = []
                for artifact_id in task.get("result_artifact_ids", []):
                    artifact = ledger.db.artifacts.find_one({"artifact_id": artifact_id, "run_id": run_id}, {"_id": 0})
                    if not artifact:
                        continue
                    reads.append({"key": artifact_id, "version": artifact["content_hash"], "kind": "artifact"})
                    if artifact.get("kind") == "worker_trace":
                        data = artifact["data"]
                        observation = {"artifact_id": artifact_id, "proposal": data.get("proposal"), "usage": data.get("usage"), "context_characters": data.get("context_characters"), "context_selection_trace": data.get("context_packet", {}).get("context_selection_trace"), "tool_names": [call.get("tool_name") for call in data.get("tool_calls", [])]}
                    elif artifact.get("kind") == "scientific_tool_result":
                        data = artifact["data"]
                        observation = {"artifact_id": artifact_id, "tool_name": data.get("tool_name"), "calculation": data.get("calculation"), "limitations": data.get("limitations"), "evidence_ids": artifact.get("evidence_ids", [])}
                    else:
                        continue
                    serialized = json.dumps(observation, ensure_ascii=False)
                    if characters + len(serialized) <= MAX_DEVELOPMENT_CONTEXT_CHARACTERS:
                        summary["worker_observations"].append(observation)
                        characters += len(serialized)
                    else:
                        omitted.append(artifact_id)
                item["tasks"].append(summary)
        packet.append(item)
    return packet, reads, omitted


def _usage(response, elapsed: float, reserved_tokens: int, reserved_cost: float) -> dict:
    raw = response.usage.model_dump() if response.usage is not None else {}
    tokens = raw.get("total_tokens")
    cost = raw.get("cost")
    complete = isinstance(tokens, (int, float)) and isinstance(cost, (int, float))
    return {"tokens": int(tokens) if isinstance(tokens, (int, float)) else None, "tool_calls": 0, "model_calls": 1, "cost_usd": float(cost) if isinstance(cost, (int, float)) else None, "duration_seconds": round(elapsed, 6), "usage_complete": complete, "reserved_tokens": reserved_tokens, "uncertain_tokens": 0 if tokens is not None else reserved_tokens, "uncertain_cost_usd": 0.0 if cost is not None else reserved_cost, "reserved_cost_usd": reserved_cost, "provider_usage": raw, "budget_breach": bool(tokens is not None and tokens > reserved_tokens)}


def propose_harness(ledger, experiment_id: str, parent_hash: str, development_results: list[dict], model_snapshot: dict, budget: dict) -> dict:
    """Return candidate_ready, blocked, rejected_invalid_proposal, or failed.

    Idempotent per experiment. A repeated call never starts a second provider
    request; a prior interrupted reservation returns an uncertain failure.
    """
    evaluation_id = f"optimizer:{experiment_id}"
    existing = ledger.db.evaluations.find_one({"evaluation_id": evaluation_id}, {"_id": 0})
    if existing:
        if existing.get("parent_hash") != parent_hash or existing.get("model_snapshot") != model_snapshot or existing.get("optimizer_budget") != budget or existing.get("development_results_hash") != digest(development_results):
            raise LedgerError("Optimizer operation identity was reused with different frozen inputs", 409)
        if existing.get("status") == "reserved" and existing.get("reservation_deadline", 0) > time.time():
            return {**existing, "status": "in_progress", "reason": "The single reserved optimizer attempt is still within its provider deadline; no duplicate call is dispatched."}
        if existing.get("status") == "reserved":
            return {**existing, "status": "failed", "error": "An earlier optimizer call may have been interrupted; reserved expenditure remains uncertain. No automatic retry.", "usage": {"tokens": None, "tool_calls": 0, "model_calls": None, "cost_usd": None, "duration_seconds": None, "usage_complete": False, "uncertain_tokens": existing.get("reserved_tokens", 0), "uncertain_cost_usd": existing.get("reserved_cost_usd", 0)}}
        return existing
    parent = get_harness(parent_hash, database=ledger.db)
    experiment = ledger.db.evaluations.find_one({"evaluation_id": experiment_id}, {"_id": 0})
    manifest = (experiment or {}).get("comparison_manifest", {})
    assigned_run_budget = manifest.get("budget")
    if not assigned_run_budget or manifest.get("model") != model_snapshot:
        raise LedgerError("Optimizer must use the frozen experiment model and assigned run budget", 422)
    source = {"evaluation_id": evaluation_id, "experiment_id": experiment_id, "type": "optimizer_attempt", "mode": "real_model", "parent_hash": parent_hash, "model_snapshot": deepcopy(model_snapshot), "assigned_run_budget": deepcopy(assigned_run_budget), "optimizer_budget": deepcopy(budget), "development_results_hash": digest(development_results), "created_at": now()}
    provider = model_snapshot.get("provider")
    model_id = model_snapshot.get("model_id")
    reserved_tokens = min(MAX_OPTIMIZER_RESERVED_TOKENS, int(budget.get("token_limit", 0)))
    if not os.getenv("OPENROUTER_API_KEY") or not model_id or provider != "openrouter" or reserved_tokens < 1000:
        blocked = {**source, "status": "blocked", "reason": "A configured OpenRouter key, frozen model identity, and nonzero bounded optimizer allowance are required.", "usage": {"tokens": 0, "tool_calls": 0, "model_calls": 0, "cost_usd": 0.0, "duration_seconds": 0.0, "usage_complete": True}, "candidate_hash": None}
        ledger.db.evaluations.update_one({"evaluation_id": evaluation_id}, {"$setOnInsert": blocked}, upsert=True)
        return ledger.db.evaluations.find_one({"evaluation_id": evaluation_id}, {"_id": 0})
    packet, read_set, omitted = _public_development_packet(ledger, development_results)
    development_experiments = {result.get("experiment_id") for result in development_results}
    if development_experiments != {experiment_id} or any(result.get("comparison_manifest_hash") != experiment.get("comparison_manifest_hash") for result in development_results):
        raise LedgerError("Optimizer development results must belong to this experiment", 422)
    user_packet = {"parent_harness": parent, "development_results": packet, "omitted_trace_artifact_ids": omitted, "fixed_model_snapshot": model_snapshot, "same_assigned_budget_for_every_arm": assigned_run_budget, "proposal_limit": 1}
    pricing = model_snapshot.get("model_pricing")
    output_cap = int(model_snapshot.get("max_output_tokens", 1800))
    def blocked_preflight(reason, bounds=None):
        blocked = {**source, "status": "blocked", "reason": reason, "candidate_hash": None, "preflight": bounds or {}, "usage": {"tokens": 0, "tool_calls": 0, "model_calls": 0, "cost_usd": 0.0, "duration_seconds": 0.0, "usage_complete": True}}
        ledger.db.evaluations.update_one({"evaluation_id": evaluation_id}, {"$setOnInsert": blocked}, upsert=True)
        return ledger.db.evaluations.find_one({"evaluation_id": evaluation_id}, {"_id": 0})
    if not pricing or pricing.get("model_id") != model_id or not pricing.get("provider_routing"):
        return blocked_preflight("Frozen model endpoint pricing/routing is required before an optimizer inference charge.")
    # Bound the ENTIRE serialized model input, including repeated role metadata,
    # protocol allowance, and output. UTF-8 bytes are a conservative text-token
    # upper bound, shared with the worker's preflight accounting.
    while True:
        messages = [{"role": "system", "content": SYSTEM_INSTRUCTIONS}, {"role": "user", "content": json.dumps(user_packet, ensure_ascii=False)}]
        request_record = {"model": model_id, "temperature": model_snapshot.get("temperature", 0), "max_tokens": output_cap, "response_format": {"type": "json_object"}, "messages": messages, "extra_body": {"provider": pricing["provider_routing"], "plugins": []}}
        input_bytes = len(json.dumps(request_record, ensure_ascii=False).encode("utf-8"))
        # Match the worker's framing allowance so the optimizer cannot obtain a
        # looser monetary/token boundary than the arms it proposes to change.
        input_bound = input_bytes + 4096 + 256 * len(messages)
        total_bound = input_bound + output_cap
        if total_bound <= reserved_tokens and input_bytes <= int(model_snapshot.get("context_limit_bytes", 60000)):
            break
        removed = False
        for case in reversed(packet):
            for task in reversed(case["tasks"]):
                if task["worker_observations"]:
                    observation = task["worker_observations"].pop()
                    artifact_id = observation["artifact_id"]
                    if artifact_id not in omitted:
                        omitted.append(artifact_id)
                    removed = True
                    break
            if removed:
                break
        if not removed:
            return blocked_preflight("Mandatory optimizer metadata exceeds the frozen token/context bound; no inference request was sent.", {"input_utf8_bytes": input_bytes, "input_bound": input_bound, "output_cap": output_cap, "assigned_token_limit": budget.get("token_limit")})
    cost_bound = request_cost_bound(pricing, input_bound, output_cap)
    preflight = {"input_utf8_bytes": input_bytes, "input_bound": input_bound, "output_cap": output_cap, "reserved_tokens": total_bound, "reserved_cost_usd": cost_bound, "pricing_hash": pricing["pricing_hash"], "provider_routing": pricing["provider_routing"], "omitted_trace_artifact_ids": omitted}
    if cost_bound > float(budget.get("cost_limit_usd", 0)):
        return blocked_preflight("Conservative optimizer request cost exceeds its frozen monetary budget; no inference request was sent.", preflight)
    reserved_tokens = total_bound
    request_hash = digest(request_record)
    reserved = {**source, "status": "reserved", "request_hash": request_hash, "reserved_tokens": reserved_tokens, "reserved_cost_usd": cost_bound, "preflight": preflight, "reservation_deadline": time.time() + 120, "input_read_set": read_set, "started_at": now(), "usage": {"tokens": None, "tool_calls": 0, "model_calls": None, "cost_usd": None, "duration_seconds": None, "usage_complete": False, "uncertain_tokens": reserved_tokens, "uncertain_cost_usd": cost_bound}}
    # One unique insert is the actual single-call gate, including concurrent callers.
    try:
        ledger.db.evaluations.insert_one(deepcopy(reserved))
    except Exception as exc:
        from pymongo.errors import DuplicateKeyError
        if isinstance(exc, DuplicateKeyError):
            return ledger.db.evaluations.find_one({"evaluation_id": evaluation_id}, {"_id": 0})
        raise
    artifact_id = f"{experiment_id}:optimizer-response"
    started = time.monotonic()
    try:
        client = OpenAI(api_key=os.environ["OPENROUTER_API_KEY"], base_url="https://openrouter.ai/api/v1", max_retries=0, timeout=90)
        response = client.chat.completions.create(**request_record)
        usage = _usage(response, time.monotonic() - started, reserved_tokens, cost_bound)
        usage["cost_budget_breach"] = bool(usage["cost_usd"] is not None and (usage["cost_usd"] > cost_bound or usage["cost_usd"] > budget.get("cost_limit_usd", 0)))
        raw_content = response.choices[0].message.content or ""
        raw = {"request": request_record, "response": response.model_dump(mode="json"), "raw_content": raw_content, "usage": usage, "development_case_ids": [item["case_id"] for item in packet], "omitted_trace_artifact_ids": omitted}
        artifact = {"artifact_id": artifact_id, "run_id": f"experiment:{experiment_id}", "kind": "harness_optimizer_response", "revision": 1, "content_hash": digest(raw), "data": raw, "evidence_ids": [read["key"] for read in read_set], "input_read_set": read_set, "provenance": {"mode": "real_model", "provider": provider, "model_id": model_id, "experiment_id": experiment_id, "parent_hash": parent_hash, "request_hash": request_hash, "source_split": "development"}, "created_at": now()}
        # Record the exact response even when parsing or compilation rejects it.
        ledger.db.artifacts.update_one({"artifact_id": artifact_id}, {"$setOnInsert": artifact}, upsert=True)
        try:
            if usage.get("budget_breach") or usage.get("cost_budget_breach"):
                raise LedgerError("Provider-reported optimizer usage exceeded its frozen reservation; proposal cannot advance", 429)
            parsed = json.loads(raw_content)
            if not isinstance(parsed, dict) or set(parsed) != {"rationale", "patch"} or not isinstance(parsed["rationale"], str) or not 1 <= len(parsed["rationale"]) <= 5000:
                raise LedgerError("Optimizer response must have a bounded rationale and exact patch", 422)
            if not any(operation.get("op") in {"split_role", "insert_reviewer"} for operation in parsed["patch"].get("operations", [])):
                raise LedgerError("Proposal must change executed task topology", 422)
            candidate = apply_patch(parent, parsed["patch"], proposal_mode="real_model", proposal_metadata={"model_id": model_id, "provider": provider, "response_artifact_id": artifact_id, "experiment_id": experiment_id, "request_hash": request_hash, "rationale": parsed["rationale"], "development_case_ids": [item["case_id"] for item in packet]})
            save_harness(candidate, database=ledger.db)
            result = {**reserved, "status": "candidate_ready", "candidate_hash": candidate["harness_hash"], "proposal_artifact_id": artifact_id, "rationale": parsed["rationale"], "patch": parsed["patch"], "usage": usage, "finished_at": now()}
        except (ValueError, TypeError, AttributeError, KeyError, LedgerError) as exc:
            result = {**reserved, "status": "rejected_invalid_proposal", "candidate_hash": None, "proposal_artifact_id": artifact_id, "error": str(exc), "usage": usage, "finished_at": now()}
    except Exception as exc:
        result = {**reserved, "status": "failed", "candidate_hash": None, "error": f"{exc.__class__.__name__}: {str(exc)[:600]}", "usage": {"tokens": None, "tool_calls": 0, "model_calls": None, "cost_usd": None, "duration_seconds": round(time.monotonic() - started, 6), "usage_complete": False, "uncertain_tokens": reserved_tokens, "uncertain_cost_usd": cost_bound}, "finished_at": now()}
    ledger.db.evaluations.replace_one({"evaluation_id": evaluation_id}, result)
    return deepcopy(result)

"""Scoped scientific tools and honest deterministic/OpenRouter execution adapters."""
from __future__ import annotations

import importlib
import json
import os
import time
from typing import Any

from openai import OpenAI

from safe_harbor.runtime.compiler import APPROVED_TOOLS
from safe_harbor.runtime.ledger import LedgerError, digest, identifier, now

TOOL_SCOPES = {
    "inspect_candidate": ("catalog", "annotation", "sequence"), "list_evidence": ("expression", "catalog", "annotation", "sequence"), "table_slice": ("expression",),
    "expression_comparison": ("expression",), "control_overlap": ("expression",),
    "gene_proximity": ("annotation", "expression"), "screen_candidate": ("annotation",), "reference_sequence": ("sequence",),
}


def science():
    return importlib.import_module("safe_harbor.science")


def read_set_for(ledger, run: dict, task: dict) -> list[dict]:
    """Record query availability even when the corresponding query returns no rows."""
    keys = {"criteria:v1", "source:data_version"}
    for tool in task["allowed_tools"]:
        keys.update(f"scope:{task['candidate_id']}:{scope}" for scope in TOOL_SCOPES[tool])
    for dependency in task["depends_on"]:
        parent = ledger.db.tasks.find_one({"run_id": run["run_id"], "task_id": dependency}, {"_id": 0})
        if parent:
            keys.update(read["key"] for read in parent["input_read_set"])
    return [{"key": key, "version": run["evidence_versions"][key], "kind": "criteria" if key == "criteria:v1" else "query_scope" if key.startswith("scope:") else "artifact"} for key in sorted(keys)]


def build_context_packet(ledger, run: dict, task: dict) -> dict:
    """Bounded integration packet; R10 can extend retrieval without changing tool access."""
    source = science().get_catalog()
    candidate = next(candidate for candidate in source["candidates"] if candidate["candidate_id"] == task["candidate_id"])
    available = []
    for dependency in task["depends_on"]:
        parent = ledger.db.tasks.find_one({"task_id": dependency}, {"_id": 0})
        for artifact_id in (parent or {}).get("result_artifact_ids", []):
            artifact = ledger.db.artifacts.find_one({"run_id": run["run_id"], "artifact_id": artifact_id}, {"_id": 0})
            if artifact and artifact["kind"] != "worker_trace":
                available.append(artifact)
    try:
        select = importlib.import_module("safe_harbor.harness").select_context_artifacts
    except (ModuleNotFoundError, AttributeError):
        evidence, omitted, size = [], [], 0
        for artifact in available:
            length = len(json.dumps(artifact))
            if size + length <= 28000:
                evidence.append(artifact)
                size += length
            else:
                omitted.append(artifact["artifact_id"])
        selection_trace = {"policy": "integration_fallback_dependency_order", "characters": size}
    else:
        selection = select(available, task.get("context_policy", "relevant_evidence"), max_characters=28000)
        evidence, omitted = selection["evidence"], selection["omitted_artifact_ids"]
        selection_trace = selection.get("selection_trace", {})
    return {
        "objective": run["objective"], "question": task["question"], "candidate": candidate,
        "assembly": run["assembly"], "cell_context": run["cell_context"], "data_version": run["data_version"],
        "criteria": source.get("criteria", {}), "input_read_set": task["input_read_set"],
        "evidence": evidence, "omitted_artifact_ids": omitted, "allowed_tools": task["allowed_tools"],
        "context_policy": task.get("context_policy"), "harness_hash": run["harness_hash"],
        "context_selection_trace": selection_trace,
        "remaining_budget": run["budget"], "evidence_availability": run["evidence_availability"][task["candidate_id"]],
        "limitations": ["Only the publication-derived shortlist is investigated.", "GRCh38 is a reference assembly, not a newly sequenced H1 genome.", "Control overlap and proximity cannot establish biological safety or causality."],
    }


def execute_tool(task: dict, run: dict, name: str, arguments: dict | None = None) -> dict:
    if name not in APPROVED_TOOLS or name not in task["allowed_tools"]:
        raise LedgerError(f"Tool {name} is not allowed for role {task['role_id']}", 403)
    arguments = arguments or {}
    if not isinstance(arguments, dict):
        raise LedgerError("Tool arguments must be an object", 422)
    if set(arguments) & {"url", "path", "file", "artifact_id", "candidate_id", "run_id"}:
        raise LedgerError("Tools accept scoped arguments, not arbitrary resources", 403)
    arguments = dict(arguments)
    if name in ("control_overlap", "table_slice", "list_evidence", "expression_comparison"):
        arguments["controls_available"] = run["evidence_availability"][task["candidate_id"]]["control_evidence"]
        if arguments.get("cell_context", "H1") != "H1":
            raise LedgerError("This investigation is scoped to H1; H9 evidence requires a separately labeled context", 403)
        arguments["cell_context"] = "H1"
    if name == "control_overlap" and not run["evidence_availability"][task["candidate_id"]]["control_evidence"]:
        return {
            "tool_name": name, "candidate_id": task["candidate_id"], "assembly": "GRCh38",
            "cell_context": run["cell_context"], "data_version": run["data_version"], "evidence_ids": [],
            "calculation": {"status": "unavailable", "reason": "Original control evidence is unavailable under this prepared operational evidence revision."},
            "limitations": ["Absence is an evidence-availability condition, not a negative biological result."],
            "input_read_set": task["input_read_set"], "source_hashes": {},
        }
    result = science().run_tool(name, task["candidate_id"], arguments)
    for read in result.get("input_read_set", []):
        if read["key"] not in run["evidence_versions"]:
            raise LedgerError("Scientific tool returned an unregistered evidence dependency", 422)
        read["version"] = run["evidence_versions"][read["key"]]
    return result


def _artifact(run: dict, task: dict, kind: str, data: dict, evidence_ids: list[str] | None = None) -> dict:
    return {
        "artifact_id": identifier("artifact"), "run_id": run["run_id"], "kind": kind,
        "revision": task.get("plan_revision", 0) + 1, "content_hash": digest(data), "data": data,
        "evidence_ids": evidence_ids or [], "input_read_set": task["input_read_set"],
        "provenance": {"mode": run["mode"], "task_id": task["task_id"], "role_id": task["role_id"], "harness_hash": run["harness_hash"], "adapter": "deterministic_operational" if run["mode"] == "deterministic" else "openrouter", "model_id": run.get("model_id")},
        "created_at": now(),
    }


def proposal_to_assessment(ledger, run: dict, task: dict, proposal: dict, results: list[dict]) -> dict:
    """Conservative initial proposal boundary. Numerical screen facts remain authoritative."""
    criteria = science().get_catalog().get("criteria", {}).get("criteria", [])
    screen = next((result.get("calculation", {}) for result in results if result.get("tool_name") == "screen_candidate"), {})
    facts_fn = getattr(science(), "assessment_facts", None)
    facts = facts_fn(task["candidate_id"]) if facts_fn else {}
    criterion_results = facts.get("criterion_results", screen.get("criterion_results", []))
    if not criterion_results:
        criterion_results = [{"criterion_id": criterion["criterion_id"], "status": "incomplete", "reason": "Required result has not been attached to this assessment.", "evidence_ids": []} for criterion in criteria]
    statuses = {item["status"] for item in criterion_results}
    screen_status = "incomplete" if "incomplete" in statuses or not statuses else "fail" if "fail" in statuses else "pass"
    evidence_ids = sorted({evidence_id for result in results for evidence_id in result.get("evidence_ids", [])})
    context = build_context_packet(ledger, run, task)
    evidence_ids += [item["artifact_id"] for item in context["evidence"]]
    previous = list(ledger.db.assessments.find({"run_id": run["run_id"], "candidate_id": task["candidate_id"]}, {"assessment_revision": 1}))
    revision = max((item["assessment_revision"] for item in previous), default=0) + 1
    conclusion = proposal.get("conclusion") or "This operational run preserves the expression concern as unresolved; it does not supply a model interpretation."
    return {
        "assessment_id": f"{run['run_id']}:{task['candidate_id']}:assessment:{revision}", "run_id": run["run_id"],
        "candidate_id": task["candidate_id"], "assembly": "GRCh38", "cell_context": run["cell_context"],
        "screen_status": screen_status, "evidence_status": "unknown", "criterion_results": criterion_results,
        "experimental_endpoint_results": [{"endpoint": "expression perturbation concern", "assay": "RNA-seq comparisons", "cell_context": run["cell_context"], "evidence_status": "unknown", "reason": conclusion, "evidence_ids": evidence_ids}],
        "evidence_ids": evidence_ids, "unresolved_questions": proposal.get("unresolved_questions", [run["objective"], "Overall suitability remains uncertain; required cancer-gene and regulatory evidence is unavailable."]),
        "limitations": context["limitations"] + proposal.get("limitations", []) + ["Computational status applies only to the named criteria; no global safety label is assigned."],
        "assessment_revision": revision, "freshness": "current", "conclusion": conclusion,
        "input_read_set": task["input_read_set"], "proposal": proposal,
    }


def execute_worker(ledger, run: dict, task: dict) -> dict:
    started = time.monotonic()
    packet = build_context_packet(ledger, run, task)
    results, calls, messages, proposal = [], [], [], {}
    usage = {"tokens": 0, "tool_calls": 0, "model_calls": 0, "cost_usd": 0.0 if run["mode"] == "deterministic" else None}
    request_bounds = []
    if run["mode"] == "deterministic":
        for name in task["allowed_tools"][:task["budget"]["max_tool_calls"]]:
            result = execute_tool(task, run, name)
            results.append(result)
            calls.append({"tool_name": name, "arguments": {}, "result": result})
        proposal = {"conclusion": "Deterministic operational execution completed the assigned calculations. The expression-exclusion question remains unresolved pending a real model interpretation.", "mode": "deterministic"}
    else:
        client = OpenAI(api_key=os.environ["OPENROUTER_API_KEY"], base_url="https://openrouter.ai/api/v1", max_retries=0, timeout=90)
        system = (
            "You investigate publication-derived GRCh38 candidate regions in H1 human embryonic stem cells. "
            "Answer the assigned question from numerical evidence and methods. Never invent values, criteria or source IDs. "
            "Select useful approved tools. Numerical operations must be performed by tools. Missing evidence stays incomplete/unknown. "
            "A control overlap or distance cannot establish safety or causality. No global safe label. "
            "Return a JSON object with conclusion, unresolved_questions, limitations, evidence_ids and numerical_findings. "
            "Do not quote the paper's interpretive conclusion. " + task.get("instructions", "")
        )
        messages = [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(packet, ensure_ascii=False)}]
        tools = science().tool_definitions(task["allowed_tools"])
        costs = []
        for call_index in range(task["budget"]["max_model_calls"]):
            remaining_tools = task["budget"]["max_tool_calls"] - len(calls)
            may_use_tools = bool(tools and remaining_tools > 0 and call_index < task["budget"]["max_model_calls"] - 1)
            output_cap = 1800
            # UTF-8 bytes conservatively bound common tokenizer input units; explicit framing
            # allowance covers provider chat/tool envelopes. Repeated context is counted anew.
            serialized_input = json.dumps({"messages": messages, "tools": tools if may_use_tools else []}, ensure_ascii=False).encode("utf-8")
            input_bound = len(serialized_input) + 4096 + 256 * len(messages)
            total_bound = usage["tokens"] + input_bound + output_cap
            reservation = ledger.extend_reservation(run["run_id"], task["task_id"], task["coordinator_epoch"], total_bound)
            task["reservation"] = reservation
            request_bounds.append({"call_index": call_index, "input_utf8_bytes": len(serialized_input), "input_bound": input_bound, "output_cap": output_cap, "cumulative_reserved_tokens": reservation["tokens"]})
            response = client.chat.completions.create(
                model=run["model_id"], messages=messages,
                max_tokens=output_cap,
                temperature=0, **({"tools": tools, "tool_choice": "auto", "parallel_tool_calls": False} if may_use_tools else {"response_format": {"type": "json_object"}}),
            )
            usage["model_calls"] += 1
            if response.usage:
                usage["tokens"] += response.usage.total_tokens
                raw_usage = response.usage.model_dump()
                costs.append(raw_usage.get("cost"))
            else:
                costs.append(None)
                usage["tokens_uncertain"] = True
            message = response.choices[0].message
            messages.append(message.model_dump(exclude_none=True))
            if message.tool_calls:
                if not may_use_tools or len(message.tool_calls) > remaining_tools:
                    raise LedgerError("Model exceeded bounded tool allowance", 403)
                for call in message.tool_calls:
                    arguments = json.loads(call.function.arguments or "{}")
                    result = execute_tool(task, run, call.function.name, arguments)
                    results.append(result)
                    calls.append({"tool_name": call.function.name, "arguments": arguments, "result": result, "model_call_id": call.id})
                    tool_content = json.dumps(result, ensure_ascii=False)
                    if len(tool_content.encode("utf-8")) > 24000:
                        tool_content = json.dumps({"tool_name": call.function.name, "candidate_id": task["candidate_id"], "content_hash": digest(result), "evidence_ids": result.get("evidence_ids", []), "calculation": result.get("calculation", {}), "limitations": result.get("limitations", []) + ["Detailed rows omitted from active context; the full tool output is retained in the immutable run artifact."]}, ensure_ascii=False)
                        if len(tool_content.encode("utf-8")) > 24000:
                            tool_content = json.dumps({"tool_name": call.function.name, "content_hash": digest(result), "status": "output_requires_smaller_scoped_query", "evidence_ids": result.get("evidence_ids", []), "limitations": ["Tool output exceeded the active-context bound; no partial numeric conclusion should be inferred."]})
                    messages.append({"role": "tool", "tool_call_id": call.id, "content": tool_content})
                continue
            raw = message.content or "{}"
            try:
                proposal = json.loads(raw.removeprefix("```json").removesuffix("```").strip())
            except json.JSONDecodeError:
                proposal = {"conclusion": raw, "limitations": ["Model response did not match the requested JSON format; no typed endpoint claim accepted."]}
            break
        if costs and all(cost is not None for cost in costs):
            usage["cost_usd"] = sum(float(cost) for cost in costs)
    usage["tool_calls"] = len(calls)
    usage["duration_seconds"] = round(time.monotonic() - started, 4)
    artifacts = [_artifact(run, task, "scientific_tool_result", result, result.get("evidence_ids", [])) for result in results]
    artifacts.append(_artifact(run, task, "worker_trace", {"mode": run["mode"], "role_id": task["role_id"], "context_packet": packet, "tool_calls": calls, "messages": messages, "proposal": proposal, "usage": usage, "request_token_bounds": request_bounds, "context_characters": len(json.dumps(packet))}))
    assessments = []
    if task["kind"] in ("assess_candidate", "review_candidate"):
        assessments.append(proposal_to_assessment(ledger, run, task, proposal, results))
    if task["kind"] == "publish_shortlist":
        artifacts.append(_artifact(run, task, "versioned_dossier", {"candidate_id": task["candidate_id"], "proposal": proposal, "upstream_task_ids": task["depends_on"], "limitations": packet["limitations"]}))
    return {"run_id": run["run_id"], "task_id": task["task_id"], "epoch": task["coordinator_epoch"], "attempt": task["attempt"], "input_read_set": task["input_read_set"], "artifacts": artifacts, "assessments": assessments, "usage": usage}

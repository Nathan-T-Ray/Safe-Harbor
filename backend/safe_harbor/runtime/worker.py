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
from safe_harbor.runtime.context import available_artifacts, compact_artifact, retrieve, RETRIEVAL_DEFINITION, RUNTIME_TOOLS
from safe_harbor.runtime.assessments import METRICS, OUTPUT_CONTRACT, metric_values, validate_proposal
from safe_harbor.runtime.pricing import request_cost_bound

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
    keys.add(f"scope:{task['candidate_id']}:catalog")
    keys.update(f"artifact:{artifact['artifact_id']}" for artifact in available_artifacts(ledger, run, task))
    for tool in task["allowed_tools"]:
        keys.update(f"scope:{task['candidate_id']}:{scope}" for scope in TOOL_SCOPES[tool])
    for dependency in task["depends_on"]:
        parent = ledger.db.tasks.find_one({"run_id": run["run_id"], "task_id": dependency}, {"_id": 0})
        if parent:
            keys.update(read["key"] for read in parent["input_read_set"])
    versions = ledger.get_run(run["run_id"])["evidence_versions"]
    return [{"key": key, "version": versions[key], "kind": "criteria" if key == "criteria:v1" else "query_scope" if key.startswith("scope:") else "artifact"} for key in sorted(keys)]


def build_context_packet(ledger, run: dict, task: dict) -> dict:
    """Bounded integration packet; R10 can extend retrieval without changing tool access."""
    source = science().get_catalog()
    if source["data_version"] != run["data_version"]:
        raise LedgerError("Frozen source version is unavailable in this process; start a new run for the newly ingested dataset", 409)
    candidate = next(candidate for candidate in source["candidates"] if candidate["candidate_id"] == task["candidate_id"])
    originals = available_artifacts(ledger, run, task)
    available = [compact_artifact(artifact) for artifact in originals if artifact["kind"] not in ("reference_assets", "source_manifest")]
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
    packet = {
        "objective": run["objective"], "question": task["question"], "candidate": candidate,
        "assembly": run["assembly"], "cell_context": run["cell_context"], "data_version": run["data_version"],
        "criteria": source.get("criteria", {}), "input_read_set": task["input_read_set"],
        "evidence": evidence, "omitted_artifact_ids": omitted, "allowed_tools": task["allowed_tools"],
        "runtime_tools": RUNTIME_TOOLS,
        "evidence_manifest": [{"artifact_id": artifact["artifact_id"], "kind": artifact["kind"], "content_hash": artifact["content_hash"], "revision": artifact["revision"]} for artifact in originals],
        "case_context": run.get("case_context", {}),
        "context_policy": task.get("context_policy"), "harness_hash": run["harness_hash"],
        "context_selection_trace": selection_trace,
        "remaining_budget": run["budget"], "evidence_availability": run["evidence_availability"][task["candidate_id"]],
        "task_limits": {**task["budget"], "tool_allowance_includes": "Both scientific tools and retrieve_evidence; the run-level limit is not this task's allowance."},
        "limitations": ["Only the publication-derived shortlist is investigated.", "GRCh38 is a reference assembly, not a newly sequenced H1 genome.", "Control overlap and proximity cannot establish biological safety or causality."],
    }
    while len(json.dumps(packet, ensure_ascii=False).encode()) > 60000 and packet["evidence"]:
        packet["omitted_artifact_ids"].append(packet["evidence"].pop()["artifact_id"])
    if len(json.dumps(packet, ensure_ascii=False).encode()) > 60000:
        raise LedgerError("Mandatory context metadata exceeds the 60 KB bound; no model request was made", 429)
    packet["context_limit_bytes"] = 60000
    return packet


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
    deterministic = run["mode"] == "deterministic" or (run.get("baseline_arm") == "R0" and task["kind"] != "assess_candidate")
    return {
        "artifact_id": identifier("artifact"), "run_id": run["run_id"], "kind": kind,
        "revision": task.get("plan_revision", 0) + 1, "content_hash": digest(data), "data": data,
        "evidence_ids": evidence_ids or [], "input_read_set": task["input_read_set"],
        "provenance": {"mode": run["mode"], "task_id": task["task_id"], "role_id": task["role_id"], "harness_hash": run["harness_hash"], "adapter": ("deterministic_operational" if run["mode"] == "deterministic" else "deterministic_checks_within_real_model_run") if deterministic else "openrouter", "model_id": None if deterministic else run.get("model_id")},
        "created_at": now(),
    }


def proposal_to_assessment(ledger, run: dict, task: dict, proposal: dict, results: list[dict], direct_artifacts: list[dict] | None = None) -> dict:
    """Conservative initial proposal boundary. Numerical screen facts remain authoritative."""
    criteria = science().get_catalog().get("criteria", {}).get("criteria", [])
    screen = next((result.get("calculation", {}) for result in results if result.get("tool_name") == "screen_candidate"), {})
    frontier, visited = list(task["depends_on"]), set()
    while frontier and not screen:
        parent_id = frontier.pop(0)
        if parent_id in visited:
            continue
        visited.add(parent_id)
        parent = ledger.db.tasks.find_one({"run_id": run["run_id"], "task_id": parent_id}, {"_id": 0})
        if not parent or parent["status"] != "complete":
            continue
        frontier.extend(parent["depends_on"])
        for artifact_id in parent.get("result_artifact_ids", []):
            artifact = ledger.db.artifacts.find_one({"run_id": run["run_id"], "artifact_id": artifact_id, "data.tool_name": "screen_candidate"}, {"_id": 0})
            if artifact:
                screen = artifact["data"]["calculation"]
                break
    # Reuse a previously accepted scientific computation; never make unmetered hidden tool calls.
    criterion_results = screen.get("criterion_results", [])
    if not criterion_results:
        criterion_results = [{"criterion_id": criterion["criterion_id"], "status": "incomplete", "reason": "Required result has not been attached to this assessment.", "evidence_ids": []} for criterion in criteria]
    statuses = {item["status"] for item in criterion_results}
    screen_status = "incomplete" if "incomplete" in statuses or not statuses else "fail" if "fail" in statuses else "pass"
    evidence_ids = sorted({evidence_id for result in results for evidence_id in result.get("evidence_ids", [])})
    context = build_context_packet(ledger, run, task)
    consumed = available_artifacts(ledger, run, task) + (direct_artifacts or [])
    evidence_ids += [item["artifact_id"] for item in context["evidence"]]
    previous = list(ledger.db.assessments.find({"run_id": run["run_id"], "candidate_id": task["candidate_id"]}, {"assessment_revision": 1}))
    revision = max((item["assessment_revision"] for item in previous), default=0) + 1
    validation_errors = []
    if run["mode"] == "deterministic":
        values, numerical_evidence = {key: None for key in METRICS}, {}
        for artifact in consumed:
            for key, value in metric_values(artifact.get("data", {})).items():
                if value is not None:
                    values[key] = value
                    numerical_evidence[key] = [artifact["artifact_id"]]
        validated = {"exclusion_decision": "unresolved", "numerical_findings": values, "numerical_evidence": numerical_evidence, "limitation_codes": ["deterministic_operational_no_model_interpretation"]}
    else:
        validated, validation_errors = validate_proposal(proposal, consumed, criterion_results, screen_status, run["evidence_availability"][task["candidate_id"]]["control_evidence"])
        if validation_errors:
            validated = {"exclusion_decision": "unresolved", "numerical_findings": {key: None for key in METRICS}, "numerical_evidence": {}, "limitation_codes": ["model_proposal_failed_validation"]}
    conclusion = proposal.get("conclusion") or "This operational run preserves the expression concern as unresolved; it does not supply a model interpretation."
    if validation_errors:
        conclusion = "The model proposal failed evidence or schema validation. The expression-exclusion question remains unresolved; inspect the recorded proposal and validation errors."
    accepted_questions = validated.get("unresolved_questions", [run["objective"]])
    accepted_limitations = validated.get("limitations", [])
    missing_criteria = [item["criterion_id"] for item in criterion_results if item["status"] == "incomplete"]
    if missing_criteria:
        accepted_questions = list(accepted_questions) + ["Required evidence remains unavailable for: " + ", ".join(missing_criteria)]
    evidence_ids = sorted(set(evidence_ids) | {evidence_id for item in criterion_results for evidence_id in item.get("evidence_ids", [])} | set(validated.get("evidence_ids", [])))
    return {
        "assessment_id": f"{run['run_id']}:{task['candidate_id']}:assessment:{revision}", "run_id": run["run_id"],
        "task_id": task["task_id"],
        "candidate_id": task["candidate_id"], "assembly": "GRCh38", "cell_context": run["cell_context"],
        "screen_status": screen_status, "evidence_status": "unknown", "criterion_results": criterion_results,
        "experimental_endpoint_results": [{"endpoint": "expression perturbation concern", "assay": "RNA-seq comparisons", "cell_context": run["cell_context"], "evidence_status": "unknown", "reason": conclusion, "evidence_ids": evidence_ids}],
        "evidence_ids": evidence_ids, "unresolved_questions": accepted_questions,
        "limitations": context["limitations"] + accepted_limitations + ["Computational status applies only to the named criteria; no global safety label is assigned."],
        "assessment_revision": revision, "freshness": "current", "conclusion": conclusion,
        "input_read_set": task["input_read_set"], "proposal": proposal,
        "exclusion_decision": validated["exclusion_decision"], "numerical_findings": validated["numerical_findings"],
        "numerical_evidence": validated.get("numerical_evidence", {}), "limitation_codes": validated.get("limitation_codes", []),
        "validation_errors": validation_errors, "model_proposal_accepted": run["mode"] == "real_model" and not validation_errors,
    }


def execute_worker(ledger, run: dict, task: dict) -> dict:
    state = {}
    try:
        return _execute_worker(ledger, run, task, state)
    except Exception as exc:
        # A received response remains inspectable even when its proposed action is
        # rejected. The coordinator settles this diagnostic in the failure event.
        if state:
            usage = dict(state["usage"])
            usage.update(tool_calls=len(state["calls"]), cost_usd=sum(float(cost) for cost in state.get("costs", []) if cost is not None), duration_seconds=round(time.monotonic() - state["started"], 4))
            uncertain = bool(state.get("request_in_flight") or usage.get("tokens_uncertain"))
            failure = {"usage": usage, "tokens_uncertain": uncertain, "cost_uncertain": bool(state.get("request_in_flight") or any(cost is None for cost in state.get("costs", []))), "request_in_flight": bool(state.get("request_in_flight"))}
            trace = {"mode": run["mode"], "status": "failed", "error": f"{type(exc).__name__}: {exc}", "role_id": task["role_id"], "context_packet": state["packet"], "messages": state["messages"], "tool_calls": state["calls"], "provider_responses": state.get("provider_responses", []), "request_token_bounds": state["request_bounds"], **failure}
            failure["artifact"] = _artifact(run, task, "worker_failure_trace", trace)
            exc.worker_failure = failure
        raise


def _execute_worker(ledger, run: dict, task: dict, state: dict) -> dict:
    started = time.monotonic()
    packet = build_context_packet(ledger, run, task)
    results, calls, messages, proposal = [], [], [], {}
    usage = {"tokens": 0, "tool_calls": 0, "model_calls": 0, "cost_usd": 0.0 if run["mode"] == "deterministic" else None}
    request_bounds = []
    state.update(started=started, packet=packet, results=results, calls=calls, messages=messages, usage=usage, request_bounds=request_bounds, provider_responses=[])
    deterministic_task = run["mode"] == "deterministic" or (run.get("baseline_arm") == "R0" and task["kind"] != "assess_candidate")
    if deterministic_task:
        usage["cost_usd"] = 0.0
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
            f"This task permits at most {task['budget']['max_tool_calls']} total tool calls, including retrieve_evidence, and {task['budget']['max_model_calls']} model responses. "
            "You may request several independent approved tools together within that task allowance; do not request more. "
            "A control overlap or distance cannot establish safety or causality. No global safe label. "
            "Return a JSON object with conclusion, unresolved_questions, limitations, evidence_ids and numerical_findings. "
            "Do not quote the paper's interpretive conclusion. " + task.get("instructions", "")
        )
        if task["kind"] in ("assess_candidate", "review_candidate", "publish_shortlist"):
            system += " " + OUTPUT_CONTRACT
        messages = [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(packet, ensure_ascii=False)}]
        state["messages"] = messages
        tools = science().tool_definitions(task["allowed_tools"]) + [RETRIEVAL_DEFINITION]
        costs = []
        state["costs"] = costs
        cumulative_cost_bound = 0.0
        for call_index in range(task["budget"]["max_model_calls"]):
            remaining_tools = task["budget"]["max_tool_calls"] - len(calls)
            may_use_tools = bool(tools and remaining_tools > 0 and call_index < task["budget"]["max_model_calls"] - 1)
            output_cap = run.get("model_settings", {}).get("max_output_tokens", 3000)
            # UTF-8 bytes conservatively bound common tokenizer input units; explicit framing
            # allowance covers provider chat/tool envelopes. Repeated context is counted anew.
            serialized_input = json.dumps({"messages": messages, "tools": tools if may_use_tools else []}, ensure_ascii=False).encode("utf-8")
            input_bound = len(serialized_input) + 4096 + 256 * len(messages)
            total_bound = usage["tokens"] + input_bound + output_cap
            call_cost_bound = request_cost_bound(run.get("model_pricing"), input_bound, output_cap)
            cumulative_cost_bound += call_cost_bound
            reservation = ledger.extend_reservation(run["run_id"], task["task_id"], task["coordinator_epoch"], total_bound, cumulative_cost_bound)
            task["reservation"] = reservation
            request_bounds.append({"call_index": call_index, "input_utf8_bytes": len(serialized_input), "input_bound": input_bound, "output_cap": output_cap, "cumulative_reserved_tokens": reservation["tokens"], "call_cost_bound_usd": call_cost_bound, "pricing_hash": run["model_pricing"]["pricing_hash"]})
            state["request_in_flight"] = True
            response = client.chat.completions.create(
                model=run["model_id"], messages=messages,
                max_tokens=output_cap,
                temperature=run.get("model_settings", {}).get("temperature", 0), **({"tools": tools, "tool_choice": "auto"} if may_use_tools else {"response_format": {"type": "json_object"}}),
                extra_body={"provider": run["model_pricing"]["provider_routing"], "plugins": []},
            )
            state["request_in_flight"] = False
            state["provider_responses"].append({"call_index": call_index, "response": response.model_dump(mode="json")})
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
                    result = retrieve(ledger, run, task, arguments) if call.function.name == "retrieve_evidence" else execute_tool(task, run, call.function.name, arguments)
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
    assessments = []
    if task["kind"] in ("assess_candidate", "review_candidate"):
        assessments.append(proposal_to_assessment(ledger, run, task, proposal, results, artifacts))
        artifacts.append(_artifact(run, task, "assessment_proposal", {"assessment": assessments[-1], "raw_model_proposal": proposal}, assessments[-1]["evidence_ids"]))
    if task["kind"] == "publish_shortlist":
        dossier = proposal_to_assessment(ledger, run, task, proposal, results, artifacts)
        artifacts.append(_artifact(run, task, "versioned_dossier", {"candidate_id": task["candidate_id"], "validated_summary": dossier, "raw_model_proposal": proposal, "upstream_task_ids": task["depends_on"], "limitations": packet["limitations"]}))
    artifacts.append(_artifact(run, task, "worker_trace", {"mode": run["mode"], "execution_adapter": "deterministic_operational" if deterministic_task else "openrouter", "role_id": task["role_id"], "context_packet": packet, "tool_calls": calls, "messages": messages, "provider_responses": state["provider_responses"], "proposal": proposal, "usage": usage, "request_token_bounds": request_bounds, "context_characters": len(json.dumps(packet))}))
    return {"run_id": run["run_id"], "task_id": task["task_id"], "epoch": task["coordinator_epoch"], "attempt": task["attempt"], "input_read_set": task["input_read_set"], "artifacts": artifacts, "assessments": assessments, "usage": usage}

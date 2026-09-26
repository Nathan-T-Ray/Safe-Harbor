"""Executable, immutable Safe Harbor harness records and strict structural patches.

No model proposal is authored here. The curated H0 record is a fixed baseline.
Optimizer callers must pass the exact generated patch and provenance separately.
"""
from __future__ import annotations

from copy import deepcopy
from graphlib import CycleError, TopologicalSorter
import hashlib
import json
import re
from typing import Any

from safe_harbor.runtime.compiler import APPROVED_TOOLS, TASK_KINDS, compile_harness
from safe_harbor.runtime.ledger import LedgerError

POLICIES = frozenset({"relevant_evidence", "numerical_first", "contradictions_first"})
ROLE_FIELDS = frozenset({"role_id", "kind", "question", "depends_on", "allowed_tools", "context_policy", "instructions", "decision_target", "completion_condition", "max_tool_calls", "max_model_calls"})
IMMUTABLE_CONSTRAINTS = {
    "assembly": "GRCh38", "cell_context": "H1 human embryonic stem cells",
    "scientific_criteria": "safe-harbor-criteria-v1; fixed by the source catalog",
    "reference_answers": "evaluator-only; immutable and unavailable to workers",
    "evaluation_rules": "frozen experiment manifest; optimizer cannot modify",
    "input_data": "frozen source hashes and evidence availability per case",
    "model_identity": "fixed by the comparison manifest; optimizer cannot modify",
    "total_assigned_budget": "fixed by the comparison manifest and run ledger",
    "permission_boundary": "scoped approved tools only; no arbitrary URLs, files, or evaluator data",
    "max_workers": 2, "max_tasks_per_episode": 24, "max_replanning_rounds": 3,
    "max_transient_retries": 1, "max_candidates": 3,
    "scientific_contract": "Separate named-criterion screen status, endpoint support, and freshness. Missing required evidence means incomplete. No global safety claim.",
}
SCIENTIFIC_INSTRUCTIONS = (
    "Use actual source-backed numerical results and exact evidence IDs. Preserve assembly, H1 cell context, "
    "source versions, original row provenance, and unresolved requirements. Missing evidence is not a negative "
    "biological result. Keep gene-body and transcription-start distances distinct. Reference GRCh38 is not a "
    "personalized H1 genome. GENCODE v36 is a new annotation analysis. Control overlap and proximity cannot "
    "establish safety or causality. Never assign a global safe label or invent thresholds. "
)


def canonical_hash(record: dict) -> str:
    payload = {key: value for key, value in record.items() if key != "harness_hash"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _role(role_id: str, kind: str, question: str, depends_on: list[str], tools: list[str], instructions: str) -> dict:
    return {
        "role_id": role_id, "kind": kind, "question": question,
        "depends_on": depends_on, "allowed_tools": tools,
        "context_policy": "relevant_evidence", "instructions": SCIENTIFIC_INSTRUCTIONS + instructions,
        "decision_target": "expression_exclusion_concern",
        "completion_condition": "Persist exact evidence-linked results, distinguish measured facts from interpretation, and retain unresolved questions.",
        "max_tool_calls": 4, "max_model_calls": 2,
    }


def baseline_harness() -> dict:
    roles = [
        _role("screen", "screen_regions", "Which frozen computational criteria are met, failed, or incomplete for this published interval?", [], ["inspect_candidate", "screen_candidate"],
              "Read the named criteria and their parameters. Report all required missing criteria, including unavailable cancer-gene/regulatory evidence. Never infer an overall pass from the available subset."),
        _role("inspect", "inspect_evidence", "What expression tables, methods, source rows, control comparisons, and reference evidence are available?", [], ["list_evidence", "table_slice", "reference_sequence"],
              "Identify H1 targeted-versus-control and untargeted-control contrasts, significance/selection rules, gene units, duplicate identifiers, and whether only significant results are tabulated. H9 is a different biological context."),
        _role("compare", "compute_features", "How do targeted expression changes compare with untargeted-control variation and genomic proximity?", ["inspect"], ["expression_comparison", "control_overlap", "gene_proximity"],
              "Select relevant deterministic calculations. Obtain targeted and control counts, explicit overlap numerators and denominators, duplicate/unmapped identifiers, and distances using tools. Prioritize a missing control or proximity calculation that could change the interpretation. Do not do interval arithmetic yourself."),
        _role("assess", "assess_candidate", "Do these measured expression changes justify excluding this candidate region?", ["screen", "inspect", "compare"], ["expression_comparison", "control_overlap", "gene_proximity"],
              "Synthesize the available numerical results and methods. Use tools to resolve missing consequential evidence. Explain what the expression comparison supports or questions, with exact counts and denominators. Control variation can contextualize a concern but does not establish causality or safety. Preserve uncertainty when required evidence is missing."),
        _role("review", "review_candidate", "Are the candidate assessment's numerical findings, context, and exclusions supported by the consumed evidence?", ["screen", "inspect", "compare", "assess"], ["screen_candidate", "control_overlap"],
              "Independently challenge numerical claims, denominators, control awareness, applicability to H1, and unsupported biological conclusions. Reconcile contradictions explicitly. Do not turn absent results into failures or label suitability established."),
        _role("report", "publish_shortlist", "What versioned candidate dossier accurately records the conclusion, evidence, and remaining requirements?", ["screen", "inspect", "compare", "assess", "review"], [],
              "Publish a concise inspectable synthesis scoped to the named endpoint and assay. Include evidence IDs and remaining limitations. Label publication-derived shortlist, deterministic operational versus real model mode, and provisional unknowns faithfully."),
    ]
    record = {
        "schema_version": 1, "name": "H0 · competent fixed investigation",
        "parent_hash": None, "roles": roles, "patch": None,
        "proposal_mode": "developer_authored_fixed_baseline",
        "immutable_constraints": deepcopy(IMMUTABLE_CONSTRAINTS),
        "baseline_arm": "H0", "description": "A fixed control-aware six-role workflow with the complete approved scientific tool set. No improvement claim.",
    }
    record["harness_hash"] = canonical_hash(record)
    return validate_harness(record)


def _fail(message: str) -> None:
    raise LedgerError(message, 422)


def validate_harness(record: dict) -> dict:
    record = deepcopy(record)
    required = {"harness_hash", "name", "parent_hash", "roles", "patch", "proposal_mode", "immutable_constraints"}
    if not isinstance(record, dict) or required - set(record):
        _fail("Harness record is missing required fields")
    allowed_fields = required | {"schema_version", "baseline_arm", "description", "proposal_metadata"}
    if set(record) - allowed_fields:
        _fail("Harness contains forbidden top-level settings")
    if canonical_hash(record) != record["harness_hash"]:
        _fail("Harness hash does not match its exact specification")
    if record["immutable_constraints"] != IMMUTABLE_CONSTRAINTS:
        _fail("Scientific, model, evidence, evaluation, permission, or total-budget constraints were altered")
    roles = record["roles"]
    if not isinstance(roles, list) or not 1 <= len(roles) <= 8:
        _fail("A harness must contain 1–8 roles, allowing three candidates within 24 tasks")
    ids = [role.get("role_id") for role in roles if isinstance(role, dict)]
    if len(ids) != len(roles) or not all(isinstance(role_id, str) for role_id in ids) or len(set(ids)) != len(ids):
        _fail("Role IDs must be unique")
    for role in roles:
        if set(role) - ROLE_FIELDS:
            _fail("Role contains unapproved settings")
        if not isinstance(role.get("role_id"), str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", role["role_id"]):
            _fail("Role ID must be a bounded canonical identifier")
        if role.get("kind") not in TASK_KINDS or role.get("context_policy") not in POLICIES:
            _fail("Unapproved role kind or context policy")
        for field, maximum in (("question", 800), ("instructions", 5000), ("completion_condition", 1000)):
            if not isinstance(role.get(field), str) or not 1 <= len(role[field]) <= maximum:
                _fail(f"Role {field} must be a nonempty bounded string")
        tools = role.get("allowed_tools")
        dependencies = role.get("depends_on")
        if not isinstance(tools, list) or not all(isinstance(tool, str) for tool in tools) or len(tools) > 4 or len(set(tools)) != len(tools) or set(tools) - APPROVED_TOOLS:
            _fail("Role requests unapproved or repeated tools")
        if not isinstance(dependencies, list) or not all(isinstance(dependency, str) for dependency in dependencies) or len(set(dependencies)) != len(dependencies) or set(dependencies) - set(ids):
            _fail("Role has unknown or repeated dependencies")
        if type(role.get("max_tool_calls")) is not int or not 0 <= role["max_tool_calls"] <= 4:
            _fail("Role tool-call cap must remain within 0–4")
        if type(role.get("max_model_calls")) is not int or not 1 <= role["max_model_calls"] <= 2:
            _fail("Role model-call cap must remain within 1–2")
    kinds = set(role["kind"] for role in roles)
    if record.get("baseline_arm") == "R0":
        # The all-checks baseline must not inherit unnecessary agent complexity.
        # Its implementation belongs to H04; only the compatible schema is here.
        if record["parent_hash"] is not None or record["patch"] is not None or record["proposal_mode"] != "developer_authored_fixed_baseline":
            _fail("R0 must identify an independently frozen fixed baseline")
        if "assess_candidate" not in kinds or not kinds.intersection({"screen_regions", "compute_features"}):
            _fail("R0 must execute deterministic analysis and a synthesis assessment")
    elif kinds != TASK_KINDS:
        _fail("The full screen, inspect, calculate, assess, review, and report workflow must remain present")
    if set().union(*(set(role["allowed_tools"]) for role in roles)) != APPROVED_TOOLS:
        _fail("A harness must retain the same complete approved tool set")
    try:
        list(TopologicalSorter({role["role_id"]: role["depends_on"] for role in roles}).static_order())
    except CycleError as exc:
        raise LedgerError("Harness dependencies contain a cycle", 422) from exc
    by_id = {role["role_id"]: role for role in roles}
    for report in (role for role in roles if role["kind"] == "publish_shortlist"):
        ancestors = set(report["depends_on"])
        frontier = list(ancestors)
        while frontier:
            for dependency in by_id[frontier.pop()]["depends_on"]:
                if dependency not in ancestors:
                    ancestors.add(dependency)
                    frontier.append(dependency)
        required_reviews = {role["role_id"] for role in roles if role["kind"] in {"review_candidate", "assess_candidate"}}
        if required_reviews - ancestors:
            _fail("Reporting must remain downstream of every assessment and review")
    compile_harness(record, "harness-schema-check", ["candidate-a", "candidate-b", "candidate-c"])
    return record


def _operation_fields(operation: dict, expected: set[str]) -> None:
    if not isinstance(operation, dict) or set(operation) != expected:
        _fail("Structural operation has missing or forbidden fields")


def _new_role(value: dict, *, default_dependencies: list[str]) -> dict:
    # The optimizer specifies content and approved tools, but cannot elevate execution limits.
    if not isinstance(value, dict) or set(value) - (ROLE_FIELDS - {"depends_on", "max_tool_calls", "max_model_calls"}):
        _fail("New role contains forbidden dependency, permission, or budget fields")
    required = {"role_id", "kind", "question", "allowed_tools"}
    if required - set(value) or not isinstance(value.get("role_id"), str) or not isinstance(value.get("kind"), str) or not isinstance(value.get("question"), str) or not isinstance(value.get("allowed_tools"), list) or not all(isinstance(tool, str) for tool in value["allowed_tools"]):
        _fail("A new role requires typed ID, kind, question, and approved tools")
    role = deepcopy(value)
    role.setdefault("context_policy", "relevant_evidence")
    role.setdefault("instructions", SCIENTIFIC_INSTRUCTIONS)
    role.setdefault("decision_target", "expression_exclusion_concern")
    role.setdefault("completion_condition", "Persist evidence-linked results and remaining uncertainty.")
    role.update(depends_on=default_dependencies, max_tool_calls=4, max_model_calls=2)
    return role


def apply_patch(parent: dict, patch: dict, *, proposal_mode: str = "unverified_proposal", proposal_metadata: dict | None = None) -> dict:
    """Compile an exact bounded patch; never promote or pretend it came from a model.

    Accepted shape: {"operations": [{"op": ..., ...}]}.
    insert_reviewer: after_role_id + role; split_role: role_id + roles (exactly 2);
    change_context: role_id + context_policy;
    reassign_tools: from_role_id + to_role_id + tools.
    """
    parent = validate_harness(parent)
    if not isinstance(patch, dict) or set(patch) != {"operations"} or not isinstance(patch["operations"], list) or not 1 <= len(patch["operations"]) <= 4:
        _fail("Patch must contain 1–4 approved structural operations only")
    if proposal_mode not in {"unverified_proposal", "deterministic_operational", "real_model"}:
        _fail("Proposal mode must explicitly identify provenance")
    if proposal_mode == "real_model" and not (proposal_metadata and proposal_metadata.get("model_id") and proposal_metadata.get("response_artifact_id")):
        _fail("A real-model proposal requires model identity and a recorded response artifact")
    record = deepcopy(parent)
    roles = record["roles"]
    for operation in patch["operations"]:
        by_id = {role["role_id"]: role for role in roles}
        op = operation.get("op") if isinstance(operation, dict) else None
        if op == "insert_reviewer":
            _operation_fields(operation, {"op", "after_role_id", "role"})
            after = by_id.get(operation["after_role_id"])
            if after is None:
                _fail("Reviewer insertion refers to an unknown role")
            role = _new_role(operation["role"], default_dependencies=[after["role_id"]])
            if role.get("kind") != "review_candidate" or role.get("role_id") in by_id:
                _fail("Inserted role must be a new reviewer")
            for downstream in roles:
                downstream["depends_on"] = [role["role_id"] if dependency == after["role_id"] else dependency for dependency in downstream["depends_on"]]
            roles.insert(roles.index(after) + 1, role)
        elif op == "split_role":
            _operation_fields(operation, {"op", "role_id", "roles"})
            old = by_id.get(operation["role_id"])
            if old is None or not isinstance(operation["roles"], list) or len(operation["roles"]) != 2:
                _fail("Split requires an existing role and exactly two replacement roles")
            first = _new_role(operation["roles"][0], default_dependencies=list(old["depends_on"]))
            second = _new_role(operation["roles"][1], default_dependencies=[first.get("role_id")])
            if first.get("role_id") in by_id or second.get("role_id") in by_id or first.get("role_id") == second.get("role_id"):
                _fail("Split roles require new distinct IDs")
            if set(old["allowed_tools"]) - set(first.get("allowed_tools", []) + second.get("allowed_tools", [])):
                _fail("Split roles must preserve the original role's tool capabilities")
            index = roles.index(old)
            roles[index:index + 1] = [first, second]
            for downstream in roles:
                downstream["depends_on"] = [second["role_id"] if dependency == old["role_id"] else dependency for dependency in downstream["depends_on"]]
        elif op == "change_context":
            _operation_fields(operation, {"op", "role_id", "context_policy"})
            if operation["role_id"] not in by_id or operation["context_policy"] not in POLICIES:
                _fail("Context change requests an unknown role or policy")
            by_id[operation["role_id"]]["context_policy"] = operation["context_policy"]
        elif op == "reassign_tools":
            _operation_fields(operation, {"op", "from_role_id", "to_role_id", "tools"})
            source, target = by_id.get(operation["from_role_id"]), by_id.get(operation["to_role_id"])
            moved = operation["tools"]
            if source is None or target is None or source is target or not isinstance(moved, list) or not moved or len(set(moved)) != len(moved) or set(moved) - set(source["allowed_tools"]):
                _fail("Tool reassignment must move existing approved tools between distinct roles")
            source["allowed_tools"] = [tool for tool in source["allowed_tools"] if tool not in moved]
            target["allowed_tools"] = sorted(set(target["allowed_tools"]) | set(moved))
        else:
            _fail("Unknown structural operation; criteria, data, model, budget, evaluation, and permission edits are forbidden")
    record.update(name=f"Candidate workflow from {parent['harness_hash'][:12]}", parent_hash=parent["harness_hash"], patch=deepcopy(patch), proposal_mode=proposal_mode)
    record.pop("baseline_arm", None)
    record["description"] = "Unselected candidate specification; execution and separate evaluation are required."
    if proposal_metadata is not None:
        record["proposal_metadata"] = deepcopy(proposal_metadata)
    record["harness_hash"] = canonical_hash(record)
    if roles == parent["roles"]:
        _fail("Patch does not change executable role behavior")
    return validate_harness(record)

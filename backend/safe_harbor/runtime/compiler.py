"""Compile a frozen role specification to a bounded, dependency-aware task DAG."""
from __future__ import annotations

from graphlib import CycleError, TopologicalSorter
from shared.contracts import Task
from safe_harbor.runtime.ledger import LedgerError

APPROVED_TOOLS = frozenset({"inspect_candidate", "list_evidence", "table_slice", "expression_comparison", "control_overlap", "gene_proximity", "screen_candidate", "reference_sequence"})
TASK_KINDS = frozenset({"screen_regions", "inspect_evidence", "compute_features", "assess_candidate", "review_candidate", "publish_shortlist"})
MAX_TASKS = 24
MAX_REPLANS = 3
MAX_WORKERS = 2


def validate_plan(tasks: list[dict]) -> list[str]:
    if not tasks or len(tasks) > MAX_TASKS:
        raise LedgerError("A plan must contain 1–24 tasks", 422)
    validated = [Task.model_validate(task).model_dump() for task in tasks]
    ids = {task["task_id"] for task in validated}
    if len(ids) != len(tasks):
        raise LedgerError("Duplicate task IDs", 422)
    if len({task["canonical_question_key"] for task in validated}) != len(tasks):
        raise LedgerError("Repeated canonical question", 422)
    if len({task["run_id"] for task in validated}) != 1 or len({task["harness_hash"] for task in validated}) != 1:
        raise LedgerError("A plan must use one run and one frozen harness", 422)
    graph = {}
    for task in validated:
        if task["kind"] not in TASK_KINDS:
            raise LedgerError("Unapproved task kind", 422)
        if set(task["allowed_tools"]) - APPROVED_TOOLS:
            raise LedgerError("Unapproved task tool", 422)
        if set(task["depends_on"]) - ids:
            raise LedgerError("Unknown task dependency", 422)
        if set(task.get("output_references", [])) - set(task["depends_on"]):
            raise LedgerError("Output references must identify declared dependencies", 422)
        graph[task["task_id"]] = task["depends_on"]
    try:
        return list(TopologicalSorter(graph).static_order())
    except CycleError as exc:
        raise LedgerError("Cyclic task plan", 422) from exc


def compile_harness(harness: dict, run_id: str, candidate_ids: list[str], revision: int = 0) -> list[dict]:
    """Each role becomes an executed task; dependencies are compiled, never drawn only."""
    roles = harness.get("roles", [])
    if not roles or len({role["role_id"] for role in roles}) != len(roles):
        raise LedgerError("Harness roles must be nonempty and unique", 422)
    tasks = []
    for candidate_id in candidate_ids:
        ids = {role["role_id"]: f"{run_id}:{candidate_id}:{role['role_id']}:r{revision}" for role in roles}
        for role in roles:
            if set(role.get("depends_on", [])) - set(ids):
                raise LedgerError("Unknown role dependency", 422)
            task = {
                "task_id": ids[role["role_id"]], "run_id": run_id, "candidate_id": candidate_id,
                "kind": role["kind"], "question": role["question"],
                "canonical_question_key": f"{candidate_id}:{role['role_id']}:{role['kind']}:r{revision}",
                "decision_target": role.get("decision_target", "expression_exclusion_concern"),
                "depends_on": [ids[key] for key in role.get("depends_on", [])], "input_read_set": [],
                "role_id": role["role_id"], "harness_hash": harness["harness_hash"],
                "allowed_tools": role.get("allowed_tools", []),
                "completion_condition": role.get("completion_condition", "Persist an evidence-linked result and explicit remaining uncertainty."),
                "budget": {"max_tool_calls": min(8, role.get("max_tool_calls", 4)), "max_model_calls": min(3, role.get("max_model_calls", 2))},
                "status": "queued", "attempt": 0, "context_policy": role.get("context_policy", "relevant_evidence"),
                "instructions": role.get("instructions", ""), "plan_revision": revision,
                "runtime_tools": ["retrieve_evidence"],
            }
            tasks.append(Task.model_validate(task).model_dump())
    validate_plan(tasks)
    return tasks


def ready_tasks(tasks: list[dict]) -> list[dict]:
    completed = {task["task_id"] for task in tasks if task["status"] == "complete"}
    ready = [task for task in tasks if task["status"] in ("queued", "reopened") and set(task["depends_on"]) <= completed]
    priority = {"screen_regions": 0, "inspect_evidence": 1, "compute_features": 2, "assess_candidate": 3, "review_candidate": 4, "publish_shortlist": 5}
    return sorted(ready, key=lambda task: (priority[task["kind"]], task.get("candidate_id") or "", task["canonical_question_key"]))

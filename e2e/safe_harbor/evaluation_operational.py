"""Actual API/MongoDB experiment journey; no mocks or unit/component tests.

Usage: python e2e/safe_harbor/evaluation_operational.py --base-url http://127.0.0.1:8013
Pass --experiment-id to inspect an existing completed operational recording.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time
import requests

TOOLS = {"inspect_candidate", "screen_candidate", "list_evidence", "reference_sequence", "table_slice", "expression_comparison", "control_overlap", "gene_proximity"}
FORBIDDEN_KEYS = {"required_numbers", "required_decisions", "required_limitations", "unavailable_numbers", "reference_review_status"}


def assert_no_keys(value):
    if isinstance(value, dict):
        assert not FORBIDDEN_KEYS.intersection(value), "Evaluator answer/rubric field reached a worker packet"
        for item in value.values():
            assert_no_keys(item)
    elif isinstance(value, list):
        for item in value:
            assert_no_keys(item)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8013")
    parser.add_argument("--experiment-id")
    parser.add_argument("--blocked-experiment-id")
    parser.add_argument("--output", default="artifacts/safe_harbor/evaluation-e2e/latest-report.json")
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    def get(path):
        response = requests.get(base+path, timeout=30)
        response.raise_for_status()
        return response.json()
    def post(path, body):
        response = requests.post(base+path, json=body, timeout=30)
        response.raise_for_status()
        return response.json()
    health = get("/health")
    assert health["authoritative_store"] == "MongoDB" and health["coordinator_available"]
    experiment_id = args.experiment_id or post("/experiments", {"mode": "deterministic"})["evaluation_id"]
    deadline = time.monotonic()+args.timeout
    while True:
        experiment = get("/experiments/"+experiment_id)
        if experiment["status"] in {"operational_complete", "blocked", "failed"}:
            break
        assert time.monotonic() < deadline, "Experiment did not complete within the E2E deadline"
        time.sleep(.5)
    assert experiment["mode"] == "deterministic" and experiment["status"] == "operational_complete", experiment.get("error")
    rows = experiment["results"]
    assert len(rows) == 24 and len({(r["case_id"], r["arm"]) for r in rows}) == 24
    expected = {(case["case_id"], arm) for case in experiment["cases"] for arm in (("H0", "R0") if case["split"] == "development" else ("H0", "R0", "H1"))}
    assert {(r["case_id"], r["arm"]) for r in rows} == expected
    attempted = [r for r in rows if r.get("run_id")]
    assert len(attempted) == 18 and len({r["run_id"] for r in attempted}) == 18
    assert all(r["status"] == "not_run_no_candidate" and r["score"] is None for r in rows if r["arm"] == "H1")
    counts, denominators, snapshots = {}, {}, {}
    all_artifact_ids = set()
    for row in attempted:
        assert row["status"] == "operational_complete"
        snapshot = get("/runs/"+row["run_id"]+"/snapshot")
        snapshots[row["run_id"]] = snapshot
        run = snapshot["run"]
        assert run["harness_hash"] == row["harness_hash"] == experiment["arms"][row["arm"]]
        assert row["comparison_manifest_hash"] == run["comparison_manifest_hash"] == experiment["comparison_manifest_hash"]
        assert run["case_context"]["case_id"] == row["case_id"]
        assert run["comparison_model_settings"] == experiment["comparison_manifest"]["model"]
        for key, value in experiment["comparison_manifest"]["budget"].items():
            assert run["budget"][key] == value
        artifact_ids = {a["artifact_id"] for a in snapshot["artifacts"]}
        assert not all_artifact_ids.intersection(artifact_ids), "Arm namespaces overlap"
        all_artifact_ids.update(artifact_ids)
        assert all(a["run_id"] == row["run_id"] for a in snapshot["artifacts"])
        for artifact in snapshot["artifacts"]:
            if artifact["kind"] == "worker_trace":
                packet = artifact["data"]["context_packet"]
                assert_no_keys(packet)
                assert set(packet["allowed_tools"]) <= TOOLS
                assert packet["runtime_tools"] == ["retrieve_evidence"]
                assert {item["artifact_id"] for item in packet["evidence_manifest"]} <= artifact_ids
            elif artifact["kind"] == "scientific_tool_result":
                assert_no_keys(artifact["data"])
                if row["scenario_id"] == "controls_withheld" and artifact["data"].get("tool_name") == "control_overlap":
                    assert artifact["data"]["calculation"]["status"] == "unavailable"
        assert row["score"]["required_correct"] == 0 and row["score"]["required_total"] > 0
        assert row["score"]["coverage"] == 0, "Operational fixture must not fabricate a model answer"
        assert row["usage"]["model_calls"] == 0 and row["usage"]["tokens"] == 0
        counts[row["arm"]] = counts.get(row["arm"], 0)+row["usage"]["tool_calls"]
        denominators[row["arm"]] = denominators.get(row["arm"], 0)+row["score"]["required_total"]
        if row["arm"] == "R0":
            assert len([task for task in snapshot["tasks"] if task["status"] == "complete"]) == 3
            invoked = [a["data"].get("tool_name") for a in snapshot["artifacts"] if a["kind"] == "scientific_tool_result"]
            assert len(invoked) == 8 and set(invoked) == TOOLS
    assert counts == {"H0": 117, "R0": 72} and denominators == {"H0": 159, "R0": 159}
    assert experiment["promotion"]["status"] == "operational_only"
    assert not experiment["report"]["model_improvement_claim"] and not experiment["report"]["cost_win_claim"]
    assert len(experiment["report"]["case_results"]) == 24
    attachment = experiment["report_attachment"]
    attached = snapshots[attachment["run_id"]]
    assert attached["run"]["harness_hash"] == experiment["selected_harness_hash"]
    events = get("/runs/"+attachment["run_id"]+"/events?after_sequence="+str(attachment["sequence"]-1))
    events = events["events"] if isinstance(events, dict) else events
    assert any(event["sequence"] == attachment["sequence"] and event["cause"] == "experiment.reported" for event in events)
    blocked_id = args.blocked_experiment_id
    if not health["model_available"]:
        blocked = get("/experiments/"+blocked_id) if blocked_id else post("/experiments", {"mode": "real_model"})
        blocked_id = blocked["evaluation_id"]
        assert blocked["status"] == "blocked" and len(blocked["results"]) == 24
        assert all(row["status"] == "not_run_blocked" and row["score"] is None and row["run_id"] is None for row in blocked["results"])
    report = {"mode": "deterministic_operational_e2e", "experiment_id": experiment_id, "blocked_real_experiment_id": blocked_id,
              "assigned_records": 24, "actual_case_runs": 18, "tool_calls": counts, "model_calls": 0, "required_denominators": denominators,
              "model_improvement_claim": False, "comparison_manifest_hash": experiment["comparison_manifest_hash"], "report_attachment": attachment,
              "checks": ["Real API and MongoDB", "Fresh arm/case namespaces", "Same frozen model settings, evidence and budgets", "Every assigned row retained", "All R0 tools exactly once", "No evaluator keys in worker context or tool outputs", "Control withholding enforced", "Missing model answers score zero", "Selected harness used after selection", "Ordered committed comparison report"],
              "limitations": ["No genuine model execution or automatic model proposal.", "Answer-key attack attempts belong to the separate Q06 E2E; this journey audits all observed packets and allowed interfaces.", "No model improvement or biological safety claim."]}
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()

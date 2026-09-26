"""Real API/model/Mongo development preflight, with explicit paid-run limits.

Example (creates a real provider call; credentials remain on the API server):
  .venv/bin/python e2e/safe_harbor/model_preflight.py --arm R0 \
    --candidate pansio-1 --token-limit 400000 --tool-limit 40 --cost-limit-usd 5

This is an operational end-to-end journey followed by evaluator-only scoring,
not a unit/component test or a held-out comparison. It never sends gold answers
to the API. A timed-out provider call is not cancelled or counted as free.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from datetime import datetime, timezone

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]
from safe_harbor.evaluation.baselines import frozen_baselines
from safe_harbor.evaluation.cases import load_cases
from safe_harbor.evaluation.reference_answers import load_reference
from safe_harbor.evaluation.scoring import extract_run_output, score_case


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=("H0", "R0"), required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--token-limit", type=int, required=True)
    parser.add_argument("--tool-limit", type=int, required=True)
    parser.add_argument("--cost-limit-usd", type=float, required=True)
    parser.add_argument("--api", default="http://127.0.0.1:8016")
    parser.add_argument("--timeout-seconds", type=float, default=900)
    parser.add_argument("--output-root", type=Path, default=ROOT / "artifacts/safe_harbor/real-model-preflight")
    args = parser.parse_args()
    if min(args.token_limit, args.tool_limit, args.cost_limit_usd, args.timeout_seconds) <= 0:
        parser.error("Assigned budgets and deadline must be positive.")
    case = next((case for case in load_cases("development")
                 if case["candidate_id"] == args.candidate and case["scenario_id"] == "full_sources"), None)
    if case is None:
        parser.error("Choose a candidate from the frozen development split; validation/final preflights are prohibited.")
    api = args.api.rstrip("/")

    def get(path: str):
        response = requests.get(api + path, timeout=30)
        response.raise_for_status()
        return response.json()

    get("/health")
    harness = frozen_baselines()[args.arm]
    budget = {"token_limit": args.token_limit, "tool_limit": args.tool_limit, "cost_limit_usd": args.cost_limit_usd}
    print(json.dumps({"mode": "real_model", "purpose": "development_only_configuration_preflight",
                      "cost_label": "Actual model calls may incur charges up to the explicit assigned run cap.",
                      "arm": args.arm, "candidate_id": args.candidate, "assigned_budget": budget}), flush=True)
    response = requests.post(api + "/runs", json={"mode": "real_model", "candidate_ids": [args.candidate],
                              "harness_hash": harness["harness_hash"], "budget": budget}, timeout=30)
    response.raise_for_status()
    run_id = response.json()["run_id"]
    out = args.output_root / run_id
    out.mkdir(parents=True, exist_ok=True)
    print(json.dumps({"stage": "created", "run_id": run_id, "output": str(out)}), flush=True)
    started = time.monotonic()
    last = None
    while True:
        snapshot = get("/runs/" + run_id + "/snapshot")
        run = snapshot["run"]
        progress = (run["status"], tuple((t["role_id"], t["status"]) for t in snapshot["tasks"]))
        if progress != last:
            print(json.dumps({"stage": "progress", "run_id": run_id, "status": run["status"],
                              "tasks": progress[1], "elapsed_seconds": round(time.monotonic() - started, 1)}), flush=True)
            last = progress
        if run["status"] in ("complete", "blocked", "failed", "budget_exhausted"):
            break
        if time.monotonic() - started > args.timeout_seconds:
            report = {"status": "pending_terminal_reconciliation", "run_id": run_id,
                      "usage_complete": False, "budget_at_timeout": run["budget"],
                      "reason": "Coordinator/provider execution may still finish or incur already-reserved cost. Reconcile this run before dispatching another preflight."}
            (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report), flush=True)
            return 2
        time.sleep(3)
    score = score_case(case, load_reference(case["case_id"]), extract_run_output(snapshot))
    export = get("/runs/" + run_id + "/export")
    (out / "run-export.json").write_text(json.dumps(export, indent=2, ensure_ascii=False) + "\n")
    provider_responses = []
    for artifact in snapshot["artifacts"]:
        if artifact["kind"] != "worker_trace":
            continue
        for call in artifact["data"].get("provider_responses", []):
            response = call["response"]
            usage = response.get("usage") or {}
            for choice in response.get("choices", []):
                message = choice.get("message") or {}
                provider_responses.append({"artifact_id": artifact["artifact_id"],
                    "role_id": artifact["data"].get("role_id"), "call_index": call["call_index"],
                    "finish_reason": choice.get("finish_reason"), "content_characters": len(message.get("content") or ""),
                    "tool_call_count": len(message.get("tool_calls") or []), "completion_tokens": usage.get("completion_tokens"),
                    "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")})
    report = {"mode": "real_model", "purpose": "development_only_configuration_preflight_not_scored_comparison",
              "run_id": run_id, "arm": args.arm, "case_id": case["case_id"], "recorded_at": datetime.now(timezone.utc).isoformat(),
              "status": run["status"], "model_id": run["model_id"], "model_settings": run["model_settings"],
              "pricing_hash": run["model_pricing"]["pricing_hash"], "harness_hash": run["harness_hash"],
              "assigned_budget": budget, "budget": run["budget"], "score": score, "provider_responses": provider_responses,
              "valid_preflight": score["completed"] and score["support_ok"] and score["required_correct"] == score["required_total"],
              "limitations": ["Development-only preflight does not demonstrate improvement or held-out performance.",
                              "Gold answers and scoring stayed evaluator-only; no reference answers were sent to the worker."]}
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"stage": "finished", "run_id": run_id, "valid_preflight": report["valid_preflight"],
                      "required_correct": score["required_correct"], "required_total": score["required_total"],
                      "report": str(out / "report.json")}), flush=True)
    return 0 if report["valid_preflight"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

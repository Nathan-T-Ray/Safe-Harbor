"""Launch one genuine three-candidate recording after the frozen comparison.

Uses the selected saved harness, never changes the comparison or its scores.
Requires the running API's configured model. Assigned total cost cap: USD5.
Re-running reuses the locally recorded run ID instead of buying another run.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--api", default="http://127.0.0.1:8016")
    parser.add_argument("--output", type=Path, default=Path("artifacts/safe_harbor/multi-candidate-demo"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    launch_file = args.output / "launch.json"

    def request(path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(args.api.rstrip("/") + path, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)

    if launch_file.exists():
        saved = json.loads(launch_file.read_text())
        request("/runs/" + saved["run_id"] + "/snapshot")
        print(json.dumps({"reused_existing_recording": True, "run_id": saved["run_id"]}), flush=True)
        return
    print("Waiting for complete comparison and attached report before dispatch; no additional model calls yet.", flush=True)
    while True:
        experiment = request("/experiments/" + args.experiment)
        if experiment["status"] == "complete" and experiment.get("report_attachment"):
            break
        if experiment["status"] in ("failed", "blocked", "aborted_configuration_failure"):
            raise RuntimeError("Comparison did not finish; no demonstration was dispatched")
        time.sleep(5)
    selected = experiment["selected_harness_hash"]
    body = {"mode": "real_model", "candidate_ids": ["pansio-1", "olonne-18", "keppel-19"],
            "harness_hash": selected,
            "budget": {"token_limit": 1200000, "tool_limit": 120, "cost_limit_usd": 5}}
    # One POST only. A transport failure must be reconciled before any retry.
    created = request("/runs", body)
    record = {"schema_version": 1, "run_id": created["run_id"], "mode": "real_model",
              "created_at": datetime.now(timezone.utc).isoformat(), "request": body,
              "selection_experiment": args.experiment,
              "selection_decision": experiment["promotion"],
              "purpose": "Separate multi-candidate demonstration, excluded from frozen comparison scores",
              "limitations": ["Three publication-derived candidates, not a genome-wide search.",
                              "Queued tasks are a saved plan, not completed investigations.",
                              "No successful outcome or improvement is promised."]}
    launch_file.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"run_id": created["run_id"], "candidate_count": 3,
                      "assigned_budget": body["budget"], "model_mode": "real_model"}), flush=True)


if __name__ == "__main__":
    main()

"""Read-only E2E proof of real selection and subsequent saved-harness execution.

Reads the actual API and MongoDB. Creates no runs, model calls or ledger writes.
Exit 2 means recorded selection/reuse is still pending; it is never a pass.
This does not recompute scores or infer improvement from task completion.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from pymongo import MongoClient
import requests


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--api", default="http://127.0.0.1:8016")
    parser.add_argument("--mongo-uri", default="mongodb://127.0.0.1:27021/?replicaSet=safe-harbor-dev")
    parser.add_argument("--database", default="safe_harbor")
    parser.add_argument("--output", type=Path, default=Path("artifacts/safe_harbor/selected-harness-proof"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=5000)
    db = client[args.database]
    checks: list[dict] = []

    def get(path):
        response = requests.get(args.api.rstrip("/") + path, timeout=30)
        response.raise_for_status()
        return response.json()

    def check(name, condition, detail=None):
        checks.append({"name": name, "passed": bool(condition), "detail": detail})

    experiment = get("/experiments/" + args.experiment)
    stored = db.evaluations.find_one({"evaluation_id": args.experiment}, {"_id": 0})
    check("API experiment has identical frozen manifest to MongoDB", stored is not None and
          experiment["comparison_manifest"] == stored["comparison_manifest"])
    check("Experiment records genuine model mode", experiment["mode"] == "real_model")
    proposal = experiment.get("optimizer") or {}
    candidate_hash = experiment["arms"].get("H1")
    check("Automatic proposal produced the recorded H1 version", proposal.get("status") == "candidate_ready"
          and proposal.get("candidate_hash") == candidate_hash and bool(candidate_hash))
    candidate = db.harness_versions.find_one({"harness_hash": candidate_hash}, {"_id": 0})
    check("Candidate harness is durably saved", candidate is not None)
    decision = experiment.get("promotion")
    evidence = {"proposal_candidate_hash": candidate_hash, "selection": decision, "selected_run": None}
    pending = []
    if decision is None:
        pending.append("Validation selection has not been committed.")
    else:
        persisted = db.evaluations.find_one({"evaluation_id": "promotion:" + args.experiment}, {"_id": 0})
        check("Selection is separately durable in MongoDB", persisted is not None and
              all(persisted.get(key) == value for key, value in decision.items()))
        check("Selection uses only validation", decision.get("selection_split") == "validation")
        check("Selection rule is the pre-comparison frozen rule",
              decision.get("rule") == experiment["comparison_manifest"]["promotion_rule"])
        selected = experiment.get("selected_harness_hash")
        check("Selected version matches recorded decision", selected == decision.get("selected_harness_hash"))
        check("Selection is a terminal promote or reject decision", decision.get("status") in ("promoted", "rejected"))
        check("Rejection retains the parent version", decision.get("promoted") is True or
              selected == experiment["arms"]["H0"])
        validation = [r for r in experiment["results"] if r["split"] == "validation" and r["arm"] in ("H0", "H1")]
        assigned = {c["case_id"] for c in experiment["cases"] if c["split"] == "validation"}
        decided_cases = [c["case_id"] for c in decision.get("per_case", [])]
        check("Decision enumerates exactly validation cases and no final cases",
              len(decided_cases) == len(assigned) and set(decided_cases) == assigned)
        check("Decision binds the experiment, frozen manifest and exact competing hashes",
              decision.get("experiment_id") == args.experiment and
              decision.get("comparison_manifest_hash") == experiment.get("comparison_manifest_hash") and
              decision.get("parent_harness_hash") == experiment["arms"]["H0"] and
              decision.get("candidate_harness_hash") == candidate_hash)
        for arm in ("H0", "H1"):
            rows = [r for r in validation if r["arm"] == arm]
            check(f"{arm} selection retains every assigned validation result including failures",
                  len(rows) == len(assigned) and {r["case_id"] for r in rows} == assigned and
                  all(r.get("score") is not None for r in rows))
        evidence["validation_results"] = validation
        reused = [r for r in experiment["results"] if r["split"] == "final" and
                  r.get("harness_hash") == selected and r.get("run_id")]
        if not reused:
            pending.append("No subsequent final-case run has reused the selected saved version yet.")
        else:
            row = reused[0]
            exported = get("/runs/" + row["run_id"] + "/export")
            run = exported["snapshot"]["run"]
            events = exported["events"]
            tasks = exported["snapshot"]["tasks"]
            stored_run = db.runs.find_one({"run_id": row["run_id"]}, {"_id": 0})
            version = db.harness_versions.find_one({"harness_hash": selected}, {"_id": 0})
            check("Subsequent API run and MongoDB freeze the selected saved hash", version is not None and
                  run["harness_hash"] == stored_run["harness_hash"] == selected)
            check("Subsequent task instances use the selected version", bool(tasks) and
                  all(t["harness_hash"] == selected for t in tasks))
            initial_versions = events[0]["upserts"].get("harness_versions", []) if events else []
            check("Run creation committed the exact selected saved specification",
                  events[0]["cause"] == "run.created" and any(v == version for v in initial_versions))
            check("Selected-version run was created after validation selection",
                  datetime.fromisoformat(run["created_at"]) >= datetime.fromisoformat(decision["decided_at"]))
            check("Selected-version events form a contiguous ledger prefix",
                  [e["sequence"] for e in events] == list(range(1, exported["through_sequence"] + 1)))
            traces = [a for a in exported["snapshot"]["artifacts"] if a["kind"] == "worker_trace"
                      and a["data"].get("provider_responses")]
            if not traces:
                pending.append("Selected version is instantiated; no accepted genuine provider trace exists yet.")
            else:
                complete_ids = {t["task_id"] for t in tasks if t["status"] == "complete"}
                check("Saved selected version actually executed a real model worker", all(
                    a["run_id"] == run["run_id"] and a["provenance"].get("task_id") in complete_ids and
                    a["provenance"].get("harness_hash") == selected and
                    a["data"].get("context_packet", {}).get("harness_hash") == selected and
                    a["data"].get("mode") == "real_model" and
                    a["data"].get("usage", {}).get("model_calls", 0) >= 1 for a in traces))
            content = (json.dumps(exported, indent=2, ensure_ascii=False) + "\n").encode()
            filename = row["run_id"] + ".export.json"
            (args.output / filename).write_bytes(content)
            evidence["selected_run"] = {"run_id": row["run_id"], "case_id": row["case_id"],
                "harness_hash": selected, "status": run["status"], "through_sequence": exported["through_sequence"],
                "real_trace_ids": [a["artifact_id"] for a in traces], "export": filename,
                "export_sha256": hashlib.sha256(content).hexdigest()}
    failed = [c for c in checks if not c["passed"]]
    report = {"schema_version": 1, "observed_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_actual_api_and_mongodb_real_model_records", "experiment_id": args.experiment,
        "experiment_status": experiment["status"], "status": "failed" if failed else "pending" if pending else "passed",
        "checks": checks, "pending": pending, "evidence": evidence, "model_calls_by_inspection": 0,
        "ledger_writes": 0, "scoring_recomputed": False,
        "limitations": ["Structural execution and selected-version reuse do not establish improvement.",
                        "A rejected proposal remains a rejection; subsequent parent reuse is reported as such.",
                        "This reads the actual experiment; it never substitutes synthetic promotion or run records."]}
    (args.output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"status": report["status"], "checks": len(checks), "failures": len(failed), "pending": pending}))
    client.close()
    return 1 if failed else 2 if pending else 0


if __name__ == "__main__":
    raise SystemExit(main())

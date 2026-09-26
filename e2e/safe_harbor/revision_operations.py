#!/usr/bin/env python3
"""Actual API/process/Mongo evidence revision E2E with two in-flight branches.

Uses real source calculations and an explicitly mock harness topology. The
deterministic adapter does not establish any biological interpretation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from runtime_operations import Journey, ROOT, role
from safe_harbor.runtime.ledger import digest, now


class RevisionJourney(Journey):
    def execute(self):
        try:
            self.start(SAFE_HARBOR_OPERATIONAL_DELAY_BEFORE_ACCEPT="2", SAFE_HARBOR_OPERATIONAL_DELAY_ROLES="expression_a,expression_b")
            screen = role("reference_branch", "screen_regions"); screen["allowed_tools"] = ["reference_sequence"]
            first = role("expression_a", "inspect_evidence", ["reference_branch"]); first["allowed_tools"] = ["control_overlap"]
            second = role("expression_b", "compute_features", ["reference_branch"]); second["allowed_tools"] = ["expression_comparison"]
            assess = role("assessment", "assess_candidate", ["expression_a", "expression_b"])
            report = role("report", "publish_shortlist", ["assessment"])
            run_id = self.fixture("Mock topology; real source calculations; revision E2E", [screen, first, second, assess, report])
            self.request(f"/runs/{run_id}/resume", {})
            initial = self.wait_run(run_id)
            reference = next(task for task in initial["tasks"] if task["role_id"] == "reference_branch")
            reference_hash = digest(reference)
            assert initial["assessments"][0]["freshness"] == "current"
            first_revision = self.request(f"/runs/{run_id}/evidence-revisions", {"fixture_id": "withhold-control-evidence"})
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                active = self.request(f"/runs/{run_id}/snapshot")
                running = [task for task in active["tasks"] if task["status"] == "running" and task["role_id"] in ("expression_a", "expression_b")]
                if len(running) == 2:
                    break
                time.sleep(0.05)
            else:
                raise AssertionError("Both affected expression branches did not become active")
            assert all(assessment["freshness"] == "stale" for assessment in active["assessments"])
            active_task_ids = [task["task_id"] for task in running]
            second_revision = self.request(f"/runs/{run_id}/evidence-revisions", {"fixture_id": "restore-control-evidence"})
            final = self.wait_run(run_id)
            assert digest(next(task for task in final["tasks"] if task["role_id"] == "reference_branch")) == reference_hash
            assert all(next(task for task in final["tasks"] if task["task_id"] == task_id)["status"] == "superseded" for task_id in active_task_ids)
            rejected = list(self.ledger.db.operations.find({"run_id": run_id, "status": "rejected"}, {"_id": 0}))
            assert len(rejected) >= 2 and all("Consumed evidence changed" in operation["reason"] for operation in rejected)
            assert any(assessment["freshness"] == "stale" for assessment in final["assessments"])
            assert any(assessment["freshness"] == "current" for assessment in final["assessments"])
            assert final["run"]["replan_rounds"] == 2
            assert final["run"]["budget"]["tool_calls"] == 5
            assert final["run"]["budget"]["uncertain_tool_calls"] == 2
            initial_again = self.request(f"/runs/{run_id}/snapshot?through_sequence={initial['through_sequence']}")
            assert initial_again == initial
            self.report.update({"source_calculations": "real immutable workbook and reference inputs", "biological_results": "Computed numerical results only; no model interpretation", "passed": True})
            self.report["cases"].append({"case": "revision_during_two_active_branches", "run_id": run_id, "passed": True, "first_revision": first_revision, "second_revision": second_revision, "in_flight_rejected": active_task_ids, "rejection_count": len(rejected), "unchanged_reference_task_id": reference["task_id"], "historical_snapshot_unchanged": True, "final_events": final["through_sequence"], "export": self.export(run_id)})
        finally:
            self.stop()
            self.report["finished_at"] = now()
            (self.output / "report.json").write_text(json.dumps(self.report, indent=2))
            print(json.dumps(self.report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8018)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "safe_harbor" / "revision-e2e" / str(int(time.time())))
    args = parser.parse_args()
    RevisionJourney(args.port, args.output).execute()

#!/usr/bin/env python3
"""SH-Q04 E2E: prepared evidence revision applied while affected work is running.

Run from the repository root (worktree), with the replica set up:
  set -a; source .env; set +a
  PYTHONPATH=backend:. .venv/bin/python e2e/safe_harbor/revision.py --port 8032

Topology (a validated, explicitly mock-labelled harness; real deterministic scientific tools):
  per candidate: screen (annotation only)            -> unrelated branch
                 inspect -> assess                   -> affected branch A (expression scope)
                 compare -> review                   -> affected branch B (expression scope)
                 report depends on assess + review
Two candidates run; the fixed fixtures only revise the first candidate, so the whole second
candidate is additional unrelated work. A real API process runs the coordinator with a labeled
operational delay before acceptance so that the revision (POST /runs/{id}/evidence-revisions,
fixture "withhold-control-evidence") lands while branch B's compare task is executing and after
branch A's inspect task has been accepted. A second phase applies "restore-control-evidence"
after completion to exercise assessment staleness. Mode: deterministic_operational.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from _support import E2E, default_output, mock_harness
from safe_harbor.harness.specification import SCIENTIFIC_INSTRUCTIONS, validate_harness


def role(role_id, kind, depends_on, tools):
    return {"role_id": role_id, "kind": kind, "question": f"E2E revision topology fixture: {role_id} (no biological claim).",
            "depends_on": depends_on, "allowed_tools": tools, "context_policy": "relevant_evidence",
            "instructions": SCIENTIFIC_INSTRUCTIONS, "decision_target": "expression_exclusion_concern",
            "completion_condition": "Persist evidence-linked tool results.", "max_tool_calls": 4, "max_model_calls": 2}


def topology_harness() -> dict:
    record = mock_harness("E2E revision topology fixture (mock harness structure)", [
        role("screen", "screen_regions", [], ["inspect_candidate", "screen_candidate"]),
        role("inspect", "inspect_evidence", [], ["list_evidence", "table_slice", "reference_sequence"]),
        role("compare", "compute_features", [], ["expression_comparison", "control_overlap", "gene_proximity"]),
        role("assess", "assess_candidate", ["screen", "inspect"], ["expression_comparison"]),
        role("review", "review_candidate", ["screen", "compare"], ["screen_candidate", "control_overlap"]),
        role("report", "publish_shortlist", ["assess", "review"], []),
    ])
    return validate_harness(record)  # the fixture itself satisfies the runtime's harness rules


class Revision(E2E):
    def fingerprints(self, run_id, task_id):
        return sorted((a["artifact_id"], a["content_hash"]) for a in self.ledger.db.artifacts.find({"run_id": run_id, "provenance.task_id": task_id}, {"_id": 0}))

    def revision_during_active_work(self):
        reservation = 200
        harness = topology_harness()
        c0, c1 = self.candidate_ids(2)
        run_id = self.fixture_run(harness, [c0, c1], label="evidence revision during active work")
        tid = lambda cid, r: f"{run_id}:{cid}:{r}:r0"
        self.start(SAFE_HARBOR_OPERATIONAL_DELAY_BEFORE_ACCEPT="4", SAFE_HARBOR_OPERATIONAL_TOKEN_RESERVATION=str(reservation))

        def window():
            tasks = {t["task_id"]: t for t in self.db_tasks(run_id)}
            return tasks[tid(c0, "compare")]["status"] == "running" and tasks[tid(c0, "inspect")]["status"] == "complete" and tasks

        before = self.wait_until(window, timeout=120, interval=0.05, what="compare running with inspect accepted")
        pre_sequence = self.db_run(run_id)["through_sequence"]
        pre_artifacts = {task_id: self.fingerprints(run_id, task_id) for task_id, t in before.items() if t["status"] == "complete"}
        status, result = self.call("POST", f"/runs/{run_id}/evidence-revisions", {"fixture_id": "withhold-control-evidence"})
        states_at_revision = {task_id: t["status"] for task_id, t in before.items()}
        affected_expected = sorted(tid(c0, r) for r in ("inspect", "compare", "assess", "review", "report"))
        unrelated = sorted([tid(c0, "screen")] + [tid(c1, r) for r in ("screen", "inspect", "compare", "assess", "review", "report")])
        self.check(
            "revision:applied_through_api_while_affected_task_running",
            status == 200 and result.get("affected_task_ids") == affected_expected and sorted(result.get("unchanged_task_ids", [])) == unrelated
            and self.ledger.db.tasks.find_one({"task_id": tid(c0, "compare")})["status"] == "superseded",
            http_status=status, response=result, task_states_when_revision_posted=states_at_revision, sequence_before_revision=pre_sequence,
        )

        final = self.wait_terminal(run_id, timeout=180)
        compare_id = tid(c0, "compare")
        rejected = self.operations(run_id, prefix=f"rejected:accept:{compare_id}:", status="rejected")
        compare = self.ledger.db.tasks.find_one({"task_id": compare_id}, {"_id": 0})
        self.check(
            "revision:stale_acceptance_rejected",
            len(rejected) == 1 and f"Consumed evidence changed: scope:{c0}:expression" in rejected[0]["reason"]
            and not self.fingerprints(run_id, compare_id) and compare["status"] == "superseded"
            and not self.accepted_ops(run_id, compare_id),
            rejection_records=rejected, superseded_task={k: compare.get(k) for k in ("status", "superseded_by", "reopen_reason", "attempt")},
            artifacts_accepted_from_stale_attempt=len(self.fingerprints(run_id, compare_id)),
        )

        tasks = {t["task_id"]: t for t in self.db_tasks(run_id)}
        successors = {task_id: tasks.get(f"{task_id}:revision1") for task_id in affected_expected}
        scope_key = f"scope:{c0}:expression"
        succ_summary = {k: None if v is None else {"status": v["status"], "attempt": v["attempt"], "plan_revision": v.get("plan_revision"), "supersedes": v.get("supersedes_task_id"),
                                                   "expression_scope_version": next((r["version"] for r in v["input_read_set"] if r["key"] == scope_key), None), "depends_on": v["depends_on"]}
                        for k, v in successors.items()}
        overlap = [a["data"]["calculation"] for a in self.ledger.db.artifacts.find({"run_id": run_id, "provenance.task_id": f"{compare_id}:revision1", "data.tool_name": "control_overlap"}, {"_id": 0})]
        self.check(
            "revision:successors_ran_on_new_evidence_version",
            final["status"] == "complete" and all(s and s["status"] == "complete" and s["expression_scope_version"] == 2 and s["plan_revision"] == 1 for s in succ_summary.values())
            and all(tasks[t]["status"] == "superseded" for t in affected_expected)
            # successor rewires to reopened parents but keeps the unaffected, still-valid screen result
            and set(succ_summary[tid(c0, "assess")]["depends_on"]) == {tid(c0, "screen"), f"{tid(c0, 'inspect')}:revision1"},
            final_status=final["status"], successors=succ_summary,
            successor_control_overlap=[{k: c.get(k) for k in ("status", "reason")} for c in overlap],
        )
        self.check("revision:successor_saw_withheld_control_evidence_as_unavailable", bool(overlap) and all(c.get("status") == "unavailable" for c in overlap),
                   control_overlap_calculations=[{k: c.get(k) for k in ("status", "reason")} for c in overlap])

        inspect_id = tid(c0, "inspect")
        old = pre_artifacts[inspect_id]
        fetched = [self.call("GET", f"/runs/{run_id}/artifacts/{aid}") for aid, _ in old]
        historical = self.call("GET", f"/runs/{run_id}/snapshot?through_sequence={pre_sequence}")[1]
        hist_inspect = next(t for t in historical["tasks"] if t["task_id"] == inspect_id)
        self.check(
            "revision:old_results_remain_inspectable",
            bool(old) and all(code == 200 and body["content_hash"] == h for (code, body), (_, h) in zip(fetched, old))
            and hist_inspect["status"] == "complete" and sorted(hist_inspect["result_artifact_ids"]) == sorted(a for a, _ in old)
            and tasks[inspect_id]["status"] == "superseded" and tasks[inspect_id]["result_artifact_ids"] == hist_inspect["result_artifact_ids"],
            superseded_task=inspect_id, old_artifacts=[a for a, _ in old], http_statuses=[code for code, _ in fetched],
            historical_snapshot_sequence=pre_sequence, historical_status=hist_inspect["status"],
        )

        unrelated_state = {t: {"status": tasks[t]["status"], "attempt": tasks[t]["attempt"], "accepts": len(self.accepted_ops(run_id, t)),
                               "successor": f"{t}:revision1" in tasks, "artifacts_unchanged": (t not in pre_artifacts) or self.fingerprints(run_id, t) == pre_artifacts[t]} for t in unrelated}
        c1_assess = [a for a in self.ledger.db.assessments.find({"run_id": run_id, "candidate_id": c1}, {"_id": 0})]
        self.check(
            "revision:unrelated_work_remains_valid",
            all(v == {"status": "complete", "attempt": 1, "accepts": 1, "successor": False, "artifacts_unchanged": True} for v in unrelated_state.values()) and bool(c1_assess),
            unrelated=unrelated_state, second_candidate_assessments=[{k: a[k] for k in ("assessment_id", "freshness")} for a in c1_assess],
        )
        budget = final["budget"]
        self.check(
            "revision:interrupted_reservation_recorded_as_uncertain",
            budget["uncertain_tokens"] == reservation and budget["reserved_tokens"] == 0 and budget["model_calls"] == 0,
            final_budget=budget, note="The superseded compare attempt held an operational reservation; revision moved it to uncertain, not refunded.",
        )
        self.check("revision:worker_cap", self.max_concurrent_running(run_id) <= 2, max_concurrent_running=self.max_concurrent_running(run_id))

        # Phase 2: completed assessment becomes stale on a later prepared revision; old revision remains stored.
        c0_assessments_before = {a["assessment_id"]: a for a in self.ledger.db.assessments.find({"run_id": run_id, "candidate_id": c0}, {"_id": 0})}
        c1_ids = sorted(a["assessment_id"] for a in c1_assess)
        status2, result2 = self.call("POST", f"/runs/{run_id}/evidence-revisions", {"fixture_id": "restore-control-evidence"})
        stale_seq = result2.get("sequence")
        snap = self.call("GET", f"/runs/{run_id}/snapshot?through_sequence={stale_seq}")[1] if stale_seq else {"assessments": []}
        fresh = {a["assessment_id"]: a["freshness"] for a in snap["assessments"]}
        final2 = self.wait_terminal(run_id, timeout=180)
        stored = {a["assessment_id"]: a for a in self.ledger.db.assessments.find({"run_id": run_id}, {"_id": 0})}
        new_c0 = [a for a in stored.values() if a["candidate_id"] == c0 and a["assessment_id"] not in c0_assessments_before]
        self.check(
            "revision:assessments_marked_stale_and_old_revisions_retained",
            status2 == 200 and bool(c0_assessments_before) and all(fresh.get(a) == "stale" for a in c0_assessments_before)
            and bool(c1_ids) and all(fresh.get(a) == "current" for a in c1_ids) and all(stored[a] == c0_assessments_before[a] for a in c0_assessments_before),
            http_status=status2, response=result2, freshness_at_revision_event=fresh,
            immutable_old_revisions_unchanged=all(stored[a] == c0_assessments_before[a] for a in c0_assessments_before),
        )
        tasks2 = self.db_tasks(run_id)
        failed = [{"task_id": t["task_id"], "kind": t["kind"], "error": t.get("error")} for t in tasks2 if t["status"] == "failed"]
        rejections = [{"operation_id": o["operation_id"][:160], "reason": o["reason"]} for o in self.operations(run_id, status="rejected")]
        self.check(
            "revision:second_revision_successors_complete",
            final2["status"] == "complete" and bool(new_c0) and all(next(r["version"] for r in a["input_read_set"] if r["key"] == scope_key) == 3 for a in new_c0),
            final_status=final2["status"], stop_reason=final2.get("stop_reason"),
            new_assessment_revisions=[{k: a[k] for k in ("assessment_id", "assessment_revision", "freshness")} for a in new_c0],
            failed_tasks=failed, rejected_operations=rejections, task_nodes=len(tasks2), replan_rounds=final2["replan_rounds"],
            max_concurrent_running=self.max_concurrent_running(run_id),
            note="In this topology assess and review of one candidate are independent, so both may run concurrently under the two-worker cap.",
        )
        self.report.setdefault("runs", {})["revision_during_active_work"] = {"run_id": run_id, "harness_hash": harness["harness_hash"], "export": self.export_run(run_id)}
        self.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8032)
    parser.add_argument("--output", type=Path, default=default_output("revision"))
    args = parser.parse_args()
    journey = Revision("revision", args.port, args.output)
    raise SystemExit(journey.execute([journey.revision_during_active_work]))

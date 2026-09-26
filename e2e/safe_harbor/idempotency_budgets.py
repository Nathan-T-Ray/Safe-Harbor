#!/usr/bin/env python3
"""SH-Q05 E2E: idempotency, invalid plans, prohibited patches and durable budgets.

Run from the repository root (worktree) with MONGODB_URI (MongoDB Atlas) in the environment:
  set -a; source .env; set +a
  PYTHONPATH=backend:. .venv/bin/python e2e/safe_harbor/idempotency_budgets.py --port 8033

Every case runs against actual uvicorn API/coordinator processes and an isolated MongoDB
sh_e2e_ database on the MONGODB_URI deployment. Operation re-submission goes through the runtime's own Ledger.accept
against that live database while the API process is serving (there is no HTTP endpoint for
worker acceptances). Invalid harness records are stored in harness_versions exactly as a
corrupted/hostile saved record would be, then referenced through POST /runs. Structural
patches go through the harness library's apply_patch (no HTTP patch endpoint exists).
Mode: deterministic_operational; token reservations are labeled fault-injection units.
"""
from __future__ import annotations

import argparse
import copy
import json
import secrets
import time
from pathlib import Path

from _atlas import add_keep_db_flag
from _support import E2E, default_output
from safe_harbor.harness import baseline_harness, save_harness
from safe_harbor.harness.specification import apply_patch, canonical_hash
from safe_harbor.runtime.ledger import LedgerError, digest
from safe_harbor.runtime.worker import read_set_for


def rehash(record: dict) -> dict:
    record = copy.deepcopy(record)
    record["harness_hash"] = canonical_hash(record)
    return record


class Boundaries(E2E):
    legit_runs: list

    def create(self, body: dict) -> tuple[int, dict]:
        status, response = self.call("POST", "/runs", body)
        if status == 201:
            self.legit_runs.append(response["run_id"])
        return status, response

    def stopped_after(self, run_id: str, sequence: int):
        """Wait for a run.stopped event later than `sequence` (a fresh coordinator decision)."""
        def seen():
            event = self.ledger.db.events.find_one({"run_id": run_id, "cause": "run.stopped", "sequence": {"$gt": sequence}})
            return event and self.db_run(run_id)
        return self.wait_until(seen, timeout=60, what=f"fresh stop decision for {run_id}")

    def open_work(self, run: dict) -> list[str]:
        """Tasks still queued/reopened/running although the run reports 'complete' (should be empty)."""
        if run["status"] != "complete":
            return []
        return sorted(f"{t['task_id']}={t['status']}" for t in self.db_tasks(run["run_id"]) if t["status"] not in ("complete", "superseded"))

    def completion_race_probe(self):
        """A revision that lands while a fresh coordinator is deciding to stop must not be dropped."""
        self.start()
        attempts = []
        for attempt in range(10):
            code, created = self.create({"candidate_ids": self.candidate_ids(1), "mode": "deterministic", "budget": {"tool_limit": 200}})
            run_id = created["run_id"]
            first = self.wait_terminal(run_id)["through_sequence"]
            self.call("POST", f"/runs/{run_id}/resume", {})
            code_rev, body = self.revise(run_id, "withhold-control-evidence")
            self.wait_terminal(run_id)
            time.sleep(2)  # allow any legitimate re-dispatch before judging
            run = self.db_run(run_id)
            open_work = self.open_work(run)
            causes = [(e["sequence"], e["cause"], e["upserts"]["runs"][0]["status"]) for e in self.events(run_id) if e["sequence"] > first]
            attempts.append({"run_id": run_id, "revision_http": code_rev, "final_status": run["status"], "open_work_while_complete": open_work, "events_after_first_completion": causes})
            if open_work:
                break
        violations = [a for a in attempts if a["open_work_while_complete"]]
        self.check(
            "idempotency:revision_racing_coordinator_stop_not_dropped",
            not violations, attempts=attempts,
            note="POST /resume on a complete run followed immediately by a prepared revision. A violation means the run was marked complete while reopened successors never ran. Absence of a violation in these attempts is not proof the race is absent.",
        )
        self.stop()

    def revise(self, run_id: str, fixture_id: str):
        return self.call("POST", f"/runs/{run_id}/evidence-revisions", {"fixture_id": fixture_id})

    # ---------------------------------------------------------------- case 1
    def operation_idempotency_and_replans(self):
        self.legit_runs = []
        self.start()
        cid = self.candidate_ids(1)[0]
        status, created = self.create({"candidate_ids": [cid], "mode": "deterministic"})
        run_id = created["run_id"]
        run = self.wait_terminal(run_id)
        assess = next(t for t in self.db_tasks(run_id) if t["kind"] == "assess_candidate")
        operation_id = f"accept:{assess['task_id']}:{assess['coordinator_epoch']}:{assess['attempt']}"
        stored = self.ledger.db.operations.find_one({"operation_id": operation_id}, {"_id": 0})
        event = next(e for e in self.events(run_id) if e["operation_id"] == operation_id)
        trace = next(a for a in event["upserts"]["artifacts"] if a["kind"] == "worker_trace")
        payload = {"run_id": run_id, "task_id": assess["task_id"], "epoch": assess["coordinator_epoch"], "attempt": assess["attempt"],
                   "input_read_set": assess["input_read_set"], "artifacts": event["upserts"]["artifacts"],
                   "assessments": event["upserts"]["assessments"], "usage": trace["data"]["usage"]}
        before = {"through_sequence": run["through_sequence"], "operations": self.ledger.db.operations.count_documents({"run_id": run_id}),
                  "assessments": self.ledger.db.assessments.count_documents({"run_id": run_id}), "artifacts": self.ledger.db.artifacts.count_documents({"run_id": run_id})}
        replay = self.ledger.accept(operation_id, payload)
        after = {"through_sequence": self.db_run(run_id)["through_sequence"], "operations": self.ledger.db.operations.count_documents({"run_id": run_id}),
                 "assessments": self.ledger.db.assessments.count_documents({"run_id": run_id}), "artifacts": self.ledger.db.artifacts.count_documents({"run_id": run_id})}
        self.check(
            "idempotency:identical_operation_deduplicates",
            status == 201 and run["status"] == "complete" and digest(payload) == stored["payload_hash"] and replay == stored["accepted_result"] and before == after,
            operation_id=operation_id, reconstructed_payload_hash=digest(payload), stored_payload_hash=stored["payload_hash"],
            returned=replay, ledger_counts_before=before, ledger_counts_after=after,
        )
        conflict = copy.deepcopy(payload)
        conflict["assessments"][0]["conclusion"] = "Conflicting resubmission under a reused operation ID (E2E probe)."
        try:
            self.ledger.accept(operation_id, conflict)
            outcome = "accepted"
        except LedgerError as exc:
            outcome = f"rejected {exc.code}: {exc}"
        rejection = self.ledger.db.operations.find_one({"operation_id": f"rejected:{operation_id}:{digest(conflict)}"}, {"_id": 0})
        stored_assessment = self.ledger.db.assessments.find_one({"assessment_id": payload["assessments"][0]["assessment_id"]}, {"_id": 0})
        self.check(
            "idempotency:conflicting_hash_rejected_with_audit_record",
            "different content" in outcome and rejection is not None and rejection["status"] == "rejected"
            and self.db_run(run_id)["through_sequence"] == before["through_sequence"] and stored_assessment["conclusion"] == payload["assessments"][0]["conclusion"],
            outcome=outcome, rejection_record=rejection, through_sequence=self.db_run(run_id)["through_sequence"],
        )

        # Prepared revisions through the API: repeat is a no-op, three replans max.
        # (This run was created with the default 40-call tool budget; replans need more, so a
        # second run with an explicit, sufficient tool budget isolates the replan limit.)
        code, created = self.create({"candidate_ids": [cid], "mode": "deterministic", "budget": {"tool_limit": 200}})
        run_id = created["run_id"]
        self.wait_terminal(run_id)
        steps, consistency = [], {}
        code, body = self.revise(run_id, "withhold-control-evidence"); steps.append(("withhold#1", code, body.get("sequence")))
        consistency["after_withhold#1"] = self.open_work(self.wait_terminal(run_id))
        snap = self.db_run(run_id)
        code_dup, body_dup = self.revise(run_id, "withhold-control-evidence"); steps.append(("withhold#1-repeat", code_dup, body_dup))
        dup_run = self.db_run(run_id)
        revised_events = sum(e["cause"] == "evidence.revised" for e in self.events(run_id))
        self.check(
            "idempotency:repeated_prepared_revision_is_noop",
            code_dup == 200 and body_dup.get("status") == "unchanged" and dup_run["replan_rounds"] == snap["replan_rounds"] == 1
            and dup_run["evidence_versions"] == snap["evidence_versions"] and revised_events == 1,
            response=body_dup, replan_rounds=dup_run["replan_rounds"], evidence_revised_events=revised_events,
            note="Repeat is detected by the fixture's target state; each POST gets a fresh operation ID (no client-supplied idempotency key).",
        )
        # The repeat still enqueues the coordinator; let that claim/stop cycle settle so the next revision cannot race it
        # (the race itself is probed separately in completion_race_probe).
        self.stopped_after(run_id, body_dup.get("through_sequence", 0))
        code, body = self.revise(run_id, "restore-control-evidence"); steps.append(("restore#2", code, body.get("sequence")))
        consistency["after_restore#2"] = self.open_work(self.wait_terminal(run_id))
        code, body = self.revise(run_id, "withhold-control-evidence"); steps.append(("withhold#3", code, body.get("sequence")))
        final3 = self.wait_terminal(run_id)
        consistency["after_withhold#3"] = self.open_work(final3)
        tasks3 = len(self.db_tasks(run_id))
        code4, body4 = self.revise(run_id, "restore-control-evidence")
        after4 = self.db_run(run_id)
        self.check(
            "budget:three_replan_limit_enforced",
            [s[1] for s in steps] == [200, 200, 200, 200] and final3["replan_rounds"] == 3 and final3["status"] == "complete"
            and not any(consistency.values())
            and code4 == 429 and "Three-replan" in body4.get("detail", "") and after4["through_sequence"] == final3["through_sequence"]
            and after4["evidence_versions"] == final3["evidence_versions"] and len(self.db_tasks(run_id)) == tasks3,
            steps=steps, fourth_revision={"http_status": code4, "body": body4}, replan_rounds=after4["replan_rounds"], task_nodes=tasks3,
            final_status=final3["status"], budget=final3["budget"], open_work_when_terminal=consistency,
            through_sequence_unchanged=after4["through_sequence"] == final3["through_sequence"],
        )
        self.report.setdefault("runs", {})["idempotency_and_replans"] = {"run_id": run_id, "export": self.export_run(run_id)}
        self.stop()

    # ---------------------------------------------------------------- case 2
    def invalid_plans_rejected_before_dispatch(self):
        self.legit_runs = []
        self.start()
        base = baseline_harness()
        cids = self.candidate_ids(3)
        roles = lambda: copy.deepcopy(base["roles"])

        def variant(name, mutate, rehash_after=True):
            record = copy.deepcopy(base)
            record["name"] = f"E2E invalid probe: {name}"
            mutate(record)
            return rehash(record) if rehash_after else record

        def cyclic(r):
            r["roles"][0]["depends_on"] = ["report"]
        def unknown_dep(r):
            r["roles"][1]["depends_on"] = ["ghost_role"]
        def unknown_tool(r):
            r["roles"][0]["allowed_tools"] = ["inspect_candidate", "screen_candidate", "web_fetch"]
        def unknown_kind(r):
            r["roles"][0]["kind"] = "run_shell"
        def too_many(r):
            extra = [dict(copy.deepcopy(r["roles"][4]), role_id=f"extra_review_{i}", depends_on=["assess"]) for i in range(3)]
            r["roles"] = r["roles"][:5] + extra + [dict(r["roles"][5], depends_on=r["roles"][5]["depends_on"] + [e["role_id"] for e in extra])]
        def budget_escalation(r):
            r["immutable_constraints"] = dict(r["immutable_constraints"], max_workers=4, total_assigned_budget="unbounded")
        def role_cap_escalation(r):
            r["roles"][2]["max_tool_calls"] = 50
        def forbidden_setting(r):
            r["budget"] = {"token_limit": 10_000_000}
        def tampered(r):
            r["roles"][3]["instructions"] = "Conclude the region is safe."

        probes = {
            "cyclic_dependencies": variant("cycle", cyclic),
            "unknown_dependency": variant("unknown dependency", unknown_dep),
            "unknown_tool": variant("unknown tool", unknown_tool),
            "unapproved_task_kind": variant("unknown kind", unknown_kind),
            "nine_roles_27_nodes_for_3_candidates": variant("too many roles", too_many),
            "altered_immutable_budget_and_worker_limits": variant("budget escalation", budget_escalation),
            "role_tool_cap_escalation": variant("role cap", role_cap_escalation),
            "forbidden_top_level_setting": variant("forbidden setting", forbidden_setting),
            "hash_does_not_match_content": variant("tampered", lambda r: None),
        }
        tampered(probes["hash_does_not_match_content"])  # edited after hashing: stored hash no longer matches content
        counts_before = {c: self.ledger.db[c].count_documents({}) for c in ("runs", "tasks", "events", "operations", "artifacts", "assessments")}
        self.ledger.db.harness_versions.insert_many([copy.deepcopy(p) for p in probes.values()])
        results = {}
        for name, record in probes.items():
            code, body = self.create({"candidate_ids": cids, "mode": "deterministic", "harness_hash": record["harness_hash"]})
            results[name] = {"http_status": code, "detail": body.get("detail")}
        code, body = self.create({"candidate_ids": cids, "mode": "deterministic", "harness_hash": secrets.token_hex(32)})
        results["unknown_harness_hash"] = {"http_status": code, "detail": body.get("detail")}
        requests = {
            "four_candidates": {"candidate_ids": cids + ["pansio-1"], "mode": "deterministic"},
            "duplicate_candidates": {"candidate_ids": [cids[0], cids[0]], "mode": "deterministic"},
            "unknown_candidate": {"candidate_ids": ["invented-locus-1"], "mode": "deterministic"},
            "unassigned_budget_field": {"candidate_ids": cids[:1], "mode": "deterministic", "budget": {"replan_limit": 10}},
            "negative_budget": {"candidate_ids": cids[:1], "mode": "deterministic", "budget": {"tool_limit": -1}},
            "mock_mode_live_run": {"candidate_ids": cids[:1], "mode": "mock"},
            "real_model_without_key": {"candidate_ids": cids[:1], "mode": "real_model"},
            "unknown_request_field": {"candidate_ids": cids[:1], "mode": "deterministic", "max_workers": 8},
        }
        for name, body in requests.items():
            code, response = self.create(body)
            results[name] = {"http_status": code, "detail": response.get("detail") if isinstance(response.get("detail"), str) else "schema validation error"}
        expected = {name: 422 for name in results}
        expected.update(unknown_harness_hash=404, real_model_without_key=409)
        counts_after = {c: self.ledger.db[c].count_documents({}) for c in counts_before}
        self.check(
            "invalid_plans:rejected_before_any_record_or_dispatch",
            all(results[name]["http_status"] == expected[name] for name in results) and not self.legit_runs and counts_after == counts_before,
            results=results, expected_status=expected, ledger_counts_before=counts_before, ledger_counts_after=counts_after,
        )

        # Oversized plan through the revision path: 3 candidates x 6 roles = 18; a revision adds 5 -> 23; another would make 28.
        code, created = self.create({"candidate_ids": cids, "mode": "deterministic", "budget": {"tool_limit": 200}})
        run_id = created["run_id"]
        self.wait_terminal(run_id)
        first = self.revise(run_id, "withhold-control-evidence")
        state = self.wait_terminal(run_id)
        nodes = len(self.db_tasks(run_id))
        second = self.revise(run_id, "restore-control-evidence")
        after = self.db_run(run_id)
        self.check(
            "invalid_plans:24_node_limit_enforced_on_replanning",
            first[0] == 200 and nodes == 23 and second[0] == 429 and "24-node" in second[1].get("detail", "")
            and len(self.db_tasks(run_id)) == 23 and after["through_sequence"] == state["through_sequence"] and after["replan_rounds"] == 1,
            first_revision_status=first[0], nodes_after_first=nodes, second_revision={"http_status": second[0], "body": second[1]},
            replan_rounds=after["replan_rounds"], final_status=state["status"],
        )

        # Structural patches (harness library; there is no HTTP patch endpoint).
        exp_status, exp_body = self.call("POST", "/experiments", {"mode": "deterministic"})
        patches = {
            "edit_criteria": {"operations": [{"op": "change_criteria", "criteria": "loosened"}]},
            "edit_budget": {"operations": [{"op": "set_budget", "token_limit": 10_000_000}]},
            "new_role_budget_escalation": {"operations": [{"op": "insert_reviewer", "after_role_id": "assess", "role": {"role_id": "extra_review", "kind": "review_candidate", "question": "Probe", "allowed_tools": ["control_overlap"], "max_tool_calls": 99}}]},
            "new_role_unapproved_tool": {"operations": [{"op": "insert_reviewer", "after_role_id": "assess", "role": {"role_id": "extra_review", "kind": "review_candidate", "question": "Probe", "allowed_tools": ["web_fetch"]}}]},
            "reassign_unowned_tool": {"operations": [{"op": "reassign_tools", "from_role_id": "screen", "to_role_id": "report", "tools": ["shell"]}]},
            "split_dropping_tool": {"operations": [{"op": "split_role", "role_id": "compare", "roles": [{"role_id": "compare_a", "kind": "compute_features", "question": "a", "allowed_tools": ["expression_comparison"]}, {"role_id": "compare_b", "kind": "compute_features", "question": "b", "allowed_tools": ["gene_proximity"]}]}]},
            "extra_patch_field": {"operations": [{"op": "change_context", "role_id": "assess", "context_policy": "numerical_first"}], "model_id": "other-model"},
        }
        patch_results = {}
        for name, patch in patches.items():
            try:
                apply_patch(base, patch, proposal_mode="deterministic_operational")
                patch_results[name] = "accepted"
            except LedgerError as exc:
                patch_results[name] = f"rejected {exc.code}: {exc}"
        allowed = apply_patch(base, {"operations": [{"op": "insert_reviewer", "after_role_id": "assess", "role": {"role_id": "second_review", "kind": "review_candidate", "question": "Independently re-check the assessment's denominators.", "allowed_tools": ["control_overlap", "screen_candidate"]}}]}, proposal_mode="deterministic_operational")
        save_harness(allowed, database=self.ledger.db)
        code, created = self.create({"candidate_ids": cids[:1], "mode": "deterministic", "harness_hash": allowed["harness_hash"]})
        control = self.wait_terminal(created["run_id"]) if code == 201 else None
        self.check(
            "invalid_plans:prohibited_patches_rejected_allowed_patch_executes",
            all(v.startswith("rejected 422") for v in patch_results.values()) and code == 201 and control["status"] == "complete"
            and len(self.db_tasks(created["run_id"])) == 7,
            prohibited=patch_results, allowed_patch_hash=allowed["harness_hash"], allowed_run_status=None if control is None else control["status"],
            allowed_run_tasks=len(self.db_tasks(created["run_id"])) if code == 201 else 0,
            post_experiments={"http_status": exp_status, "detail": exp_body.get("detail")},
        )
        self.stop()

    # ---------------------------------------------------------------- case 3
    def worker_cap(self):
        run_id = self.fixture_run(baseline_harness(), self.candidate_ids(3), label="worker cap")
        self.start(SAFE_HARBOR_OPERATIONAL_DELAY_BEFORE_ACCEPT="3")
        tasks = self.wait_until(lambda: (t := self.db_tasks(run_id)) and sum(x["status"] == "running" for x in t) == 2 and t, interval=0.05, what="two running workers")
        run = self.db_run(run_id)
        complete = {t["task_id"] for t in tasks if t["status"] == "complete"}
        third = next(t for t in tasks if t["status"] == "queued" and set(t["depends_on"]) <= complete)
        try:
            self.ledger.reserve(run_id, third["task_id"], run["coordinator_epoch"], read_set_for(self.ledger, run, third), 0, 0, 0.0)
            outcome = "reserved (cap NOT enforced)"
        except LedgerError as exc:
            outcome = f"rejected {exc.code}: {exc}"
        third_after = self.ledger.db.tasks.find_one({"task_id": third["task_id"]}, {"_id": 0})
        final = self.wait_terminal(run_id, timeout=240)
        peak = self.max_concurrent_running(run_id)
        self.check(
            "budget:two_worker_cap_enforced_durably",
            "Two-worker concurrency cap" in outcome and third_after["status"] == "queued" and peak == 2 and final["status"] == "complete",
            third_reservation_probe=outcome, probed_task=third["task_id"], probed_task_status_after=third_after["status"],
            max_concurrent_running_from_event_replay=peak, final_status=final["status"], task_nodes=len(self.db_tasks(run_id)),
            note="Probe calls Ledger.reserve with the live coordinator epoch while two workers hold reservations.",
        )
        self.stop()

    # ---------------------------------------------------------------- case 4
    def tool_budget(self):
        self.legit_runs = []
        self.start()
        code, created = self.create({"candidate_ids": self.candidate_ids(1), "mode": "deterministic", "budget": {"tool_limit": 3}})
        run_id = created["run_id"]
        stopped = self.wait_terminal(run_id)
        tasks = {t["role_id"]: t["status"] for t in self.db_tasks(run_id)}
        self.check(
            "budget:tool_limit_stops_dispatch",
            code == 201 and stopped["status"] == "budget_exhausted" and stopped["budget"]["tool_calls"] <= 3 and stopped["budget"].get("reserved_tools", 0) == 0
            and tasks["screen"] == "complete" and all(tasks[r] == "queued" for r in ("inspect", "compare", "assess", "review", "report")),
            final_status=stopped["status"], stop_reason=stopped.get("stop_reason"), budget=stopped["budget"], task_status=tasks,
        )
        self.stop()
        self.start()  # fresh process: a budget_exhausted run is not re-enqueued; explicit resume re-checks the durable cap
        code_r, _ = self.call("POST", f"/runs/{run_id}/resume", {})
        again = self.stopped_after(run_id, stopped["through_sequence"])
        new_starts = [e["sequence"] for e in self.events(run_id) if e["cause"] == "task.started" and e["sequence"] > stopped["through_sequence"]]
        self.check(
            "budget:tool_limit_durable_across_restart_and_resume",
            code_r == 200 and again["status"] == "budget_exhausted" and again["budget"]["tool_calls"] == stopped["budget"]["tool_calls"] and not new_starts
            and again["coordinator_epoch"] == stopped["coordinator_epoch"] + 1,
            resume_status=code_r, status_after_resume=again["status"], tool_calls_before=stopped["budget"]["tool_calls"], tool_calls_after=again["budget"]["tool_calls"],
            task_started_events_after_resume=new_starts, epochs=(stopped["coordinator_epoch"], again["coordinator_epoch"]),
        )
        self.report.setdefault("runs", {})["tool_budget"] = {"run_id": run_id}
        self.stop()

    def token_budget(self):
        reservation, limit = 1000, 1500
        hooks = {"SAFE_HARBOR_OPERATIONAL_TOKEN_RESERVATION": str(reservation)}
        # Control: the same limit with no crash. Total demand fits when reservations are sequential.
        control_id = self.fixture_run(baseline_harness(), self.candidate_ids(1), budget={"token_limit": limit}, label="token contention control")
        self.start(**hooks)
        control = self.wait_terminal(control_id)
        control_tasks = {t["role_id"]: t["status"] for t in self.db_tasks(control_id)}
        self.check(
            "budget:reservation_contention_not_reported_as_exhaustion",
            control["status"] == "complete",
            final_status=control["status"], stop_reason=control.get("stop_reason"), task_status=control_tasks, budget=control["budget"],
            note=f"Two concurrent {reservation}-unit reservations exceed a {limit} limit, so one dispatch is deferred with 429. Deterministic usage is 0, so the sequential total always fits; the run should end 'complete'.",
        )
        self.stop()

        run_id = self.fixture_run(baseline_harness(), self.candidate_ids(1), budget={"token_limit": limit}, label="token budget after uncertain spend")
        self.start(SAFE_HARBOR_CRASH_AFTER_RESERVE="compute_features", **hooks)
        code = self.wait_exit(timeout=90)
        self.stop()
        self.start(**hooks)
        stopped = self.wait_terminal(run_id)
        compare = next(t for t in self.db_tasks(run_id) if t["role_id"] == "compare")
        budget = stopped["budget"]
        self.check(
            "budget:uncertain_tokens_count_against_limit",
            code == 87 and stopped["status"] == "budget_exhausted" and budget["uncertain_tokens"] == reservation and budget["reserved_tokens"] == 0
            and budget["tokens_used"] == 0 and budget["model_calls"] == 0 and compare["status"] == "queued" and compare["attempt"] == 1,
            crash_exit_code=code, final_status=stopped["status"], budget=budget, compare={k: compare.get(k) for k in ("status", "attempt", "recovery_reason")},
            usage_note="Operational reservation units only; no model call.",
        )
        self.stop()
        self.start(**hooks)
        self.call("POST", f"/runs/{run_id}/resume", {})
        again = self.stopped_after(run_id, stopped["through_sequence"])
        self.check(
            "budget:token_limit_durable_across_restart_and_resume",
            again["status"] == "budget_exhausted" and again["budget"]["uncertain_tokens"] == reservation
            and not [e for e in self.events(run_id) if e["cause"] == "task.started" and e["sequence"] > stopped["through_sequence"]],
            status_after_resume=again["status"], budget=again["budget"],
        )
        self.stop()

    def interrupted_attempt_retry_limit(self):
        run_id = self.fixture_run(baseline_harness(), self.candidate_ids(1), label="retry limit")
        exits = []
        for _ in range(2):
            self.start(SAFE_HARBOR_CRASH_AFTER_RESERVE="screen_regions")
            exits.append(self.wait_exit(timeout=90))
            self.stop()
        self.start()
        final = self.wait_terminal(run_id)
        screen = next(t for t in self.db_tasks(run_id) if t["role_id"] == "screen")
        reserves = self.operations(run_id, prefix=f"reserve:{screen['task_id']}:")
        self.check(
            "budget:one_retry_for_interrupted_attempt",
            exits == [87, 87] and screen["status"] == "failed" and screen["attempt"] == 2 and len(reserves) == 2 and final["status"] == "blocked",
            crash_exit_codes=exits, screen={k: screen.get(k) for k in ("status", "attempt", "recovery_reason")}, reserve_operations=len(reserves),
            final_status=final["status"], stop_reason=final.get("stop_reason"),
            note="Covers the interrupted-attempt retry path (Ledger.claim). The transient-exception retry path (Ledger.task_failed transient=True) has no fault hook and is not exercised.",
        )
        self.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8033)
    parser.add_argument("--output", type=Path, default=default_output("idempotency_budgets"))
    add_keep_db_flag(parser)
    args = parser.parse_args()
    journey = Boundaries("idem_budget", args.port, args.output)
    journey.keep_db = args.keep_db
    journey.report["not_exercised"] = {
        "transient_exception_retry": "No runtime hook raises TimeoutError/ConnectionError inside a deterministic worker; only the crash/interrupted-attempt retry path is exercised.",
        "cost_budget": "Deterministic runs reserve and spend $0; cost enforcement needs real-model usage or a cost fault hook.",
        "provider_usage_breach": "Ledger.accept budget_breach requires provider-reported usage; no model key.",
    }
    raise SystemExit(journey.execute([journey.operation_idempotency_and_replans, journey.completion_race_probe, journey.invalid_plans_rejected_before_dispatch, journey.worker_cap,
                                      journey.tool_budget, journey.token_budget, journey.interrupted_attempt_retry_limit]))

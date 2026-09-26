#!/usr/bin/env python3
"""SH-Q03 E2E: actual crash recovery of the Safe Harbor coordinator.

Run from the repository root (worktree) with MONGODB_URI (MongoDB Atlas) in the environment:
  set -a; source .env; set +a
  PYTHONPATH=backend:. .venv/bin/python e2e/safe_harbor/recovery.py --port 8031 [--keep-db]

Only the API/coordinator processes are killed and restarted. The database is a managed
deployment this journey cannot and does not restart; durability is exercised across process death.

Cases (each uses real uvicorn API+coordinator processes and an isolated MongoDB database):
  1. accept_then_die: a run created through POST /runs (frozen H0 baseline harness) whose
     coordinator process exits (os._exit 86, SAFE_HARBOR_CRASH_AFTER_ACCEPT hook) right after the
     compute_features acceptance transaction commits and before LangGraph checkpoints the node.
  2. reserve_then_die: the process exits (87, SAFE_HARBOR_CRASH_AFTER_RESERVE) right after a
     durable budget reservation, before any worker execution.
  3. external_sigkill: an external SIGKILL while two workers are mid-execution.
After each death a fresh process is started. Accepted outputs must be preserved exactly,
unfinished work must resume, and uncertain expenditure must remain recorded.
Mode: deterministic_operational. Token "reservations" are labeled fault-injection units, not model usage.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from _atlas import add_keep_db_flag
from _support import E2E, default_output
from langgraph.checkpoint.mongodb import MongoDBSaver
from safe_harbor.harness import baseline_harness


class Recovery(E2E):
    def task_by_role(self, run_id: str, role_id: str, candidate_id: str | None = None) -> dict:
        query = {"run_id": run_id, "role_id": role_id, "status": {"$ne": "superseded"}}
        if candidate_id:
            query["candidate_id"] = candidate_id
        return self.ledger.db.tasks.find_one(query, {"_id": 0})

    def artifact_fingerprint(self, run_id: str, task_id: str) -> list[tuple[str, str]]:
        return sorted((a["artifact_id"], a["content_hash"]) for a in self.ledger.db.artifacts.find({"run_id": run_id, "provenance.task_id": task_id}, {"_id": 0}))

    def latest_checkpoint_values(self, thread_id: str):
        saver = MongoDBSaver(self.ledger.client, db_name=self.database, checkpoint_collection_name="runtime_checkpoints", writes_collection_name="runtime_checkpoint_writes")
        found = saver.get_tuple({"configurable": {"thread_id": thread_id}})
        return None if found is None else dict(found.checkpoint.get("channel_values", {}))

    # -------------------------------------------------------------- case 1
    def accept_then_die(self):
        cid = self.candidate_ids(1)[0]
        self.start(SAFE_HARBOR_CRASH_AFTER_ACCEPT="compute_features")
        status, created = self.call("POST", "/runs", {"candidate_ids": [cid], "mode": "deterministic"})
        self.check("accept_crash:run_created_via_api", status == 201, http_status=status, body=created)
        run_id = created["run_id"]
        exit_code = self.wait_exit(timeout=90)
        self.check("accept_crash:process_died_at_hook", exit_code == 86, exit_code=exit_code, hook="SAFE_HARBOR_CRASH_AFTER_ACCEPT=compute_features")

        compare = self.task_by_role(run_id, "compare")
        screen = self.task_by_role(run_id, "screen")
        before = {task["role_id"]: {"status": task["status"], "attempt": task["attempt"], "epoch": task.get("coordinator_epoch")} for task in self.db_tasks(run_id)}
        compare_thread = f"{run_id}:{compare['task_id']}:{compare['coordinator_epoch']}:{compare['attempt']}"
        screen_thread = f"{run_id}:{screen['task_id']}:{screen['coordinator_epoch']}:{screen['attempt']}"
        compare_ckpt, screen_ckpt = self.latest_checkpoint_values(compare_thread), self.latest_checkpoint_values(screen_thread)
        compare_accepts = self.accepted_ops(run_id, compare["task_id"])
        preserved = {role: self.artifact_fingerprint(run_id, self.task_by_role(run_id, role)["task_id"]) for role in ("screen", "inspect", "compare")}
        run_before = self.db_run(run_id)
        self.check(
            "accept_crash:acceptance_durable_but_node_not_checkpointed",
            compare["status"] == "complete" and len(compare_accepts) == 1 and bool(preserved["compare"])
            and (compare_ckpt is None or "accepted_sequence" not in compare_ckpt)
            and screen_ckpt is not None and "accepted_sequence" in screen_ckpt,
            task_states_after_death=before, compare_accept_operations=[op["operation_id"] for op in compare_accepts],
            compare_latest_checkpoint_channels=None if compare_ckpt is None else sorted(compare_ckpt),
            screen_latest_checkpoint_channels=None if screen_ckpt is None else sorted(screen_ckpt),
            note="The ledger holds the compare acceptance; its LangGraph thread has no completed-node checkpoint (screen's does), i.e. the process died between acceptance and checkpoint.",
            through_sequence_at_death=run_before["through_sequence"],
        )

        self.stop()
        restarted = time.monotonic()
        self.start()
        final = self.wait_terminal(run_id, timeout=120)
        resumed_after = round(time.monotonic() - restarted, 2)
        tasks = {task["role_id"]: task for task in self.db_tasks(run_id)}
        after = {role: self.artifact_fingerprint(run_id, tasks[role]["task_id"]) for role in ("screen", "inspect", "compare")}
        self.check(
            "accept_crash:accepted_outputs_preserved_not_reexecuted",
            after == preserved and tasks["compare"]["attempt"] == 1 and len(self.accepted_ops(run_id, compare["task_id"])) == 1,
            artifacts_before_restart=preserved, artifacts_after_restart=after, compare_attempt=tasks["compare"]["attempt"],
        )
        downstream = {role: {"status": tasks[role]["status"], "epoch": tasks[role].get("coordinator_epoch"), "attempt": tasks[role]["attempt"]} for role in ("assess", "review", "report")}
        recovered = [e for e in self.events(run_id) if e["cause"] == "coordinator.recovered"]
        self.check(
            "accept_crash:unfinished_work_resumed_by_fresh_process",
            final["status"] == "complete" and all(v["status"] == "complete" and v["epoch"] == final["coordinator_epoch"] >= 2 for v in downstream.values()) and len(recovered) >= 2,
            final_status=final["status"], final_epoch=final["coordinator_epoch"], downstream=downstream,
            recovery_events=[{"sequence": e["sequence"], "epoch": e["upserts"]["runs"][0]["coordinator_epoch"]} for e in recovered],
            seconds_from_restart_to_terminal=resumed_after,
            assessments=self.ledger.db.assessments.count_documents({"run_id": run_id}),
            note="Resumption needs no manual call: the fresh coordinator enqueues running runs and takes over once the dead process's 12 s lease expires.",
        )
        seqs = [e["sequence"] for e in self.events(run_id)]
        self.check("accept_crash:event_history_contiguous", seqs == list(range(1, final["through_sequence"] + 1)), events=len(seqs), through_sequence=final["through_sequence"])
        self.report.setdefault("runs", {})["accept_then_die"] = {"run_id": run_id, "export": self.export_run(run_id)}
        self.stop()

    # -------------------------------------------------------------- case 2
    def reserve_then_die(self):
        reservation = 1000
        cid = self.candidate_ids(1)[0]
        run_id = self.fixture_run(baseline_harness(), [cid], label="reserve crash")
        hooks = {"SAFE_HARBOR_OPERATIONAL_TOKEN_RESERVATION": str(reservation)}
        self.start(SAFE_HARBOR_CRASH_AFTER_RESERVE="compute_features", **hooks)
        exit_code = self.wait_exit(timeout=90)
        self.check("reserve_crash:process_died_at_hook", exit_code == 87, exit_code=exit_code, hook="SAFE_HARBOR_CRASH_AFTER_RESERVE=compute_features")
        compare = self.task_by_role(run_id, "compare")
        budget_at_death = self.db_run(run_id)["budget"]
        preserved = {role: self.artifact_fingerprint(run_id, self.task_by_role(run_id, role)["task_id"]) for role in ("screen", "inspect")}
        reserve_ops = self.operations(run_id, prefix=f"reserve:{compare['task_id']}:")
        self.check(
            "reserve_crash:reservation_durable_at_death",
            compare["status"] == "running" and compare["attempt"] == 1 and compare["reservation"].get("tokens") == reservation
            and budget_at_death["reserved_tokens"] == reservation and len(reserve_ops) == 1 and not self.artifact_fingerprint(run_id, compare["task_id"]),
            compare_task={k: compare.get(k) for k in ("status", "attempt", "reservation")}, budget_at_death=budget_at_death,
            reserve_operations=[op["operation_id"] for op in reserve_ops],
        )
        self.stop()
        self.start(**hooks)
        final = self.wait_terminal(run_id, timeout=120)
        budget = final["budget"]
        compare = self.task_by_role(run_id, "compare")
        recovered = [t for e in self.events(run_id) if e["cause"] == "coordinator.recovered" for t in e["upserts"].get("tasks", []) if t["task_id"] == compare["task_id"]]
        traces = list(self.ledger.db.artifacts.find({"run_id": run_id, "kind": "worker_trace"}, {"_id": 0, "data.usage": 1}))
        measured_tools = sum(t["data"]["usage"]["tool_calls"] for t in traces)
        self.check(
            "reserve_crash:uncertain_expenditure_recorded",
            budget["uncertain_tokens"] == reservation and budget["reserved_tokens"] == 0 and budget["tokens_used"] == 0 and budget["model_calls"] == 0
            and bool(recovered) and "uncertain" in recovered[0].get("recovery_reason", ""),
            final_budget=budget, recovery_task_record={k: recovered[0].get(k) for k in ("status", "attempt", "recovery_reason")} if recovered else None,
            tool_calls_measured_from_worker_traces=measured_tools, tool_calls_ledger=budget["tool_calls"],
            interrupted_tool_reservation_charged=budget["tool_calls"] - measured_tools,
            usage_note=f"{reservation} operational reservation units; no model call happened, and none is reported as model usage.",
        )
        after = {role: self.artifact_fingerprint(run_id, self.task_by_role(run_id, role)["task_id"]) for role in ("screen", "inspect")}
        self.check(
            "reserve_crash:unfinished_work_resumed_and_prior_outputs_kept",
            final["status"] == "complete" and compare["status"] == "complete" and compare["attempt"] == 2
            and len(self.accepted_ops(run_id, compare["task_id"])) == 1 and after == preserved,
            final_status=final["status"], compare_attempt=compare["attempt"],
            compare_accept_operations=[op["operation_id"] for op in self.accepted_ops(run_id, compare["task_id"])],
            prior_outputs_unchanged=after == preserved,
        )
        self.report.setdefault("runs", {})["reserve_then_die"] = {"run_id": run_id, "export": self.export_run(run_id)}
        self.stop()

    # -------------------------------------------------------------- case 3
    def external_sigkill(self):
        reservation = 500
        cids = self.candidate_ids(2)
        run_id = self.fixture_run(baseline_harness(), cids, label="external SIGKILL")
        self.start(SAFE_HARBOR_OPERATIONAL_DELAY_BEFORE_ACCEPT="3", SAFE_HARBOR_OPERATIONAL_TOKEN_RESERVATION=str(reservation))

        def mid_flight():
            tasks = self.db_tasks(run_id)
            running = [t for t in tasks if t["status"] == "running"]
            complete = [t for t in tasks if t["status"] == "complete"]
            return len(running) == 2 and len(complete) >= 2 and (running, complete)

        running, complete = self.wait_until(mid_flight, timeout=90, interval=0.05, what="two running workers after completed work")
        preserved = {t["task_id"]: self.artifact_fingerprint(run_id, t["task_id"]) for t in complete}
        exit_code = self.kill()
        budget_at_death = self.db_run(run_id)["budget"]
        states = {t["task_id"]: t["status"] for t in self.db_tasks(run_id)}
        interrupted = [t["task_id"] for t in running if states[t["task_id"]] == "running"]
        self.check(
            "sigkill:killed_mid_execution",
            exit_code == -9 and len(interrupted) == 2 and budget_at_death["reserved_tokens"] == 2 * reservation,
            exit_code=exit_code, interrupted_tasks=interrupted, completed_before_kill=sorted(preserved), budget_at_death=budget_at_death,
        )
        self.stop()
        self.start(SAFE_HARBOR_OPERATIONAL_TOKEN_RESERVATION=str(reservation))
        final = self.wait_terminal(run_id, timeout=150)
        tasks = {t["task_id"]: t for t in self.db_tasks(run_id)}
        after = {task_id: self.artifact_fingerprint(run_id, task_id) for task_id in preserved}
        self.check(
            "sigkill:completed_outputs_preserved",
            after == preserved and all(tasks[t]["attempt"] == 1 and len(self.accepted_ops(run_id, t)) == 1 for t in preserved),
            preserved_tasks=len(preserved), identical=after == preserved,
        )
        self.check(
            "sigkill:interrupted_work_resumed",
            final["status"] == "complete" and all(tasks[t]["status"] == "complete" and tasks[t]["attempt"] == 2 for t in interrupted),
            final_status=final["status"], interrupted={t: {"status": tasks[t]["status"], "attempt": tasks[t]["attempt"]} for t in interrupted},
        )
        self.check(
            "sigkill:uncertain_expenditure_recorded",
            final["budget"]["uncertain_tokens"] == len(interrupted) * reservation and final["budget"]["reserved_tokens"] == 0 and final["budget"]["model_calls"] == 0,
            final_budget=final["budget"], expected_uncertain_tokens=len(interrupted) * reservation,
        )
        peak = self.max_concurrent_running(run_id)
        self.check("sigkill:worker_cap_held_across_restart", peak <= 2, max_concurrent_running_from_event_replay=peak)
        self.report.setdefault("runs", {})["external_sigkill"] = {"run_id": run_id, "export": self.export_run(run_id)}
        self.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8031)
    parser.add_argument("--output", type=Path, default=default_output("recovery"))
    add_keep_db_flag(parser)
    args = parser.parse_args()
    journey = Recovery("recovery", args.port, args.output)
    journey.keep_db = args.keep_db
    raise SystemExit(journey.execute([journey.accept_then_die, journey.reserve_then_die, journey.external_sigkill]))

"""One persistent coordinator; at most two workers; checkpoint/ledger reconciliation."""
from __future__ import annotations

import logging
import os
import queue
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import TypedDict

from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.graph import END, START, StateGraph

from safe_harbor.runtime.compiler import ready_tasks
from safe_harbor.runtime.ledger import LedgerError, identifier
from safe_harbor.runtime.worker import execute_worker, read_set_for

logger = logging.getLogger(__name__)


class WorkerState(TypedDict, total=False):
    run_id: str
    task_id: str
    epoch: int
    attempt: int
    accepted_sequence: int


class Coordinator:
    def __init__(self, ledger):
        self.ledger = ledger
        self.owner = identifier("coordinator")
        self.queue = queue.Queue()
        self.pending = set()
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="safe-harbor-worker")
        self.checkpointer = MongoDBSaver(ledger.client, db_name=ledger.db.name, checkpoint_collection_name="runtime_checkpoints", writes_collection_name="runtime_checkpoint_writes")
        graph = StateGraph(WorkerState)
        graph.add_node("execute_and_accept", self._execute_and_accept)
        graph.add_edge(START, "execute_and_accept")
        graph.add_edge("execute_and_accept", END)
        self.graph = graph.compile(checkpointer=self.checkpointer)

    def start(self):
        self.thread = threading.Thread(target=self._loop, name="safe-harbor-coordinator", daemon=True)
        self.thread.start()
        for run in self.ledger.db.runs.find({"status": {"$in": ["queued", "running", "revising"]}}, {"run_id": 1}):
            self.enqueue(run["run_id"])

    def stop(self):
        self.stop_event.set()
        self.queue.put(None)
        if self.thread:
            self.thread.join(timeout=3)
        self.pool.shutdown(wait=False, cancel_futures=True)

    def enqueue(self, run_id: str):
        with self.lock:
            if run_id not in self.pending:
                self.pending.add(run_id)
                self.queue.put(run_id)

    def _loop(self):
        while not self.stop_event.is_set():
            run_id = self.queue.get()
            if run_id is None:
                return
            retry_lease = False
            try:
                self._run(run_id)
            except LedgerError as exc:
                retry_lease = "unexpired lease" in str(exc)
                if not retry_lease:
                    logger.warning("Run %s stopped: %s", run_id, exc)
            except Exception:
                logger.exception("Coordinator failed for %s", run_id)
            finally:
                with self.lock:
                    self.pending.discard(run_id)
            if retry_lease and not self.stop_event.wait(1):
                self.enqueue(run_id)

    def _execute_and_accept(self, state: WorkerState):
        task = self.ledger.db.tasks.find_one({"task_id": state["task_id"], "run_id": state["run_id"]}, {"_id": 0})
        run = self.ledger.get_run(state["run_id"])
        self.ledger.check_epoch(run, state["epoch"])
        if not task or task["status"] != "running" or task["attempt"] != state["attempt"]:
            raise LedgerError("Worker attempt is no longer active")
        payload = execute_worker(self.ledger, run, task)
        if run.get("operational_fixture"):
            delay = min(10.0, max(0.0, float(os.getenv("SAFE_HARBOR_OPERATIONAL_DELAY_BEFORE_ACCEPT", "0"))))
            delayed_roles = set(filter(None, os.getenv("SAFE_HARBOR_OPERATIONAL_DELAY_ROLES", "").split(",")))
            if delay and (not delayed_roles or task["role_id"] in delayed_roles):
                time.sleep(delay)
        operation_id = f"accept:{task['task_id']}:{state['epoch']}:{state['attempt']}"
        accepted = self.ledger.accept(operation_id, payload)
        # Explicit operational crash point: acceptance is durable, checkpoint is not yet written.
        if os.getenv("SAFE_HARBOR_CRASH_AFTER_ACCEPT") == task["kind"]:
            os._exit(86)
        return {"accepted_sequence": accepted["sequence"]}

    def _dispatch(self, run: dict, task: dict, epoch: int):
        real = run["mode"] == "real_model" and not (run.get("baseline_arm") == "R0" and task["kind"] != "assess_candidate")
        model_calls = task["budget"]["max_model_calls"] if real else 0
        tokens = int(os.getenv("SAFE_HARBOR_TOKENS_PER_TASK", "12000")) if real else 0
        if run.get("operational_fixture") and not real:
            # Fault-injection proof only: a labeled reservation, never reported as model use.
            tokens = int(os.getenv("SAFE_HARBOR_OPERATIONAL_TOKEN_RESERVATION", "0"))
        tools = task["budget"]["max_tool_calls"] if real else min(len(task["allowed_tools"]), task["budget"]["max_tool_calls"])
        # Unknown dollar usage stays reserved/uncertain; it cannot substantiate a cost win.
        cost = 0.0  # Verified endpoint price × next request bound is reserved before each provider call.
        reads = read_set_for(self.ledger, run, task)
        reserved = self.ledger.reserve(run["run_id"], task["task_id"], epoch, reads, tokens, tools, cost)
        if os.getenv("SAFE_HARBOR_CRASH_AFTER_RESERVE") == task["kind"]:
            os._exit(87)
        thread_id = f"{run['run_id']}:{task['task_id']}:{epoch}:{reserved['attempt']}"
        return self.pool.submit(self.graph.invoke, {"run_id": run["run_id"], "task_id": task["task_id"], "epoch": epoch, "attempt": reserved["attempt"]}, {"configurable": {"thread_id": thread_id}})

    def _run(self, run_id: str):
        run = self.ledger.get_run(run_id)
        if run["mode"] == "real_model" and not (os.getenv("OPENROUTER_API_KEY") and run.get("model_id")):
            return
        epoch = self.ledger.claim(run_id, self.owner)
        active = {}
        last_heartbeat = 0
        budget_exhausted = False
        while not self.stop_event.is_set():
            if time.monotonic() - last_heartbeat > 3:
                if not self.ledger.heartbeat(run_id, epoch, self.owner):
                    return
                last_heartbeat = time.monotonic()
            run = self.ledger.get_run(run_id)
            self.ledger.check_epoch(run, epoch)
            tasks = list(self.ledger.db.tasks.find({"run_id": run_id}, {"_id": 0}))
            ready = ready_tasks(tasks)
            for task in ready[:max(0, 2 - len(active))]:
                try:
                    future = self._dispatch(run, task, epoch)
                except LedgerError as exc:
                    if exc.code == 429:
                        budget_exhausted = True
                        break
                    if "Consumed evidence changed" in str(exc) or "not ready" in str(exc):
                        continue
                    raise
                active[future] = task["task_id"]
                run = self.ledger.get_run(run_id)
            if not active:
                if budget_exhausted:
                    self.ledger.finish(run_id, epoch, "budget_exhausted", "Assigned resource cap prevents additional work; uncertainty is preserved.")
                elif all(task["status"] in ("complete", "superseded") for task in tasks):
                    self.ledger.finish(run_id, epoch, "complete", "All current tasks accepted; scientific unknowns remain explicit.")
                else:
                    self.ledger.finish(run_id, epoch, "blocked", "No ready task can make progress; failed or unavailable dependencies remain inspectable.")
                return
            completed, _ = wait(active, timeout=0.5, return_when=FIRST_COMPLETED)
            for future in completed:
                task_id = active.pop(future)
                try:
                    future.result()
                except Exception as exc:
                    transient = isinstance(exc, (TimeoutError, ConnectionError)) or exc.__class__.__name__ in ("APITimeoutError", "APIConnectionError", "RateLimitError")
                    self.ledger.task_failed(run_id, task_id, epoch, f"{exc.__class__.__name__}: {exc}", transient=transient, failure=getattr(exc, "worker_failure", None))

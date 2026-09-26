#!/usr/bin/env python3
"""SH-Q11 — produce and rehearse the canonical real Safe Harbor demonstration run.

One real_model run (OpenRouter, the configured MODEL_ID) investigates the three published
candidates through the MongoDB ledger. While two workers are mid-flight the API process is
killed with SIGKILL and restarted on the same database, so recovery happens inside the canonical
record. After completion a prepared evidence-availability revision (withhold control evidence)
reopens the dependent tasks, which the real model executes again. The run is exported, camera
cues are derived by the UI's own deriveCues() from the exported events, and a fresh Playwright
client at 1280x720 presents the complete recorded story from commit 0 and measures its duration.

  PYTHONPATH=backend:. .venv/bin/python scripts/safe_harbor_demo.py
  # rehearse the presentation of an existing canonical run without any model call:
  PYTHONPATH=backend:. .venv/bin/python scripts/safe_harbor_demo.py --present-only RUN_ID --database DB

Every attempt is reported with its outcome and cost. Nothing is retried silently, and a failed
beat is reported as not demonstrated instead of being substituted. Credentials stay in the
ignored .env and are never printed or written.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)
MONGO_URI = "mongodb://127.0.0.1:27021/?replicaSet=safe-harbor-dev"
CANDIDATES = ["pansio-1", "olonne-18", "keppel-19"]
TERMINAL = {"complete", "blocked", "failed", "stopped", "budget_exhausted"}
SAFE_LABEL = re.compile(r"\b(is|are|as)\s+(a\s+)?(globally\s+)?safe\b(?!\s*(or|/))", re.I)
# Spec "Three-minute demo" outline, in order, with target seconds.
OUTLINE = [
    ("context", 20), ("genome_zoom", 25), ("expression_investigation", 30), ("evidence_revision", 25),
    ("recovery", 20), ("structural_patch_and_promotion", 40), ("versioned_dossier", 20),
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def http(base: str, path: str, body=None, timeout=30):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        try:
            return error.code, json.load(error)
        except Exception:
            return error.code, {"detail": str(error)}


class Demo:
    def __init__(self, args):
        self.args = args
        stamp = time.strftime("%Y%m%dT%H%M%S")
        self.output = ROOT / "artifacts/safe_harbor/demo" / stamp
        self.output.mkdir(parents=True, exist_ok=True)
        self.database = args.database or f"safe_harbor_q11_demo_{stamp}"
        self.base = f"http://127.0.0.1:{args.api_port}"
        self.ui = f"http://127.0.0.1:{args.ui_port}"
        self.api = None
        self.vite = None
        self.checks: list[dict] = []
        self.report = {
            "ticket": "SH-Q11", "started_at": now(), "database": self.database, "output": str(self.output.relative_to(ROOT)),
            "mode_requested": "real_model", "model_id": os.getenv("MODEL_ID"), "model_provider": "openrouter",
            "candidate_ids": CANDIDATES, "attempts": [], "checks": self.checks, "findings": [],
            "labels": {"run": "REAL MODEL (real_model) — genuine OpenRouter calls committed to MongoDB",
                       "presentation": "RECORDED REPLAY of the committed MongoDB events; the browser phase makes no model call and no ledger write"},
        }

    # ------------------------------------------------------------------ processes
    def check(self, name: str, ok: bool, evidence=None):
        self.checks.append({"check": name, "passed": bool(ok), "evidence": evidence})
        print(("PASS " if ok else "FAIL ") + name, flush=True)

    def flush(self):
        (self.output / "report.json").write_text(json.dumps(self.report, indent=1))

    def start_api(self, label: str):
        if self.args.attach:
            try:
                status, health = http(self.base, "/health", timeout=2)
                if status == 200 and health.get("database") == self.database:
                    self.report.setdefault("findings", []).append(f"Reused the already running API on port {self.args.api_port} for {self.database} (not started by this driver invocation).")
                    return health
            except Exception:
                pass
        env = {**os.environ, "MONGODB_URI": MONGO_URI, "MONGODB_DATABASE": self.database, "PYTHONPATH": f"{ROOT / 'backend'}:{ROOT}"}
        log = open(self.output / f"api-{label}.log", "w")
        self.api = subprocess.Popen([sys.executable, "-m", "uvicorn", "safe_harbor.api:app", "--host", "127.0.0.1", "--port", str(self.args.api_port)],
                                    cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        for _ in range(80):
            try:
                status, health = http(self.base, "/health", timeout=2)
                if status == 200:
                    return health
            except Exception:
                pass
            if self.api.poll() is not None:
                break
            time.sleep(0.25)
        raise RuntimeError(f"API ({label}) did not become healthy; see {log.name}")

    def kill_api(self) -> int:
        if self.api is None:  # attached to an API this invocation did not start: SIGKILL the port's listener
            import signal
            pid = int(subprocess.run(["lsof", "-t", f"-iTCP:{self.args.api_port}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout.split()[0])
            os.kill(pid, signal.SIGKILL)
            for _ in range(40):
                if subprocess.run(["lsof", "-t", f"-iTCP:{self.args.api_port}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout.strip() == "":
                    break
                time.sleep(0.25)
            self.args.attach = None  # the restarted API is owned (and stopped) by this invocation
            return -9
        self.api.kill()  # SIGKILL: no shutdown hook, no coordinator.stop()
        return self.api.wait(10)

    def stop_api(self):
        if self.api and self.api.poll() is None:
            self.api.terminate()
            try:
                self.api.wait(10)
            except subprocess.TimeoutExpired:
                self.api.kill()

    def stop_vite(self):
        if self.vite and self.vite.poll() is None:
            self.vite.terminate()
            try:
                self.vite.wait(10)
            except subprocess.TimeoutExpired:
                self.vite.kill()

    # ------------------------------------------------------------------ run phase
    def snapshot(self, run_id):
        return http(self.base, f"/runs/{run_id}/snapshot")[1]

    def wait_terminal(self, run_id, deadline, on_tick=None):
        while True:
            try:
                snap = self.snapshot(run_id)
            except Exception:
                time.sleep(0.5)
                continue
            if on_tick and on_tick(snap):
                continue
            if snap["run"]["status"] in TERMINAL or time.monotonic() > deadline:
                return snap
            time.sleep(0.5)

    @staticmethod
    def spend(run) -> dict:
        b = run["budget"]
        return {"tokens_used": b.get("tokens_used"), "model_calls": b.get("model_calls"), "tool_calls": b.get("tool_calls"),
                "cost_usd": b.get("cost_usd"), "uncertain_tokens": b.get("uncertain_tokens", 0), "uncertain_cost_usd": b.get("uncertain_cost_usd", 0),
                "reserved_tokens": b.get("reserved_tokens", 0)}

    def spent_so_far(self) -> float:
        return sum((a["spend"].get("cost_usd") or 0) + (a["spend"].get("uncertain_cost_usd") or 0) for a in self.report["attempts"])

    def attempt(self, index: int, attach: str | None = None) -> str | None:
        body = {"candidate_ids": CANDIDATES, "mode": "real_model",
                "budget": {"token_limit": self.args.token_limit, "tool_limit": self.args.tool_limit, "cost_limit_usd": self.args.cost_limit}}
        if attach:
            # Continue an already created canonical run (e.g. after the driver itself was interrupted).
            status, created = 201, {"run_id": attach}
            body = {"attached_to_existing_run": attach}
        else:
            status, created = http(self.base, "/runs", body)
        record = {"attempt": index, "request": body, "created_status": status, "phases": []}
        self.report["attempts"].append(record)
        if status != 201:
            record.update(outcome="not_created", detail=created, spend={})
            return None
        run_id = created["run_id"]
        record["run_id"] = run_id
        started = time.monotonic()
        crash = {"done": not self.args.crash or (bool(attach) and not self.args.crash_on_attach)}
        if attach:
            crash["note"] = "Attached after the driver was interrupted; crash injection (if any) is read from committed coordinator.recovered events."

        def maybe_crash(snap):
            if crash["done"]:
                return False
            tasks = snap["tasks"]
            running = [t for t in tasks if t["status"] == "running"]
            complete = [t for t in tasks if t["status"] == "complete"]
            if len(running) == 2 and len(complete) >= self.args.crash_after_complete:
                at_death = {"elapsed_seconds": round(time.monotonic() - started, 1), "through_sequence": snap["through_sequence"],
                            "coordinator_epoch": snap["run"].get("coordinator_epoch"),
                            "running": [{"task_id": t["task_id"], "kind": t["kind"], "attempt": t["attempt"]} for t in running],
                            "complete": len(complete), "budget": self.spend(snap["run"])}
                exit_code = self.kill_api()
                at_death["api_exit_code"] = exit_code
                restart = time.monotonic()
                self.start_api("after-sigkill")
                at_death["restart_seconds"] = round(time.monotonic() - restart, 2)
                crash.update(done=True, **at_death)
                print(f"SIGKILL at commit {at_death['through_sequence']} with 2 workers running (exit {exit_code}); restarted", flush=True)
                return True
            return False

        snap = self.wait_terminal(run_id, started + self.args.run_timeout, maybe_crash)
        run = snap["run"]
        record["phases"].append({"phase": "investigation", "status": run["status"], "stop_reason": run.get("stop_reason"),
                                 "duration_seconds": round(time.monotonic() - started, 1), "through_sequence": snap["through_sequence"],
                                 "tasks": [{"task_id": t["task_id"], "kind": t["kind"], "status": t["status"], "attempt": t["attempt"], "error": t.get("error")} for t in snap["tasks"]]})
        record["crash"] = crash if self.args.crash else "disabled"
        if run["status"] not in TERMINAL:
            record.update(outcome="still_running_at_driver_deadline", spend=self.spend(run), budget=run["budget"])
            self.report["findings"].append(f"{run_id} was still running at the driver deadline; no further attempt started while it runs.")
            self.flush()
            raise RuntimeError("canonical run still running at driver deadline; re-run with --attach")
        already_revised = any(e["cause"] == "evidence.revised" for e in http(self.base, f"/runs/{run_id}/events?after_sequence=0")[1]["events"])
        if run["status"] == "complete" and self.args.revision and not already_revised:
            rev_started = time.monotonic()
            status, result = http(self.base, f"/runs/{run_id}/evidence-revisions", {"fixture_id": "withhold-control-evidence"})
            phase = {"phase": "evidence_revision", "fixture_id": "withhold-control-evidence", "http_status": status, "result": result}
            if status == 200:
                time.sleep(1)
                snap = self.wait_terminal(run_id, rev_started + self.args.run_timeout)
                run = snap["run"]
                phase.update(status=run["status"], stop_reason=run.get("stop_reason"), duration_seconds=round(time.monotonic() - rev_started, 1),
                             through_sequence=snap["through_sequence"],
                             tasks=[{"task_id": t["task_id"], "kind": t["kind"], "status": t["status"], "attempt": t["attempt"], "error": t.get("error")} for t in snap["tasks"] if t["task_id"] in result.get("successor_task_ids", [])])
            record["phases"].append(phase)
        record.update(outcome=run["status"], stop_reason=run.get("stop_reason"), total_seconds=round(time.monotonic() - started, 1),
                      spend=self.spend(run), budget=run["budget"])
        print(f"attempt {index}: {run_id} {run['status']} cost={run['budget'].get('cost_usd')} tokens={run['budget'].get('tokens_used')}", flush=True)
        revision_ok = not self.args.revision or already_revised or any(p["phase"] == "evidence_revision" and p.get("status") == "complete" for p in record["phases"])
        self.flush()
        crash_ok = not self.args.crash or crash["done"]
        return run_id if run["status"] == "complete" and revision_ok and crash_ok else None

    # ------------------------------------------------------------------ integrity
    def verify(self, run_id: str) -> dict:
        from safe_harbor.runtime.ledger import digest
        from safe_harbor.science import run_tool
        status, export = http(self.base, f"/runs/{run_id}/export", timeout=60)
        (self.output / "export.json").write_text(json.dumps(export, indent=1))
        snap, events = export["snapshot"], export["events"]
        run, tasks, artifacts = snap["run"], snap["tasks"], snap["artifacts"]
        self.report["run_id"] = run_id
        self.report["export"] = {"path": str((self.output / "export.json").relative_to(ROOT)), "bytes": (self.output / "export.json").stat().st_size,
                                 "events": len(events), "through_sequence": export["through_sequence"]}
        self.check("export: run mode is real_model with the configured model identity", run["mode"] == "real_model" and run["model_id"] == os.getenv("MODEL_ID") and export["mode"] == "real_model",
                   {k: run.get(k) for k in ("mode", "model_id", "model_provider", "harness_hash", "data_version", "status")})
        self.check("export: events are ordered, gap-free and match the snapshot watermark",
                   [e["sequence"] for e in events] == list(range(1, len(events) + 1)) and export["through_sequence"] == len(events), {"events": len(events)})
        current = [t for t in tasks if t["status"] != "superseded"]
        self.check("export: every current task accepted", all(t["status"] == "complete" for t in current),
                   {"current": len(current), "superseded": len(tasks) - len(current), "not_complete": [(t["kind"], t["status"]) for t in current if t["status"] != "complete"]})
        self.check("export: task graph stayed within 24 nodes", len(tasks) <= 24, {"tasks": len(tasks)})
        latest = {}
        for a in snap["assessments"]:
            if a["candidate_id"] not in latest or a["assessment_revision"] > latest[a["candidate_id"]]["assessment_revision"]:
                latest[a["candidate_id"]] = a
        self.check("export: all three candidates have a committed assessment", set(latest) == set(CANDIDATES), sorted(latest))
        traces = [a for a in artifacts if a["kind"] == "worker_trace"]
        usage = [t["data"].get("usage", {}) for t in traces]
        self.check("export: worker traces carry genuine model calls with provider usage",
                   bool(usage) and all(u.get("model_calls", 0) >= 1 and u.get("tokens", 0) > 0 for u in usage),
                   {"traces": len(usage), "model_calls": sum(u.get("model_calls", 0) for u in usage), "tokens": sum(u.get("tokens", 0) for u in usage)})
        # Crash recovery inside the canonical record
        recovered = [e for e in events if e["cause"] == "coordinator.recovered"]
        epochs = [e["upserts"].get("runs", [{}])[0].get("coordinator_epoch") for e in recovered]
        post_crash = [e for e in recovered if (e["upserts"].get("runs", [{}])[0].get("coordinator_epoch") or 0) >= 2]
        # Interrupted work is read from the committed recovery event itself, not from this script's memory.
        interrupted = sorted({t["task_id"] for e in post_crash for t in e["upserts"].get("tasks", [])})
        final_attempts = {t["task_id"]: t["attempt"] for t in tasks}
        self.check("recovery: SIGKILL mid-flight was followed by a coordinator.recovered event at a new epoch and the interrupted tasks completed",
                   bool(post_crash) and bool(interrupted) and all(final_attempts.get(t, 0) >= 2 and next(x for x in tasks if x["task_id"] == t)["status"] in ("complete", "superseded") for t in interrupted),
                   {"recovered_events": [{"sequence": e["sequence"], "epoch": ep} for e, ep in zip(recovered, epochs)], "interrupted": interrupted,
                    "interrupted_final_attempts": {t: final_attempts.get(t) for t in interrupted}, "uncertain_tokens": run["budget"].get("uncertain_tokens"),
                    "uncertain_cost_usd": run["budget"].get("uncertain_cost_usd")})
        # Evidence revision inside the canonical record
        revised = [e for e in events if e["cause"] == "evidence.revised"]
        rev_seq = revised[0]["sequence"] if revised else None
        reopened = [t for t in tasks if t.get("supersedes_task_id")]
        cand0 = CANDIDATES[0]
        cand0_revisions = sorted({a["assessment_revision"] for e in events for a in e["upserts"].get("assessments", []) if a["candidate_id"] == cand0})
        after = [a for e in events if rev_seq and e["sequence"] > rev_seq for a in e["upserts"].get("assessments", []) if a["candidate_id"] == cand0]
        if not revised and not self.args.revision:
            self.report["findings"].append("No evidence revision was applied to this canonical run (--no-revision); the revision beat is evidenced separately (see revision_run).")
        else:
          self.check("revision: prepared withhold-control-evidence reopened only dependent tasks and the real model committed a new current assessment",
                   bool(revised) and bool(reopened) and all(t["candidate_id"] in (cand0, None) for t in reopened) and bool(after) and latest.get(cand0, {}).get("freshness") == "current"
                   and not run["evidence_availability"][cand0]["control_evidence"],
                   {"evidence_revised_sequence": rev_seq, "reopened": [(t["kind"], t["status"], t.get("candidate_id")) for t in reopened],
                    "candidate0_assessment_revisions": cand0_revisions, "candidate0_latest": {k: latest.get(cand0, {}).get(k) for k in ("assessment_revision", "screen_status", "evidence_status", "freshness")}})
        # Scientific text boundaries
        texts = [a.get("conclusion", "") for a in latest.values()]
        self.check("text: no global safe label in any accepted conclusion", not any(SAFE_LABEL.search(t) for t in texts), [m.group(0) for t in texts for m in SAFE_LABEL.finditer(t)])
        envelopes = [a["candidate_id"] for a in latest.values() if a.get("conclusion", "").lstrip().startswith(("{", "```"))]
        self.check("text: accepted conclusions are prose, not raw model JSON envelopes", not envelopes, {"raw_envelope_candidates": envelopes})
        self.check("assessments: independent axes and incomplete when required evidence is missing",
                   all(a["screen_status"] in ("pass", "fail", "incomplete") and a["evidence_status"] in ("supported_for_endpoint", "conflicting", "unknown")
                       and (a["screen_status"] != "pass" or all(r["status"] == "pass" for r in a["criterion_results"])) for a in latest.values()),
                   {c: {k: a[k] for k in ("screen_status", "evidence_status", "freshness", "assessment_revision")} for c, a in latest.items()})
        # Independent recomputation of every model-requested scientific tool call
        mismatched, total = [], 0
        for trace in traces:
            candidate = trace["data"].get("candidate_id") or next((t["candidate_id"] for t in tasks if t["task_id"] == trace["provenance"].get("task_id")), None)
            for call in trace["data"].get("tool_calls", []):
                if call["tool_name"] == "retrieve_evidence" or "calculation" not in call.get("result", {}):
                    continue
                total += 1
                fresh = run_tool(call["tool_name"], candidate, call["arguments"])
                if digest(fresh["calculation"]) != digest(call["result"]["calculation"]):
                    mismatched.append({"tool": call["tool_name"], "candidate": candidate, "arguments": call["arguments"]})
        self.check("recompute: every model-requested scientific tool result recomputes identically from source", total > 0 and not mismatched, {"recomputed": total, "mismatched": mismatched})
        self.report["run"] = {"run_id": run_id, "status": run["status"], "mode": run["mode"], "model_id": run["model_id"], "harness_hash": run["harness_hash"],
                              "budget": run["budget"], "evidence_availability": run["evidence_availability"], "tasks": len(tasks),
                              "latest_assessments": {c: {k: a[k] for k in ("assessment_id", "assessment_revision", "screen_status", "evidence_status", "freshness")} | {"conclusion": a["conclusion"]} for c, a in latest.items()}}
        return export

    def revision_run(self, run_id: str):
        """Record, without re-running anything, what a separate real run's evidence revision actually did."""
        status, export = http(self.base, f"/runs/{run_id}/export", timeout=60)
        path = self.output / "revision-run-export.json"
        path.write_text(json.dumps(export, indent=1))
        events, snap = export["events"], export["snapshot"]
        rev = next((e for e in events if e["cause"] == "evidence.revised"), None)
        post = [e for e in events if rev and e["sequence"] > rev["sequence"]]
        facts = {
            "run_id": run_id, "mode": snap["run"]["mode"], "status": snap["run"]["status"], "stop_reason": snap["run"].get("stop_reason"),
            "events": len(events), "export_bytes": path.stat().st_size, "budget": snap["run"]["budget"],
            "evidence_revised_sequence": rev and rev["sequence"],
            "revision_artifact": rev and next((a["data"] for a in rev["upserts"].get("artifacts", []) if a["kind"] == "evidence_revision"), None),
            "stale_assessments_at_revision": rev and [{k: a[k] for k in ("candidate_id", "assessment_revision", "freshness")} for a in rev["upserts"].get("assessments", [])],
            "reopened_successors": [{k: t.get(k) for k in ("task_id", "kind", "status", "attempt", "error", "supersedes_task_id")} for t in snap["tasks"] if t.get("supersedes_task_id")],
            "unaffected_other_candidates_complete": all(t["status"] == "complete" for t in snap["tasks"] if t.get("candidate_id") not in (CANDIDATES[0], None)),
            "post_revision_causes": [e["cause"] for e in post],
            "new_assessment_after_revision": any(e["upserts"].get("assessments") for e in post if e["cause"] != "evidence.revised"),
        }
        self.report["revision_run"] = facts
        self.check("revision run: evidence.revised committed, only candidate-0 tasks reopened and its prior assessment marked stale",
                   bool(rev) and bool(facts["reopened_successors"]) and all(CANDIDATES[0] in t["task_id"] for t in facts["reopened_successors"])
                   and any(a["freshness"] == "stale" for a in facts["stale_assessments_at_revision"] or []) and facts["unaffected_other_candidates_complete"],
                   {k: facts[k] for k in ("evidence_revised_sequence", "stale_assessments_at_revision", "unaffected_other_candidates_complete")})
        failed = [t for t in facts["reopened_successors"] if t["status"] == "failed"]
        if failed or not facts["new_assessment_after_revision"]:
            self.report["findings"].append(f"Revision run {run_id} ended '{facts['status']}': reopened tasks failed {[(t['kind'], t['error']) for t in failed]}; no post-revision assessment was committed. Reported as not demonstrated, not substituted.")

    # ------------------------------------------------------------------ presentation
    def beats(self, export: dict) -> dict:
        """Sequence spans in the recorded run for each outline beat, derived only from committed events."""
        events = export["events"]
        n = len(events)

        def first(pred):
            return next((e["sequence"] for e in events if pred(e)), None)
        tool = lambda e, names: any(a["kind"] == "scientific_tool_result" and a["data"].get("tool_name") in names for a in e["upserts"].get("artifacts", []))
        seq_bases = first(lambda e: tool(e, {"reference_sequence"}))
        seq_locus = first(lambda e: tool(e, {"inspect_candidate", "screen_candidate", "gene_proximity", "control_overlap", "list_evidence"}))
        seq_expr = first(lambda e: tool(e, {"expression_comparison", "control_overlap", "differential_expression"}))
        seq_assess = first(lambda e: bool(e["upserts"].get("assessments")))
        post_crash = [e["sequence"] for e in events if e["cause"] == "coordinator.recovered" and (e["upserts"].get("runs", [{}])[0].get("coordinator_epoch") or 0) >= 2]
        seq_rev = first(lambda e: e["cause"] == "evidence.revised")
        seq_rev_assess = first(lambda e: seq_rev and e["sequence"] > seq_rev and any(a["candidate_id"] == CANDIDATES[0] for a in e["upserts"].get("assessments", [])))
        return {"events": n, "genome_first_locus_result": seq_locus, "genome_first_reference_bases": seq_bases, "first_expression_result": seq_expr,
                "first_assessment": seq_assess, "post_crash_recovery": post_crash[0] if post_crash else None, "evidence_revised": seq_rev,
                "revised_assessment": seq_rev_assess, "last": n}

    def present(self, run_id: str, export: dict):
        env = {**os.environ, "API_TARGET": self.base}
        log = open(self.output / "vite.log", "w")
        self.vite = subprocess.Popen(["npx", "vite", "--host", "127.0.0.1", "--port", str(self.args.ui_port), "--strictPort"], cwd=ROOT / "frontend", env=env, stdout=log, stderr=subprocess.STDOUT)
        for _ in range(80):
            try:
                urllib.request.urlopen(self.ui, timeout=2)
                break
            except Exception:
                time.sleep(0.25)
        beats = self.beats(export)
        latest = self.report["run"]["latest_assessments"]
        names = {c["candidate_id"]: c["name"] for c in export["snapshot"]["candidates"]}
        config = {"ui": self.ui, "run_id": run_id, "output": str(self.output), "speed": self.args.speed, "beats": beats,
                  "measure_1x": self.args.measure_1x, "candidate0": CANDIDATES[0], "names": names,
                  "latest": {c: {"conclusion": a["conclusion"], "revision": a["assessment_revision"]} for c, a in latest.items()}}
        started = time.monotonic()
        result = subprocess.run(["node", "--input-type=module"], input=BROWSER_JS.replace("__PLAYWRIGHT__", str(ROOT / "frontend/node_modules/playwright/index.mjs")),
                                capture_output=True, text=True, timeout=900, env={**os.environ, "DEMO_CONFIG": json.dumps(config)})
        (self.output / "browser.log").write_text(result.stdout[-20000:] + "\n--- stderr ---\n" + result.stderr[-20000:])
        try:
            observed = json.loads(result.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            observed = {"checks": [], "error": (result.stdout + result.stderr)[-3000:]}
        for c in observed.get("checks", []):
            self.check("browser: " + c["check"], c["passed"], c.get("evidence"))
        if observed.get("error"):
            self.check("browser journey completed", False, observed["error"])
        cues = observed.pop("cues", [])
        (self.output / "cues.json").write_text(json.dumps({"run_id": run_id, "derived_by": "frontend/src/safe-harbor/cues.ts deriveCues() executed in the browser on GET /runs/{id}/export events",
                                                           "count": len(cues), "cues": cues}, indent=1))
        observed["browser_phase_seconds"] = round(time.monotonic() - started, 1)
        self.report["presentation"] = observed
        self.report["beats"] = beats
        self.report["timing"] = self.timing(export, beats, observed, cues)

    def timing(self, export, beats, observed, cues) -> dict:
        from datetime import datetime
        events = export["events"]
        t0 = datetime.fromisoformat(events[0]["occurred_at"].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(events[-1]["occurred_at"].replace("Z", "+00:00"))
        n, speed = beats["events"], self.args.speed
        spans = {
            "context": (0, 1), "genome_zoom": (1, beats["genome_first_reference_bases"] or beats["genome_first_locus_result"]),
            "expression_investigation": (beats["genome_first_reference_bases"] or 1, beats["first_assessment"]),
            "recovery": (beats["post_crash_recovery"], beats["post_crash_recovery"]),
            "evidence_revision": (beats["evidence_revised"], beats["revised_assessment"]),
            "structural_patch_and_promotion": (None, None), "versioned_dossier": (n, n),
        }
        rows = []
        for beat, target in OUTLINE:
            a, b = spans[beat]
            backed = a is not None and b is not None
            rows.append({"beat": beat, "target_seconds": target, "backed_by_recorded_events": backed, "commit_span": [a, b] if backed else None,
                         "replay_seconds_at_1x": (b - a) if backed else None, f"replay_seconds_at_{speed}x": round((b - a) / speed, 1) if backed else None,
                         "cues_in_span": sum(1 for c in cues if backed and a <= c["sequence"] <= b)})
        return {"recorded_run_wall_seconds_first_to_last_event": round((t1 - t0).total_seconds(), 1), "events": n,
                "replay_full_measured_seconds": observed.get("replay_measurements", {}), "outline": rows,
                "outline_target_total_seconds": sum(t for _, t in OUTLINE)}

    # ------------------------------------------------------------------ main
    def run(self):
        try:
            health = self.start_api("initial")
            self.check("api healthy: MongoDB authority and model configured", health["authoritative_store"] == "MongoDB" and health["model_available"],
                       {k: health[k] for k in ("database", "authoritative_store", "model_available", "coordinator_available")})
            run_id = self.args.present_only
            if not run_id:
                if self.args.attach:
                    self.report["attempts"].extend(self.args.prior_attempts)
                for index in range(1, self.args.attempts + 1):
                    if self.spent_so_far() >= self.args.spend_cap:
                        self.report["findings"].append(f"Stopped before attempt {index}: cumulative known+uncertain spend {self.spent_so_far():.4f} USD reached the cap.")
                        break
                    run_id = self.attempt(index, self.args.attach if index == 1 else None)
                    if run_id:
                        break
                self.check("a complete real-model canonical run (with recovery and revision beats) was produced within the attempt limit", bool(run_id),
                           [{"run_id": a.get("run_id"), "outcome": a.get("outcome"), "cost_usd": a["spend"].get("cost_usd")} for a in self.report["attempts"]])
                self.report["total_spend"] = {"known_cost_usd": round(sum(a["spend"].get("cost_usd") or 0 for a in self.report["attempts"]), 6),
                                              "uncertain_cost_usd": round(sum(a["spend"].get("uncertain_cost_usd") or 0 for a in self.report["attempts"]), 6),
                                              "tokens": sum(a["spend"].get("tokens_used") or 0 for a in self.report["attempts"])}
            if run_id:
                export = self.verify(run_id)
                if self.args.revision_run:
                    self.revision_run(self.args.revision_run)
                self.present(run_id, export)
        except Exception as exc:  # recorded, never converted into a pass
            self.check("demo executed without exception", False, repr(exc))
        finally:
            self.stop_vite()
            self.stop_api()
            self.report["finished_at"] = now()
            self.report["passed"] = bool(self.checks) and all(c["passed"] for c in self.checks)
            (self.output / "report.json").write_text(json.dumps(self.report, indent=1))
            print(json.dumps({"passed": self.report["passed"], "report": str(self.output / "report.json")}))
        return 0 if self.report["passed"] else 1


BROWSER_JS = r"""
import { chromium } from '__PLAYWRIGHT__';
const cfg = JSON.parse(process.env.DEMO_CONFIG);
const checks = [], shots = [], cueSeen = new Map(), writes = [], errors = [];
const check = (name, passed, evidence) => checks.push({ check: name, passed: Boolean(passed), evidence });
const norm = t => (t ?? '').replace(/\s+/g, ' ').trim();
const out = { checks, screenshots: shots, replay_measurements: {} };
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });  // fresh client: no storage
const page = await context.newPage();
page.on('pageerror', e => errors.push(e.message));
page.on('request', r => { if (!['GET', 'HEAD'].includes(r.method())) writes.push(r.method() + ' ' + r.url()); });
const N = cfg.beats.events;
const where = async () => norm(await page.locator('.shp-where').textContent());
const commitNow = async () => Number(((await where()).match(/commit (\d+)/) ?? [])[1] ?? -1);
async function shot(name) { const path = `${cfg.output}/${name}.png`; await page.screenshot({ path }); shots.push(name + '.png'); }
async function playToEnd(speed, sample) {
  await page.getByRole('combobox', { name: 'Replay speed' }).selectOption(String(speed));
  const t0 = Date.now();
  await page.getByRole('button', { name: 'Play presentation replay' }).click();
  while (true) {
    const c = await commitNow();
    if (sample) { const cue = norm(await page.locator('.shp-cue').textContent()); const m = cue.match(/cue keyed to commit (\d+)/); if (m && !cueSeen.has(cue)) cueSeen.set(cue, Number(m[1])); }
    if (c >= N && await page.getByRole('button', { name: 'Play presentation replay' }).count()) break;
    if (Date.now() - t0 > (N / speed + 60) * 1000) throw new Error(`replay at ${speed}x did not finish (commit ${c})`);
    await page.waitForTimeout(100);
  }
  return (Date.now() - t0) / 1000;
}
try {
  const t0 = Date.now();
  await page.goto(`${cfg.ui}/?run=${encodeURIComponent(cfg.run_id)}`);
  await page.locator('.mode-word').getByText('REAL MODEL', { exact: true }).waitFor({ timeout: 30000 });
  await page.getByRole('button', { name: 'Presentation', exact: true }).click();
  await page.waitForFunction(n => (document.querySelector('.shp-where')?.textContent ?? '').includes(`/ ${n}`), N, { timeout: 30000 });
  await page.locator('.shp-preload.ready').waitFor({ timeout: 60000 });
  out.fresh_client_ready_seconds = (Date.now() - t0) / 1000;
  const preload = norm(await page.locator('.shp-preload').textContent());
  check('fresh client opens ?run=<id> in presentation mode and preloads every committed event', preload.includes(`${N} events`), { preload, ready_seconds: out.fresh_client_ready_seconds });
  const modeBar = norm(await page.locator('.shp-mode').textContent());
  check('live view is labeled LIVE and REAL MODEL', modeBar.includes('LIVE') && modeBar.includes('REAL MODEL'), { modeBar });

  // Camera cues: the UI's own deriveCues() applied to the exported committed events.
  const cues = await page.evaluate(async id => {
    const m = await import('/src/safe-harbor/cues.ts');
    const ex = await (await fetch(`/api/runs/${encodeURIComponent(id)}/export`)).json();
    return m.deriveCues(ex.events).map(c => ({ sequence: c.sequence, step: c.step, label: c.label, cause: c.cause, source: c.source, event_id: c.event_id, target: c.target }));
  }, cfg.run_id);
  out.cues = cues;
  const steps = [...new Set(cues.map(c => c.step))];
  check('camera cues derived from actual events cover overview, genome zoom, bases, results and graph branches',
    ['overview', 'focus_chromosome', 'zoom_locus', 'show_bases', 'highlight_result', 'reveal_branch'].every(s => steps.includes(s)) && cues.every(c => c.sequence >= 1 && c.sequence <= N && c.source === 'derived'),
    { cues: cues.length, steps, server_cues: cues.filter(c => c.source === 'server').length });
  check('an evidence-revision cue reveals the reopened branch', !cfg.beats.evidence_revised || cues.some(c => c.sequence === cfg.beats.evidence_revised && c.step === 'reveal_branch'), cues.filter(c => c.sequence === cfg.beats.evidence_revised));

  // Final dossier agrees with the export.
  await page.getByRole('button', { name: 'Dossier', exact: true }).click();
  const dossier = page.getByRole('dialog', { name: /Run run-/ });
  await dossier.locator('.shp-checks li').first().waitFor();
  const ok = await dossier.locator('.shp-checks li.ok').count(), bad = await dossier.locator('.shp-checks li.bad').count();
  const articles = await dossier.locator('.shp-assessments article').allTextContents();
  const conclusionsMatch = Object.values(cfg.latest).every(a => articles.some(t => norm(t).includes(norm(a.conclusion))));
  check('dossier: screen agreement all ✓ and latest assessment per candidate equals the export', bad === 0 && ok >= 4 && articles.length === Object.keys(cfg.latest).length && conclusionsMatch,
    { ok, bad, articles: articles.length, conclusions_match_export: conclusionsMatch, facts: norm(await dossier.locator('.shp-facts').textContent()) });
  await shot('09-final-dossier');
  await dossier.getByRole('button', { name: 'Close dossier', exact: true }).last().click();

  // Reset to start: commit 0, recorded replay, REAL MODEL label, nothing from the future.
  await page.getByRole('button', { name: 'Reset presentation to start' }).click();
  await page.waitForFunction(() => /commit 0 \//.test(document.querySelector('.shp-where')?.textContent ?? ''));
  const bar0 = norm(await page.locator('.shp-mode').textContent());
  const conclusion0 = norm(await page.locator('.conclusion-text').textContent());
  check('reset-to-start: commit 0 labeled RECORDED REPLAY + REAL MODEL, no assessment or dossier leaks',
    bar0.includes('RECORDED REPLAY') && bar0.includes('REAL MODEL') && !Object.values(cfg.latest).some(a => conclusion0 === norm(a.conclusion))
      && await page.getByRole('button', { name: 'Dossier at this commit', exact: true }).isDisabled() && await page.locator('.task-failure').count() === 0,
    { bar0, conclusion0 });
  await shot('00-reset-commit-0');

  // Full story at the chosen speed, sampling the camera cues the viewer actually sees.
  out.replay_measurements[`${cfg.speed}x_seconds`] = await playToEnd(cfg.speed, true);
  const barEnd = norm(await page.locator('.shp-mode').textContent());
  check(`full replay at ${cfg.speed}× played commit 0 → ${N} with RECORDED REPLAY + REAL MODEL labels`, (await commitNow()) === N && barEnd.includes('RECORDED REPLAY') && barEnd.includes('REAL MODEL'),
    { seconds: out.replay_measurements[`${cfg.speed}x_seconds`], barEnd });
  out.cues_observed_during_playback = [...cueSeen.entries()].map(([text, sequence]) => ({ sequence, text }));
  check('camera cues were shown during playback, each keyed to a real derived cue sequence', cueSeen.size > 0 && [...cueSeen.values()].every(s => cues.some(c => c.sequence === s)), { observed: cueSeen.size, derived: cues.length });
  const selected = norm(await page.locator('.conclusion-panel h2').textContent());
  const selectedId = Object.entries(cfg.names).find(([, n]) => n === selected)?.[0];
  const endConclusion = norm(await page.locator('.conclusion-text').textContent());
  check('at the last commit the displayed conclusion equals the exported latest assessment for the selected candidate', selectedId && endConclusion === norm(cfg.latest[selectedId].conclusion), { selected, selectedId });

  // Beat stills (seek with follow camera on) and historical correctness around the revision.
  const slider = page.getByRole('slider', { name: 'Replay event position' });
  const seek = async n => { await slider.fill(String(n)); await page.waitForTimeout(700); };
  const b = cfg.beats;
  const stills = [['01-context', 1], ['02-genome-locus', b.genome_first_locus_result], ['03-reference-bases', b.genome_first_reference_bases], ['04-expression-result', b.first_expression_result],
    ['05-first-assessment', b.first_assessment], ['06-crash-recovered', b.post_crash_recovery], ['07-evidence-revised', b.evidence_revised], ['08-revised-assessment', b.revised_assessment]];
  for (const [name, n] of stills) if (n) { await seek(n); await shot(name); }
  if (b.first_assessment > 1) { await seek(b.first_assessment - 1); const pill = norm(await page.locator('.conclusion-panel .panel-head .pill').textContent()); check('no assessment appears before the first committed assessment', pill === 'Unresolved', { at: b.first_assessment - 1, pill }); }
  if (b.evidence_revised && b.revised_assessment) {
    await page.getByRole('checkbox', { name: 'Follow camera' }).uncheck();
    await seek(b.evidence_revised);
    await page.locator('.candidate-card', { hasText: cfg.names[cfg.candidate0] }).first().click();
    const stale = norm(await page.locator('.status-axes').textContent()), pillBefore = norm(await page.locator('.conclusion-panel .panel-head .pill').textContent());
    await seek(b.revised_assessment);
    const pillAfter = norm(await page.locator('.conclusion-panel .panel-head .pill').textContent()), fresh = norm(await page.locator('.status-axes').textContent());
    check('revision beat: prior assessment is shown stale at the revision commit, the new revision appears only at its own commit', /stale/.test(stale) && pillBefore !== pillAfter && /current/.test(fresh),
      { at_revision: { pill: pillBefore, axes: stale }, at_revised_assessment: { pill: pillAfter, axes: fresh } });
    await page.getByRole('checkbox', { name: 'Follow camera' }).check();
  }
  // Rehearse again from a reset, at 1x, to measure the unhurried duration.
  await page.getByRole('button', { name: 'Reset presentation to start' }).click();
  await page.waitForFunction(() => /commit 0 \//.test(document.querySelector('.shp-where')?.textContent ?? ''));
  check('second reset-to-start returns to commit 0', (await commitNow()) === 0, await where());
  if (cfg.measure_1x) out.replay_measurements['1x_seconds'] = await playToEnd(1, false);
  check('presentation made no ledger writes (GET/HEAD only)', writes.length === 0, writes);
  check('no page errors', errors.length === 0, errors);
} catch (error) {
  out.error = String(error && error.stack || error);
  try { await shot('zz-error'); } catch {}
} finally { await browser.close(); }
console.log(JSON.stringify(out));
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--token-limit", type=int, default=1_000_000, help="Explicit, reported run token budget for three candidates plus one revision round")
    parser.add_argument("--tool-limit", type=int, default=120)
    parser.add_argument("--cost-limit", type=float, default=0.6, help="Per-run USD limit frozen into the run")
    parser.add_argument("--spend-cap", type=float, default=0.8, help="Stop starting new attempts once known+uncertain spend reaches this")
    parser.add_argument("--run-timeout", type=int, default=3600)
    parser.add_argument("--attach", metavar="RUN_ID", help="Continue an existing canonical run in --database (no new run is created for attempt 1)")
    parser.add_argument("--revision-run", metavar="RUN_ID", help="A separate run in --database whose recorded evidence revision is exported and reported")
    parser.add_argument("--crash-on-attach", action="store_true", help="Inject the SIGKILL into an attached run that has not crashed yet")
    parser.add_argument("--prior-attempts", type=json.loads, default=[], help="JSON list of earlier attempt records to carry into the report")
    parser.add_argument("--crash-after-complete", type=int, default=3)
    parser.add_argument("--no-crash", dest="crash", action="store_false")
    parser.add_argument("--no-revision", dest="revision", action="store_false")
    parser.add_argument("--speed", type=float, default=2)
    parser.add_argument("--no-1x", dest="measure_1x", action="store_false")
    parser.add_argument("--present-only", metavar="RUN_ID")
    parser.add_argument("--database")
    parser.add_argument("--api-port", type=int, default=8060)
    parser.add_argument("--ui-port", type=int, default=5200)
    args = parser.parse_args()
    if (args.present_only or args.attach) and not args.database:
        sys.exit("--present-only/--attach require --database")
    if not args.present_only and not (os.getenv("OPENROUTER_API_KEY") and os.getenv("MODEL_ID")):
        sys.exit("OPENROUTER_API_KEY and MODEL_ID must be configured in the ignored .env file")
    sys.exit(Demo(args).run())


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""SH-Q06 E2E: answer-key, tool-access and artifact-manifest isolation.

Run from the repository root against a transaction-capable MongoDB:
  PYTHONPATH=backend:. .venv/bin/python e2e/safe_harbor/isolation.py

Mode: deterministic_operational. No model is called; the scored worker path is
the actual runtime (coordinator -> execute_worker -> execute_tool -> run_tool)
executing the frozen baseline harness through a real uvicorn API process with
an isolated MongoDB database. Every attempt records expected versus observed
outcome and the code boundary it relies on. An attempt passes only when the
code raises/refuses (or the endpoint returns 404); prompt wording is never
counted as a boundary. Exit status is nonzero if any attempt fails.
"""
from __future__ import annotations

import argparse
import ast
import copy
import json
import os
import re
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from safe_harbor import science
from safe_harbor.harness import get_harness, validate_harness
from safe_harbor.harness.specification import canonical_hash
from safe_harbor.runtime.compiler import APPROVED_TOOLS, compile_harness
from safe_harbor.runtime.ledger import Ledger, now
from safe_harbor.runtime.worker import TOOL_SCOPES, build_context_packet, execute_tool
from safe_harbor.science import catalog as science_catalog
from safe_harbor.science import tools as science_tools

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "backend" / "safe_harbor"
EVALUATOR = ROOT / "data" / "safe_harbor" / "evaluator"
REFERENCE_PATH = "data/safe_harbor/evaluator/reference_answers.json"
SPLITS_PATH = "data/safe_harbor/evaluator/splits.json"

# Names that must never resolve to a worker tool: evaluator functions, file/URL
# readers, dotted/path-like/injection-shaped names and near-miss spellings.
UNAPPROVED_NAMES = [
    "reference_answers", "load_reference", "recompute", "load_cases", "freeze", "evaluate", "score",
    "read_file", "fetch_url", "shell", "python", "run_tool", "tool_definitions", "assessment_facts", "get_catalog",
    "safe_harbor.evaluation.reference_answers.load_reference", "evaluation.cases.load_cases",
    "../evaluator/reference_answers", REFERENCE_PATH, "/" + SPLITS_PATH, "file://" + str(EVALUATOR / "splits.json"),
    "inspect_candidate; cat " + REFERENCE_PATH, "inspect_candidate/../reference_answers", "inspect_candidate\x00reference_answers",
    "__import__", "INSPECT_CANDIDATE", "inspect_candidate ", " screen_candidate", "",
]
RESOURCE_ARGUMENTS = ("url", "path", "file", "artifact_id", "candidate_id", "run_id")
# Keys/labels that exist only in evaluator records (verified absent from
# science/runtime/harness/api/shared sources and normalized data at authoring time).
EVALUATOR_ONLY_KEYS = (
    "required_numbers", "independent_diagnostics", "reference_method", "review_status", "human_reviewed",
    "split_hash", "promotion_rule", "rubric_notes", "required_decisions", "required_limitations",
    "unavailable_numbers", "exclusion_decision", "not_justified_by_available_evidence",
)
EXPECTED_PACKET_KEYS = {
    "objective", "question", "candidate", "assembly", "cell_context", "data_version", "criteria", "input_read_set",
    "evidence", "omitted_artifact_ids", "allowed_tools", "context_policy", "harness_hash", "context_selection_trace",
    "remaining_budget", "evidence_availability", "limitations",
}
TRAVERSAL_ARTIFACT_IDS = [
    "..%2F..%2F..%2F" + urllib.parse.quote(REFERENCE_PATH, safe=""),
    "../../catalog", "..%2F..%2Fexport", "%2E%2E%2F%2E%2E%2Fcatalog",
    urllib.parse.quote("{\"$ne\":null}", safe=""), urllib.parse.quote(".*", safe=""),
    "reference_answers", "reference_answers.json", "splits", urllib.parse.quote(SPLITS_PATH, safe=""),
]


def serialize(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def preview(value, limit: int = 400) -> str:
    return serialize(value)[:limit]


class Isolation:
    def __init__(self, port: int, output: Path, timeout: float):
        self.port = port
        self.base = f"http://127.0.0.1:{port}"
        self.output = output
        self.output.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.database = f"safe_harbor_isolation_{int(time.time())}"
        self.ledger = Ledger(database=self.database)
        self.ledger.initialize()
        self.process = None
        self.log = None
        self.processes = []
        self.attempts = []
        self.surfaces = {}
        self.runs = {}
        self.catalog = science.get_catalog()
        self.candidate_ids = [candidate["candidate_id"] for candidate in self.catalog["candidates"]]
        self.report = {
            "ticket": "SH-Q06", "started_at": now(), "database": self.database,
            "mode": "deterministic_operational", "harness": "frozen baseline H0 via safe_harbor.harness.get_harness(None)",
            "model_calls_made_by_this_script": 0, "processes": self.processes, "attempts": self.attempts,
            "findings": [], "limitations": [],
        }

    # ----------------------------------------------------------------- recording
    def record(self, attempt_id, category, interface, boundary, expected, observed, passed):
        self.attempts.append({"attempt_id": attempt_id, "category": category, "interface": interface,
                              "boundary": boundary, "expected": expected, "observed": observed, "passed": bool(passed)})
        return passed

    def deny(self, attempt_id, category, interface, boundary, call, errors, code=None):
        expected = {"outcome": "denied", "exception": list(errors), "code": code}
        try:
            value = call()
        except Exception as exc:  # noqa: BLE001 - the exception type is the recorded observation
            observed = {"outcome": "denied", "exception": type(exc).__name__, "code": getattr(exc, "code", None), "message": str(exc)[:400]}
            passed = observed["exception"] in errors and (code is None or observed["code"] == code)
        else:
            observed = {"outcome": "allowed", "result_preview": preview(value)}
            passed = False
        return self.record(attempt_id, category, interface, boundary, expected, observed, passed)

    def check(self, attempt_id, category, interface, boundary, expected, call):
        """call() returns (passed, observed)."""
        try:
            passed, observed = call()
        except Exception as exc:  # noqa: BLE001 - any error is recorded as a failed attempt
            passed, observed = False, {"outcome": "error", "exception": type(exc).__name__, "message": str(exc)[:400], "traceback": traceback.format_exc()[-1500:]}
        return self.record(attempt_id, category, interface, boundary, expected, observed, passed)

    def section(self, name, function):
        try:
            function()
        except Exception as exc:  # noqa: BLE001 - a broken section is recorded as a failure, later sections still run
            self.record(f"section-error:{name}", "journey", name, "journey must execute to produce evidence", "section completes",
                        {"outcome": "error", "exception": type(exc).__name__, "message": str(exc)[:400], "traceback": traceback.format_exc()[-2000:]}, False)

    # ------------------------------------------------------------------ process
    def http(self, method: str, path: str, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base + path, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as exc:
            status, raw = exc.code, exc.read()
        text = raw.decode("utf-8", "replace")
        try:
            parsed = json.loads(text)
        except ValueError:
            parsed = text
        return status, parsed, text

    def start(self):
        env = dict(os.environ, PYTHONPATH=f"{ROOT / 'backend'}:{ROOT}", MONGODB_DATABASE=self.database)
        for key in list(env):
            if key.startswith(("SAFE_HARBOR_CRASH_", "SAFE_HARBOR_OPERATIONAL_")):
                env.pop(key)
        path = self.output / f"process-{len(self.processes) + 1}.log"
        self.log = path.open("w")
        self.process = subprocess.Popen([sys.executable, "-m", "uvicorn", "safe_harbor.api:app", "--host", "127.0.0.1", "--port", str(self.port)],
                                        cwd=ROOT, env=env, stdout=self.log, stderr=subprocess.STDOUT)
        self.processes.append({"pid": self.process.pid, "log": str(path), "started_at": now()})
        until = time.monotonic() + 25
        while time.monotonic() < until:
            if self.process.poll() is not None:
                raise AssertionError(f"API process exited {self.process.returncode}; inspect {path}")
            try:
                status, body, _ = self.http("GET", "/health")
                if status == 200 and body.get("database") == self.database:
                    if not body.get("coordinator_available"):
                        raise AssertionError("API started without a coordinator; the scored worker cannot run")
                    return
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(0.1)
        raise AssertionError("API did not start")

    def stop(self):
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=10)
            self.processes[-1]["exit_code"] = self.process.returncode
            self.processes[-1]["ended_at"] = now()
        if self.log:
            self.log.close()
        self.process = None
        self.log = None

    def wait_run(self, run_id: str) -> dict:
        until = time.monotonic() + self.timeout
        while time.monotonic() < until:
            status, snapshot, text = self.http("GET", f"/runs/{run_id}/snapshot")
            if status != 200:
                raise AssertionError(f"Snapshot {run_id} returned {status}: {text[:300]}")
            if snapshot["run"]["status"] == "complete":
                return snapshot
            if snapshot["run"]["status"] in ("blocked", "budget_exhausted", "failed"):
                raise AssertionError(f"Run {run_id} stopped as {snapshot['run']['status']}: {snapshot['run'].get('stop_reason')}")
            time.sleep(0.2)
        raise AssertionError(f"Run did not complete within {self.timeout}s: {run_id}")

    # --------------------------------------------------------- 1. static checks
    def static_boundaries(self):
        offenders = []
        needles = ("safe_harbor.evaluation", "safe_harbor/evaluator", "reference_answers.json", "splits.json")
        files = sorted(path for lane in ("runtime", "science", "harness") for path in (PACKAGE / lane).glob("*.py")) + [PACKAGE / "api.py"]
        for path in files:
            package = "safe_harbor" if path.parent == PACKAGE else f"safe_harbor.{path.parent.name}"
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    base = package.split(".")
                    if node.level:
                        base = base[:len(base) - (node.level - 1)]
                        prefix = ".".join(base + ([node.module] if node.module else []))
                    else:
                        prefix = node.module or ""
                    modules = [prefix] + [f"{prefix}.{alias.name}" for alias in node.names]
                elif isinstance(node, ast.Constant) and isinstance(node.value, str) and path.name != "api.py" and any(needle in node.value for needle in needles):
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} string {node.value[:80]!r}")
                # api.py imports the evaluation package only for POST /experiments (not a worker interface).
                offenders += [f"{path.relative_to(ROOT)}:{node.lineno} imports {module}" for module in modules
                              if path.name != "api.py" and (module == "safe_harbor.evaluation" or module.startswith("safe_harbor.evaluation."))]
        self.record("static-no-evaluator-imports", "evaluator_data", "worker/science/harness source code",
                    "No runtime, science or harness module imports safe_harbor.evaluation or names evaluator files",
                    {"offenders": []}, {"files_scanned": [str(path.relative_to(ROOT)) for path in files], "offenders": offenders}, not offenders)
        sets = {"science.APPROVED_TOOL_NAMES": sorted(science.APPROVED_TOOL_NAMES), "compiler.APPROVED_TOOLS": sorted(APPROVED_TOOLS),
                "worker.TOOL_SCOPES": sorted(TOOL_SCOPES), "tools.ARGUMENT_MODELS": sorted(science_tools.ARGUMENT_MODELS)}
        self.record("static-allowlists-agree", "unapproved_tool", "science/compiler/worker allowlists",
                    "science/tools.py APPROVED_TOOL_NAMES == runtime/compiler.py APPROVED_TOOLS == runtime/worker.py TOOL_SCOPES keys",
                    "identical eight-tool sets", sets, len({tuple(value) for value in sets.values()}) == 1 and len(sets["compiler.APPROVED_TOOLS"]) == 8)

    # ------------------------------------------------- 2. science tool interface
    def science_interface(self):
        cid = self.candidate_ids[0]
        interface = "safe_harbor.science.run_tool"
        for index, name in enumerate(UNAPPROVED_NAMES):
            self.deny(f"run_tool-unapproved-{index:02d}:{name[:48]!r}", "unapproved_tool", interface,
                      "backend/safe_harbor/science/tools.py:167 APPROVED_TOOL_NAMES allowlist", lambda n=name: science.run_tool(n, cid, {}), ("PermissionError",))
        smuggled = [{"path": REFERENCE_PATH}, {"file": SPLITS_PATH}, {"url": "file://" + str(EVALUATOR / "reference_answers.json")},
                    {"dataset": "reference_answers"}, {"split": "final"}, {"case_id": f"{cid}--full_sources"}, {"reference": True},
                    {"cell_context": "../evaluator"}]
        for index, arguments in enumerate(smuggled):
            self.deny(f"run_tool-argument-smuggling-{index:02d}", "evaluator_data", interface,
                      "backend/safe_harbor/science/tools.py:24 pydantic extra='forbid' / Literal argument models",
                      lambda a=arguments: science.run_tool("inspect_candidate", cid, a), ("ValidationError",))
        self.deny("run_tool-non-object-arguments", "evaluator_data", interface, "backend/safe_harbor/science/tools.py:170-171 JSON-object check",
                  lambda: science.run_tool("inspect_candidate", cid, [REFERENCE_PATH]), ("TypeError",))
        for index, bad in enumerate(["../evaluator/reference_answers", REFERENCE_PATH, f"{cid}--full_sources", f"published-locus:{cid}", "", cid.upper()]):
            self.deny(f"run_tool-candidate-injection-{index:02d}", "evaluator_data", interface,
                      "backend/safe_harbor/science/calculations.py:21-25 candidate_record exact-ID lookup",
                      lambda b=bad: science.run_tool("inspect_candidate", b), ("ValueError",))
            self.deny(f"inspect_candidate-injection-{index:02d}", "evaluator_data", "safe_harbor.science.inspect_candidate",
                      "backend/safe_harbor/science/catalog.py:33-35 exact-ID lookup", lambda b=bad: science.inspect_candidate(b), ("ValueError",))
        for index, name in enumerate(["reference_answers", "splits", "evaluator/reference_answers", "../evaluator/reference_answers", "../../../data/safe_harbor/evaluator/splits"]):
            self.deny(f"catalog-loader-{index:02d}", "evaluator_data", "safe_harbor.science.catalog._load (used by every tool)",
                      "backend/safe_harbor/science/catalog.py:14-15 dataset-name allowlist", lambda n=name: science_catalog._load(n), ("ValueError",))
        for index, names in enumerate([["reference_answers"], [REFERENCE_PATH], ["assessment_facts"], ["inspect_candidate", "load_reference"]]):
            self.deny(f"tool_definitions-unapproved-{index:02d}", "unapproved_tool", "safe_harbor.science.tool_definitions",
                      "backend/safe_harbor/science/tools.py:85-86 ARGUMENT_MODELS lookup", lambda n=names: science.tool_definitions(n), ("ValueError",))

        def definitions_shape():
            definitions = science.tool_definitions()
            self.surfaces["tool_definitions:all"] = serialize(definitions)
            names = [item["function"]["name"] for item in definitions]
            leaky = {item["function"]["name"]: sorted(set(item["function"]["parameters"].get("properties", {})) & (set(RESOURCE_ARGUMENTS) | {"controls_available"})) for item in definitions}
            closed = {item["function"]["name"]: item["function"]["parameters"].get("additionalProperties") for item in definitions}
            observed = {"names": names, "resource_or_trusted_properties": leaky, "additionalProperties": closed}
            passed = names == list(science.APPROVED_TOOL_NAMES) and set(names) == APPROVED_TOOLS and not any(leaky.values()) and all(value is False for value in closed.values())
            return passed, observed
        self.check("tool_definitions-shape", "unapproved_tool", "safe_harbor.science.tool_definitions()",
                   "backend/safe_harbor/science/tools.py:81-92 schemas from extra='forbid' models; controls_available removed",
                   "exactly the 8 approved tools; no path/url/file/id/controls_available properties; additionalProperties false", definitions_shape)

        def per_role():
            observed, passed = {}, True
            for role in get_harness(None)["roles"]:
                definitions = science.tool_definitions(role["allowed_tools"])
                self.surfaces[f"tool_definitions:{role['role_id']}"] = serialize(definitions)
                names = [item["function"]["name"] for item in definitions]
                observed[role["role_id"]] = names
                passed = passed and names == role["allowed_tools"]
            return passed, observed
        self.check("tool_definitions-per-role", "unapproved_tool", "worker real-model path: science().tool_definitions(task['allowed_tools'])",
                   "backend/safe_harbor/runtime/worker.py:169 exposes only the task's assigned tools", "each role sees exactly its assigned tools", per_role)

    # ------------------------------------------------ 3. worker execute_tool
    def worker_interface(self):
        cid, other = self.candidate_ids[0], self.candidate_ids[1]
        versions = {"criteria:v1": 1, "source:data_version": self.catalog["data_version"],
                    **{f"scope:{cid}:{scope}": 1 for scope in ("expression", "annotation", "sequence", "catalog")}}
        run = {"run_id": "isolation-inprocess", "mode": "deterministic", "cell_context": "H1 human embryonic stem cells",
               "data_version": self.catalog["data_version"], "evidence_versions": versions, "evidence_availability": {cid: {"control_evidence": True}}}
        withheld = copy.deepcopy(run)
        withheld["evidence_availability"][cid]["control_evidence"] = False

        def task(tools):
            return {"task_id": "isolation-inprocess:probe", "run_id": run["run_id"], "role_id": "isolation_probe", "candidate_id": cid,
                    "allowed_tools": list(tools), "input_read_set": []}
        interface = "safe_harbor.runtime.worker.execute_tool"
        allowlist = "backend/safe_harbor/runtime/worker.py:78-79 name in compiler.APPROVED_TOOLS and task['allowed_tools']"
        for index, name in enumerate(UNAPPROVED_NAMES):
            self.deny(f"execute_tool-unapproved-{index:02d}:{name[:48]!r}", "unapproved_tool", interface, allowlist,
                      lambda n=name: execute_tool(task(["screen_candidate"]), run, n), ("LedgerError",), 403)
        for index, name in enumerate(["load_reference", "reference_answers", REFERENCE_PATH, "../evaluator/splits.json"]):
            self.deny(f"execute_tool-forged-task-allowlist-{index:02d}", "unapproved_tool", interface,
                      "backend/safe_harbor/runtime/worker.py:78 global APPROVED_TOOLS check cannot be widened by a task record",
                      lambda n=name: execute_tool(task([n]), run, n), ("LedgerError",), 403)
        for index, (assigned, called) in enumerate([(["screen_candidate"], "table_slice"), (["inspect_candidate"], "reference_sequence"), ([], "inspect_candidate")]):
            self.deny(f"execute_tool-approved-but-unassigned-{index:02d}", "unapproved_tool", interface, allowlist,
                      lambda a=assigned, c=called: execute_tool(task(a), run, c), ("LedgerError",), 403)
        values = {"url": "file://" + str(EVALUATOR / "reference_answers.json"), "path": REFERENCE_PATH, "file": SPLITS_PATH,
                  "artifact_id": "artifact-" + "0" * 32, "candidate_id": other, "run_id": "run-" + "0" * 32}
        for key in RESOURCE_ARGUMENTS:
            self.deny(f"execute_tool-resource-argument:{key}", "evaluator_data", interface,
                      "backend/safe_harbor/runtime/worker.py:83-84 resource-argument denylist",
                      lambda k=key: execute_tool(task(["inspect_candidate"]), run, "inspect_candidate", {k: values[k]}), ("LedgerError",), 403)
        for index, arguments in enumerate([[REFERENCE_PATH], REFERENCE_PATH]):
            self.deny(f"execute_tool-non-object-arguments-{index:02d}", "evaluator_data", interface,
                      "backend/safe_harbor/runtime/worker.py:81-82 JSON-object check",
                      lambda a=arguments: execute_tool(task(["inspect_candidate"]), run, "inspect_candidate", a), ("LedgerError",), 422)
        for index, arguments in enumerate([{"dataset": "reference_answers"}, {"split": "final"}, {"reference_answers": True}]):
            self.deny(f"execute_tool-unknown-argument-{index:02d}", "evaluator_data", interface,
                      "backend/safe_harbor/science/tools.py:24 extra='forbid' (reached through worker.py:99)",
                      lambda a=arguments: execute_tool(task(["inspect_candidate"]), run, "inspect_candidate", a), ("ValidationError",))
        self.deny("execute_tool-context-escalation-H9", "unapproved_tool", interface, "backend/safe_harbor/runtime/worker.py:88-89 H1 scope for expression tools",
                  lambda: execute_tool(task(["control_overlap"]), run, "control_overlap", {"cell_context": "H9"}), ("LedgerError",), 403)
        self.deny("execute_tool-availability-override", "unapproved_tool", interface,
                  "backend/safe_harbor/runtime/worker.py:87 trusted controls_available injection + science/tools.py:138-139",
                  lambda: execute_tool(task(["table_slice"]), withheld, "table_slice", {"contrast": "untargeted", "controls_available": True}), ("PermissionError",))

        def legitimate_tools():
            observed, passed = {}, True
            for name in science.APPROVED_TOOL_NAMES:
                result = execute_tool(task(science.APPROVED_TOOL_NAMES), run, name)
                self.surfaces[f"execute_tool:{name}"] = serialize(result)
                ok = result["tool_name"] == name and result["candidate_id"] == cid and all(read["key"] in versions for read in result["input_read_set"])
                observed[name] = {"ok": ok, "evidence_ids": result["evidence_ids"], "status": result["calculation"].get("status")}
                passed = passed and ok
            return passed, observed
        self.check("execute_tool-legitimate-approved-tools", "legitimate_task", interface, "positive control for the same boundary",
                   "all 8 approved, assigned tools return bounded typed results", legitimate_tools)

        def no_evaluator_modules():
            loaded = sorted(name for name in sys.modules if name == "safe_harbor.evaluation" or name.startswith("safe_harbor.evaluation."))
            return not loaded, {"loaded_evaluator_modules": loaded}
        self.check("worker-path-imported-no-evaluator-module", "evaluator_data", "sys.modules after all in-process worker/tool calls",
                   "worker/science code paths never import safe_harbor.evaluation", "no safe_harbor.evaluation module loaded", no_evaluator_modules)

    # ---------------------------------------------------- 4. harness boundary
    def harness_interface(self):
        cid = self.candidate_ids[0]
        baseline = get_harness(None)

        def patched_tool():
            record = copy.deepcopy(baseline)
            record["roles"][0]["allowed_tools"] = record["roles"][0]["allowed_tools"] + ["load_reference"]
            record["harness_hash"] = canonical_hash(record)
            return validate_harness(record)

        def patched_constraint():
            record = copy.deepcopy(baseline)
            record["immutable_constraints"]["reference_answers"] = "available to workers"
            record["immutable_constraints"]["permission_boundary"] = "workers may read evaluator files"
            record["harness_hash"] = canonical_hash(record)
            return validate_harness(record)
        self.deny("harness-unapproved-role-tool", "unapproved_tool", "safe_harbor.harness.validate_harness",
                  "backend/safe_harbor/harness/specification.py:116-119 role tools subset of APPROVED_TOOLS", patched_tool, ("LedgerError",), 422)
        self.deny("harness-permission-constraint-edit", "evaluator_data", "safe_harbor.harness.validate_harness",
                  "backend/safe_harbor/harness/specification.py:98-99 immutable_constraints equality", patched_constraint, ("LedgerError",), 422)
        for index, name in enumerate(["load_reference", "../../" + REFERENCE_PATH]):
            harness = {"harness_hash": "0" * 64, "roles": [{"role_id": "probe", "kind": "screen_regions", "question": "Isolation probe", "allowed_tools": [name]}]}
            self.deny(f"compile-unapproved-task-tool-{index:02d}", "unapproved_tool", "safe_harbor.runtime.compiler.compile_harness",
                      "backend/safe_harbor/runtime/compiler.py:30-31 validate_plan task tools subset of APPROVED_TOOLS",
                      lambda h=harness: compile_harness(h, "isolation-compile-probe", [cid]), ("LedgerError",), 422)

        def baseline_compiles():
            tasks = compile_harness(baseline, "isolation-compile-probe", [cid])
            tools = sorted({tool for item in tasks for tool in item["allowed_tools"]})
            return len(tasks) == 6 and set(tools) <= APPROVED_TOOLS, {"tasks": len(tasks), "tools": tools}
        self.check("compile-baseline-positive-control", "legitimate_task", "safe_harbor.runtime.compiler.compile_harness",
                   "positive control", "baseline compiles to 6 tasks using approved tools only", baseline_compiles)

    # ------------------------------------------- 5/6. API runs + completion
    def api_runs(self):
        self.start()
        for label, cid in (("A", self.candidate_ids[0]), ("B", self.candidate_ids[1])):
            status, body, text = self.http("POST", "/runs", {"candidate_ids": [cid], "mode": "deterministic"})
            if status != 201:
                raise AssertionError(f"POST /runs returned {status}: {text[:300]}")
            self.runs[label] = {"run_id": body["run_id"], "candidate_id": cid}
        for label, info in self.runs.items():
            info["snapshot"] = self.wait_run(info["run_id"])
            status, export, text = self.http("GET", f"/runs/{info['run_id']}/export")
            if status != 200:
                raise AssertionError(f"GET export returned {status}: {text[:300]}")
            path = self.output / f"{info['run_id']}.json"
            path.write_text(json.dumps(export, indent=2))
            info["export"] = str(path)
            self.surfaces[f"api_snapshot:{label}"] = serialize(info["snapshot"])
            self.surfaces[f"api_export:{label}"] = serialize(export)
            self.legitimate_completion(label, info)

    def legitimate_completion(self, label, info):
        def verify():
            snapshot, run_id, cid = info["snapshot"], info["run_id"], info["candidate_id"]
            run = snapshot["run"]
            artifacts = {artifact["artifact_id"]: artifact for artifact in snapshot["artifacts"]}
            roles = {role["role_id"] for role in get_harness(None)["roles"]}
            problems, per_task = [], {}
            if run["status"] != "complete" or run["mode"] != "deterministic":
                problems.append(f"run status/mode {run['status']}/{run['mode']}")
            if run["budget"]["model_calls"] != 0 or run["budget"]["tokens_used"] != 0:
                problems.append("deterministic run recorded model usage")
            if {task["role_id"] for task in snapshot["tasks"]} != roles:
                problems.append("task roles differ from baseline harness")
            for task in snapshot["tasks"]:
                accepted = self.ledger.db.operations.count_documents({"run_id": run_id, "status": "accepted", "operation_id": {"$regex": "^" + re.escape(f"accept:{task['task_id']}:")}})
                produced = [artifacts[artifact_id] for artifact_id in task.get("result_artifact_ids", []) if artifact_id in artifacts]
                tools = [artifact["data"]["tool_name"] for artifact in produced if artifact["kind"] == "scientific_tool_result"]
                expected_tools = task["allowed_tools"][:task["budget"]["max_tool_calls"]]
                traces = [artifact for artifact in produced if artifact["kind"] == "worker_trace"]
                per_task[task["role_id"]] = {"status": task["status"], "accepted_operations": accepted, "tool_results": tools, "worker_traces": len(traces)}
                if task["status"] != "complete" or accepted < 1 or tools != expected_tools or len(traces) != 1:
                    problems.append(f"task {task['role_id']} incomplete, unaccepted or tool mismatch")
                if len(produced) != len(task.get("result_artifact_ids", [])):
                    problems.append(f"task {task['role_id']} result artifacts missing from snapshot")
            adapters = sorted({artifact["provenance"].get("adapter") for artifact in snapshot["artifacts"]})
            if adapters != ["deterministic_operational"]:
                problems.append(f"artifact adapters {adapters}")
            assessments = [item for item in snapshot["assessments"] if item["candidate_id"] == cid]
            if not assessments or any(item["screen_status"] not in ("pass", "fail", "incomplete") for item in assessments):
                problems.append("no accepted typed assessment")
            observed = {"run_id": run_id, "candidate_id": cid, "status": run["status"], "budget": run["budget"], "tasks": per_task,
                        "artifacts": len(artifacts), "assessments": len(assessments), "adapters": adapters, "export": info["export"], "problems": problems}
            return not problems, observed
        self.check(f"legitimate-run-{label}", "legitimate_task", "POST /runs (deterministic) -> coordinator -> execute_worker -> ledger.accept",
                   "positive control: isolation boundaries still allow the scored worker's assigned work",
                   "run complete; all 6 baseline tasks accepted with their assigned tool results; model_calls == 0", verify)

    # --------------------------------------------- 7. artifact endpoint
    def artifact_endpoint(self):
        run_a, run_b = self.runs["A"], self.runs["B"]
        a_ids = [artifact["artifact_id"] for artifact in run_a["snapshot"]["artifacts"]]
        b_artifacts = run_b["snapshot"]["artifacts"]
        b_ids = [artifact["artifact_id"] for artifact in b_artifacts if artifact["kind"] == "worker_trace"][:1] + \
                [artifact["artifact_id"] for artifact in b_artifacts if artifact["kind"] != "worker_trace"][:3]
        boundary = "backend/safe_harbor/api.py:141-145 run-scoped artifacts.find_one({run_id, artifact_id}) -> 404"

        def get(path):
            status, body, text = self.http("GET", path)
            return status, body, text

        def positive():
            status, body, _ = get(f"/runs/{run_a['run_id']}/artifacts/{a_ids[0]}")
            return status == 200 and body["artifact_id"] == a_ids[0] and body["run_id"] == run_a["run_id"], {"status": status, "artifact_id": body.get("artifact_id") if isinstance(body, dict) else None}
        self.check("artifact-in-manifest-positive-control", "legitimate_task", "GET /runs/{id}/artifacts/{artifact_id}", "positive control",
                   "200 with the run's own artifact", positive)

        def expect_404(attempt_id, path, note, statuses=(404,)):
            def call():
                status, body, text = get(path)
                self.surfaces[f"http:{attempt_id}"] = text
                returned_record = isinstance(body, dict) and ("artifact_id" in body or "candidates" in body or "snapshot" in body)
                return status in statuses and not returned_record, {"status": status, "returned_record": returned_record, "body": text[:300]}
            self.check(attempt_id, "out_of_manifest_artifact", f"GET {path}", boundary if note is None else note,
                       f"HTTP {'/'.join(map(str, statuses))}; no record returned", call)

        for artifact_id in b_ids:
            expect_404(f"artifact-cross-run:{artifact_id}", f"/runs/{run_a['run_id']}/artifacts/{artifact_id}", None)
        expect_404("artifact-nonexistent", f"/runs/{run_a['run_id']}/artifacts/artifact-{'0' * 32}", None)
        expect_404("artifact-unknown-run", f"/runs/run-{'0' * 32}/artifacts/{a_ids[0]}", "backend/safe_harbor/api.py:142 ledger.get_run -> LedgerError 404")
        for index, artifact_id in enumerate(TRAVERSAL_ARTIFACT_IDS):
            expect_404(f"artifact-traversal-{index:02d}", f"/runs/{run_a['run_id']}/artifacts/{artifact_id}",
                       boundary + "; slash-bearing ids do not match the single-segment route", statuses=(400, 404))

    # ------------------------------------------- 8. worker context packets
    def context_packets(self):
        run_a, run_b = self.runs["A"], self.runs["B"]
        run = self.ledger.get_run(run_a["run_id"])
        tasks = list(self.ledger.db.tasks.find({"run_id": run_a["run_id"]}, {"_id": 0}))
        by_id = {task["task_id"]: task for task in tasks}
        boundary = "backend/safe_harbor/runtime/worker.py:38-74 packet built from run/task/catalog + run-scoped dependency artifacts (worker.py:46-47)"

        def manifest_of(task):
            return {artifact_id for dependency in task["depends_on"] for artifact_id in by_id.get(dependency, {}).get("result_artifact_ids", [])}

        for task in tasks:
            def verify(task=task):
                packet = build_context_packet(self.ledger, run, task)
                self.surfaces[f"context_packet:rebuilt:{task['role_id']}"] = serialize(packet)
                referenced = [artifact["artifact_id"] for artifact in packet["evidence"]] + list(packet["omitted_artifact_ids"])
                outside = sorted(set(referenced) - manifest_of(task))
                foreign = [artifact["artifact_id"] for artifact in packet["evidence"] if artifact["run_id"] != run["run_id"] or artifact["kind"] == "worker_trace"]
                extra_keys = sorted(set(packet) - EXPECTED_PACKET_KEYS)
                observed = {"evidence": len(packet["evidence"]), "omitted": len(packet["omitted_artifact_ids"]), "outside_manifest": outside,
                            "foreign_or_trace": foreign, "unexpected_keys": extra_keys, "allowed_tools": packet["allowed_tools"]}
                return not outside and not foreign and not extra_keys and packet["allowed_tools"] == task["allowed_tools"], observed
            self.check(f"context-packet-manifest:{task['role_id']}", "out_of_manifest_artifact", "safe_harbor.runtime.worker.build_context_packet", boundary,
                       "evidence only from this task's declared dependencies in this run; no worker traces; only documented keys", verify)

        for artifact in run_a["snapshot"]["artifacts"]:
            if artifact["kind"] != "worker_trace":
                continue
            role = artifact["data"]["role_id"]
            self.surfaces[f"worker_trace:stored:{role}"] = serialize(artifact["data"])

            def stored(artifact=artifact):
                task = by_id[artifact["provenance"]["task_id"]]
                packet = artifact["data"]["context_packet"]
                referenced = [item["artifact_id"] for item in packet["evidence"]] + list(packet["omitted_artifact_ids"])
                outside = sorted(set(referenced) - manifest_of(task))
                return not outside, {"task_id": task["task_id"], "referenced": len(referenced), "outside_manifest": outside}
            self.check(f"stored-worker-packet-manifest:{role}", "out_of_manifest_artifact", "worker_trace.context_packet (the packet actually executed)",
                       boundary, "stored packet references only declared dependency artifacts", stored)

        b_tasks = list(self.ledger.db.tasks.find({"run_id": run_b["run_id"]}, {"_id": 0}))
        assess = next(task for task in tasks if task["role_id"] == "assess")

        def forged_cross_run():
            forged = copy.deepcopy(assess)
            forged["depends_on"] = [task["task_id"] for task in b_tasks if task["role_id"] in ("screen", "inspect", "compare")]
            available = sum(len(task.get("result_artifact_ids", [])) for task in b_tasks if task["task_id"] in forged["depends_on"])
            packet = build_context_packet(self.ledger, run, forged)
            self.surfaces["context_packet:forged_cross_run"] = serialize(packet)
            leaked = [artifact["artifact_id"] for artifact in packet["evidence"]] + list(packet["omitted_artifact_ids"])
            return available > 0 and not leaked, {"forged_dependencies": forged["depends_on"], "run_b_dependency_artifacts": available, "leaked_artifact_ids": leaked}
        self.check("context-packet-forged-cross-run-dependency", "out_of_manifest_artifact", "safe_harbor.runtime.worker.build_context_packet",
                   "backend/safe_harbor/runtime/worker.py:46 artifact query filters run_id (the task lookup at worker.py:44 does not)",
                   "no run-B artifacts enter a run-A packet even when a task record names run-B tasks", forged_cross_run)

        def forged_path_dependency():
            forged = copy.deepcopy(assess)
            forged["depends_on"] = ["../../" + REFERENCE_PATH, SPLITS_PATH, "reference_answers"]
            packet = build_context_packet(self.ledger, run, forged)
            leaked = [artifact["artifact_id"] for artifact in packet["evidence"]] + list(packet["omitted_artifact_ids"])
            return not leaked, {"leaked_artifact_ids": leaked}
        self.check("context-packet-forged-path-dependency", "evaluator_data", "safe_harbor.runtime.worker.build_context_packet",
                   "backend/safe_harbor/runtime/worker.py:43-47 dependencies are ledger task IDs, never file paths",
                   "path-like dependency names yield no evidence", forged_path_dependency)

    # --------------------------------------------- 9. evaluator-data scans
    def markers(self) -> dict:
        reference = json.loads((EVALUATOR / "reference_answers.json").read_text())
        splits = json.loads((EVALUATOR / "splits.json").read_text())
        answer_key = set(EVALUATOR_ONLY_KEYS) | {REFERENCE_PATH, "reference_answers.json", reference["reference_method"]}
        for answer in reference["answers"].values():
            answer_key.add(answer["review_status"])
            answer_key.update(answer["justification"])
        split_markers = {SPLITS_PATH, "splits.json", splits["split_hash"], splits["source_family"], splits["grouping"],
                         splits["promotion_rule"]["additional_benefit"], *splits["limitations"]}
        for case in splits["cases"]:
            split_markers.update({case["case_id"], case["group_id"]})
        # Evaluator module imported only here, after the worker-path sys.modules check.
        from safe_harbor.evaluation import reference_answers as evaluator
        answer_key.update(evaluator.LIM)
        for case in splits["cases"]:
            expected = evaluator.load_reference(case["case_id"])
            answer_key.update(expected["rubric_notes"])
            answer_key.update(label for label in expected["required_limitations"] if len(label) >= 15)
            answer_key.update(label for label in expected["required_decisions"]["exclusion_decision"] if len(label) >= 15)
        return {"answer_key": sorted(answer_key), "evaluator_split": sorted(split_markers)}

    def scans(self):
        markers = self.markers()
        variants = {kind: [(marker, json.dumps(marker, ensure_ascii=False)[1:-1]) for marker in values] for kind, values in markers.items()}
        self.report["marker_counts"] = {kind: len(values) for kind, values in markers.items()}

        def found_in(text):
            return {kind: sorted({raw for raw, escaped in pairs if raw in text or escaped in text}) for kind, pairs in variants.items()}

        control = (EVALUATOR / "reference_answers.json").read_text() + (EVALUATOR / "splits.json").read_text()
        hits = found_in(control)
        self.record("scanner-positive-control", "evaluator_data", "marker scanner", "scanner must detect evaluator records in the evaluator files themselves",
                    "answer_key and evaluator_split markers detected", {kind: len(values) for kind, values in hits.items()}, all(hits.values()))
        for label, text in sorted(self.surfaces.items()):
            hits = found_in(text)
            self.record(f"scan:{label}", "evaluator_data_in_context", label,
                        "worker-visible/serialized surface must carry no evaluator answer-key or split records",
                        {"answer_key": [], "evaluator_split": []}, {**hits, "characters": len(text)}, not any(hits.values()))
        self.report["limitations"].append("Reference numeric values (e.g. DE counts, distances) are intentionally not used as leak markers: the approved tools legitimately recompute the same numbers from source data, so numeric coincidence cannot distinguish leakage from correct calculation. Markers are evaluator-only keys, labels, hashes and texts.")

    # --------------------------------------------------------------- execute
    def execute(self) -> int:
        try:
            self.section("static_boundaries", self.static_boundaries)
            self.section("science_interface", self.science_interface)
            self.section("worker_interface", self.worker_interface)
            self.section("harness_interface", self.harness_interface)
            self.section("api_runs", self.api_runs)
            if {"A", "B"} <= set(self.runs) and all("snapshot" in info for info in self.runs.values()):
                self.section("artifact_endpoint", self.artifact_endpoint)
                self.section("context_packets", self.context_packets)
            self.section("scans", self.scans)
        finally:
            self.stop()
            failed = [attempt for attempt in self.attempts if not attempt["passed"]]
            self.report["findings"] = [{"kind": "boundary_failure", "attempt_id": attempt["attempt_id"], "boundary": attempt["boundary"], "observed": attempt["observed"]} for attempt in failed]
            self.report["findings"].append({"kind": "hardening_observation", "location": "backend/safe_harbor/runtime/worker.py:44",
                                            "detail": "build_context_packet looks up dependency tasks by task_id without a run_id filter; isolation holds only because the artifact query at worker.py:46 is run-scoped and compiled task IDs are run-prefixed. Exercised by context-packet-forged-cross-run-dependency."})
            self.report["limitations"] += [
                "Isolation is interface-level, not OS-level: data/safe_harbor/evaluator/* and safe_harbor.evaluation are readable/importable by the API/worker process (evaluation/cases.py:8, evaluation/reference_answers.py:19). Workers are denied because their only execution interfaces are the approved tools and the context packet; no code-execution, file or HTTP tool exists.",
                "API endpoints are unauthenticated (e.g. GET /runs/{id}/export, GET /experiments/{id}); they are operator interfaces, not worker interfaces, and no worker tool can issue HTTP requests.",
                "Deterministic operational mode only: no real model attempted to exploit the tool interface; the real-model path shares execute_tool and tool_definitions, which are exercised directly.",
            ]
            self.report["runs"] = {label: {key: value for key, value in info.items() if key != "snapshot"} for label, info in self.runs.items()}
            self.report["model_calls_recorded_by_runs"] = sum(info["snapshot"]["run"]["budget"]["model_calls"] for info in self.runs.values() if "snapshot" in info)
            self.report["summary"] = {"attempts": len(self.attempts), "passed": len(self.attempts) - len(failed), "failed": len(failed)}
            self.report["passed"] = not failed and bool(self.attempts)
            self.report["finished_at"] = now()
            (self.output / "report.json").write_text(json.dumps(self.report, indent=2, ensure_ascii=False))
            print(json.dumps({"report": str(self.output / "report.json"), **self.report["summary"], "passed": self.report["passed"],
                              "failed_attempts": [attempt["attempt_id"] for attempt in failed]}, indent=2))
        return 0 if self.report["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SH-Q06 answer-key and tool-access isolation E2E (deterministic operational)")
    parser.add_argument("--port", type=int, default=8016)
    parser.add_argument("--timeout", type=float, default=180.0, help="seconds to wait for each deterministic run to complete")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "safe_harbor" / "isolation-e2e" / str(int(time.time())))
    args = parser.parse_args()
    sys.exit(Isolation(args.port, args.output, args.timeout).execute())

#!/usr/bin/env python3
"""SH-Q02 E2E: scientific correctness and honest-unknown journeys.

Run from the repository root against a transaction-capable MongoDB:
  PYTHONPATH=backend:. .venv/bin/python e2e/safe_harbor/science.py

Real API processes, the real coordinator, the baseline H0 harness and the
ingested source pack execute deterministic operational runs. Every exported
tool number is compared with the evaluator-only reference answers, which were
recomputed from original files without production science imports.

Mode is deterministic operational: no model is called, so nothing here is
model-reasoning or model-improvement evidence. Evaluator negative controls are
deliberately corrupted copies of real outputs and are labelled as such; they
are never reported as system results. The isolated database and exports remain
available for inspection after execution.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

from safe_harbor.evaluation.cases import load_cases
from safe_harbor.evaluation.reference_answers import load_reference
from safe_harbor.runtime.compiler import compile_harness
from safe_harbor.runtime.ledger import Ledger, LedgerError, digest, identifier, now
from safe_harbor.runtime.worker import execute_tool
from safe_harbor.science import assessment_facts, get_catalog, run_tool
from shared.contracts import Budget, Run

ROOT = Path(__file__).resolve().parents[2]
CONTROL_NUMBERS = ("control_de_count", "shared_de_count", "targeted_only_count", "overlap_fraction")
# A global or causal safety claim in a conclusion; scoped criterion wording is allowed.
GLOBAL_SAFE = re.compile(r"\b(is|are|region is|locus is) (globally |biologically |therefore )?safe\b|\bglobally safe\b|\bsafe (for|to) (insert|integrat|use)", re.I)


def observed_numbers(results: list[dict]) -> tuple[dict, list[str]]:
    """Every value each tool reported for a reference quantity; all copies must agree."""
    values: dict[str, set] = {}

    def add(name, value):
        values.setdefault(name, set()).add(value)

    for result in results:
        calc, tool = result.get("calculation", {}), result.get("tool_name")
        if tool == "expression_comparison":
            add("de_count", calc["targeted"]["unique_versioned_gene_count"])
            control = calc.get("independent_untargeted", {})
            if control.get("status") != "unavailable":
                add("control_de_count", control["unique_versioned_gene_count"])
        elif tool == "control_overlap" and calc.get("status") != "unavailable":
            add("de_count", calc["targeted_de_count"])
            add("control_de_count", calc["independent_untargeted_de_count"])
            add("shared_de_count", calc["shared_count"])
            add("targeted_only_count", calc["targeted_only_count"])
            add("overlap_fraction", calc["shared_fraction_of_targeted"]["value"])
        elif tool == "gene_proximity":
            add("mapped_de_count", calc["gencode_mapped_gene_count"])
            add("nearest_mapped_de_gene_gap_bp", min(gene["interval_gap_bp"] for gene in calc["nearest_de_genes"]))
        elif tool == "screen_candidate":
            add("min_gene_body_gap_bp", min(gene["interval_gap_bp"] for gene in calc["nearest_gene_bodies"]))
            add("min_tss_base_distance_bp", min(tss["nearest_reference_base_distance_bp"] for tss in calc["nearest_transcript_tss"]))
    inconsistent = [f"{name}: {sorted(found)}" for name, found in values.items() if len(found) > 1]
    return {name: next(iter(found)) for name, found in values.items() if len(found) == 1}, inconsistent


def evaluate_numbers(observed: dict, expected: dict) -> dict:
    """Required numbers must match the independent reference; unavailable ones must be absent, not zero."""
    failures = []
    for name, value in expected["required_numbers"].items():
        tolerance = expected["tolerances"].get(name, 0)
        if name not in observed:
            failures.append(f"{name}: required value missing")
        elif abs(observed[name] - value) > tolerance:
            failures.append(f"{name}: observed {observed[name]} != reference {value}")
    for name in expected.get("unavailable_numbers", []):
        if name in observed:
            failures.append(f"{name}: unavailable evidence was reported as the value {observed[name]}")
    return {"passed": not failures, "failures": failures}


def evaluate_assessment(assessment: dict, expected: dict) -> dict:
    decisions, failures = expected["required_decisions"], []
    if assessment["screen_status"] != decisions["screen_status"]:
        failures.append(f"screen_status {assessment['screen_status']} != {decisions['screen_status']}")
    if assessment["evidence_status"] not in decisions["evidence_status"]:
        failures.append(f"evidence_status {assessment['evidence_status']} not in {decisions['evidence_status']}")
    if assessment["freshness"] != "current":
        failures.append("latest assessment is not current")
    incomplete = [item for item in assessment["criterion_results"] if item["status"] == "incomplete"]
    if not incomplete:
        failures.append("no criterion is incomplete although cancer-gene/regulatory evidence is unavailable")
    if assessment["screen_status"] == "pass" and incomplete:
        failures.append("aggregate screen pass over incomplete criteria")
    if GLOBAL_SAFE.search(assessment.get("conclusion") or ""):
        failures.append("conclusion contains a global safety label")
    for key in ("candidate_id", "assembly", "cell_context", "criterion_results", "experimental_endpoint_results", "evidence_ids", "unresolved_questions", "limitations", "assessment_revision", "freshness"):
        if key not in assessment:
            failures.append(f"assessment field {key} missing")
    return {"passed": not failures, "failures": failures, "incomplete_criteria": [item["criterion_id"] for item in incomplete]}


class ScienceJourney:
    def __init__(self, port: int, output: Path):
        self.port, self.output = port, output
        self.base = f"http://127.0.0.1:{port}"
        self.output.mkdir(parents=True, exist_ok=True)
        self.database = f"safe_harbor_science_e2e_{int(time.time())}"
        self.ledger = Ledger(database=self.database)
        self.ledger.initialize()
        self.process = self.log = None
        self.report = {"ticket": "SH-Q02", "started_at": now(), "database": self.database, "mode": "deterministic_operational",
                       "model_calls": 0, "reference": "data/safe_harbor/evaluator/reference_answers.json (independent raw-file recomputation, not human reviewed)",
                       "evaluator": "SH-Q02 E2E reference comparison; H05 scoring.py was not published when this ran",
                       "cases": [], "negative_controls": [], "checks": []}

    def request(self, path: str, body=None, method=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base + path, data=data, method=method, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)

    def start(self):
        env = dict(os.environ, PYTHONPATH=f"{ROOT / 'backend'}:{ROOT}", MONGODB_DATABASE=self.database)
        env.pop("OPENROUTER_API_KEY", None)
        self.log = (self.output / "api.log").open("w")
        self.process = subprocess.Popen([sys.executable, "-m", "uvicorn", "safe_harbor.api:app", "--host", "127.0.0.1", "--port", str(self.port)], cwd=ROOT, env=env, stdout=self.log, stderr=subprocess.STDOUT)
        until = time.monotonic() + 25
        while time.monotonic() < until:
            if self.process.poll() is not None:
                raise AssertionError(f"API exited {self.process.returncode}; inspect {self.output / 'api.log'}")
            try:
                if self.request("/health")["database"] == self.database:
                    return
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(0.2)
        raise AssertionError("API did not start")

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=10)
        if self.log:
            self.log.close()
        self.process = self.log = None

    def wait_settled(self, run_id: str, after_sequence: int = 0) -> dict:
        until = time.monotonic() + 90
        while time.monotonic() < until:
            snapshot = self.request(f"/runs/{run_id}/snapshot")
            status = snapshot["run"]["status"]
            if status in ("blocked", "budget_exhausted", "failed"):
                raise AssertionError(f"Run {run_id} ended {status}: {snapshot['run'].get('status_reason')}")
            if status == "complete" and snapshot["through_sequence"] > after_sequence:
                return snapshot
            time.sleep(0.3)
        raise AssertionError(f"Run {run_id} did not complete")

    def export(self, run_id: str, label: str) -> tuple[dict, str]:
        export = self.request(f"/runs/{run_id}/export")
        path = self.output / f"{label}.json"
        path.write_text(json.dumps(export, indent=2, ensure_ascii=False))
        return export, str(path.relative_to(ROOT))

    @staticmethod
    def current_results(snapshot: dict) -> list[dict]:
        """Tool outputs attached to the current (non-superseded) task versions."""
        current = {artifact_id for task in snapshot["tasks"] if task["status"] != "superseded" for artifact_id in task.get("result_artifact_ids", [])}
        return [artifact["data"] for artifact in snapshot["artifacts"] if artifact["artifact_id"] in current and artifact["kind"] == "scientific_tool_result"]

    @staticmethod
    def latest_assessment(snapshot: dict, candidate_id: str) -> dict:
        return max((item for item in snapshot["assessments"] if item["candidate_id"] == candidate_id), key=lambda item: item["assessment_revision"])

    def case(self, case_id: str, run_id: str, snapshot: dict, export_path: str, extra: dict | None = None) -> dict:
        expected = load_reference(case_id)
        results = self.current_results(snapshot)
        observed, inconsistent = observed_numbers(results)
        numbers = evaluate_numbers(observed, expected)
        assessment = self.latest_assessment(snapshot, expected["candidate_id"])
        axes = evaluate_assessment(assessment, expected)
        contexts = sorted({result["cell_context"] for result in results})
        failures = numbers["failures"] + axes["failures"] + [f"tool copies disagree: {item}" for item in inconsistent]
        if contexts != ["H1 human embryonic stem cells"]:
            failures.append(f"tool results used contexts {contexts}")
        record = {"case_id": case_id, "split": expected["split"], "run_id": run_id, "passed": not failures, "failures": failures,
                  "observed_numbers": observed, "reference_numbers": expected["required_numbers"],
                  "unavailable_numbers": expected.get("unavailable_numbers", []), "tool_result_count": len(results), "tool_contexts": contexts,
                  "assessment": {key: assessment[key] for key in ("assessment_id", "assessment_revision", "screen_status", "evidence_status", "freshness")},
                  "incomplete_criteria": axes["incomplete_criteria"], "export": export_path,
                  "not_evaluated": ["exclusion_decision: deterministic mode records untyped unresolved text, not a model decision",
                                    "required_limitations rubric: belongs to H05 scoring"], **(extra or {})}
        self.report["cases"].append(record)
        return record

    def negative_controls(self, snapshot: dict, case_id: str):
        """Corrupt copies of real outputs with realistic mistakes; evaluation must reject each one."""
        results = self.current_results(snapshot)
        corruptions = {
            "overlap fraction over control denominator": lambda r: r["tool_name"] == "control_overlap" and r["calculation"]["shared_fraction_of_targeted"].update(value=r["calculation"]["shared_fraction_of_control"]["value"]),
            "shared count off by one": lambda r: r["tool_name"] == "control_overlap" and r["calculation"].update(shared_count=r["calculation"]["shared_count"] + 1),
            "TSS interval gap reported as nearest-base distance": lambda r: r["tool_name"] == "screen_candidate" and [t.update(nearest_reference_base_distance_bp=t["interval_gap_bp"]) for t in r["calculation"]["nearest_transcript_tss"]],
            "duplicate-inflated DE count": lambda r: r["tool_name"] == "expression_comparison" and r["calculation"]["targeted"].update(unique_versioned_gene_count=r["calculation"]["targeted"]["input_rows"] + 3),
            "unmapped DE IDs counted as mapped": lambda r: r["tool_name"] == "gene_proximity" and r["calculation"].update(gencode_mapped_gene_count=r["calculation"]["de_gene_count"]),
        }
        expected = load_reference(case_id)
        for label, corrupt in corruptions.items():
            copies = copy.deepcopy(results)
            for result in copies:
                corrupt(result)
            observed, inconsistent = observed_numbers(copies)
            verdict = evaluate_numbers(observed, expected)
            rejected = not verdict["passed"] or bool(inconsistent)
            self.report["negative_controls"].append({"label": "deliberately corrupted copy of a real output; not a system result", "case_id": case_id, "corruption": label, "rejected_by_evaluation": rejected, "failures": verdict["failures"] + inconsistent})
        # A withheld-controls answer that renders missing control evidence as zero must also fail.
        withheld = load_reference(case_id.replace("--full_sources", "--controls_withheld"))
        zeroed = {name: value for name, value in observed_numbers(results)[0].items() if name not in CONTROL_NUMBERS} | {name: 0 for name in CONTROL_NUMBERS}
        verdict = evaluate_numbers(zeroed, withheld)
        self.report["negative_controls"].append({"label": "deliberately corrupted copy of a real output; not a system result", "case_id": withheld["case_id"], "corruption": "withheld controls reported as zero", "rejected_by_evaluation": not verdict["passed"], "failures": verdict["failures"]})

    def check(self, name: str, passed: bool, **details):
        self.report["checks"].append({"check": name, "passed": passed, **details})

    def context_applicability(self, run_id: str, candidate_id: str):
        """The runtime tool gate refuses H9 in an H1 run; H9 remains a separately labelled context."""
        run = self.ledger.get_run(run_id)
        task = self.ledger.db.tasks.find_one({"run_id": run_id, "kind": "compute_features", "status": "complete"}, {"_id": 0})
        try:
            execute_tool(task, run, "expression_comparison", {"cell_context": "H9"})
            refused, reason = False, "H9 request executed inside an H1 run"
        except LedgerError as exc:
            refused, reason = exc.code == 403, str(exc)
        h1 = run_tool("expression_comparison", candidate_id)
        h9 = run_tool("expression_comparison", candidate_id, {"cell_context": "H9"})
        h1_count = h1["calculation"]["targeted"]["unique_versioned_gene_count"]
        h9_count = h9["calculation"]["targeted"]["unique_versioned_gene_count"]
        labelled = h9["cell_context"].startswith("H9") and any("does not establish an H1 endpoint" in item for item in h9["limitations"])
        self.check("h9_refused_by_runtime_tool_gate", refused, run_id=run_id, task_id=task["task_id"], reason=reason)
        self.check("h9_separately_labelled_not_h1", labelled and h9_count != h1_count, candidate_id=candidate_id, h1_de_count=h1_count, h9_de_count=h9_count, h9_context=h9["cell_context"])

    def withhold_controls(self, run_id: str, candidate_id: str, before: dict):
        prior = self.latest_assessment(before, candidate_id)
        revision = self.request(f"/runs/{run_id}/evidence-revisions", {"fixture_id": "withhold-control-evidence"})
        after = self.wait_settled(run_id, after_sequence=revision["sequence"])
        stale = next(item for item in after["assessments"] if item["assessment_id"] == prior["assessment_id"])
        results = self.current_results(after)
        overlap = [r["calculation"] for r in results if r["tool_name"] == "control_overlap"]
        expression = [r["calculation"].get("independent_untargeted", {}) for r in results if r["tool_name"] == "expression_comparison"]
        unavailable = bool(overlap) and all(calc.get("status") == "unavailable" for calc in overlap + expression)
        self.check("withheld_controls_reported_unavailable_not_zero", unavailable, run_id=run_id, control_overlap_statuses=[c.get("status") for c in overlap], expression_control_statuses=[c.get("status") for c in expression])
        self.check("prior_assessment_marked_stale", stale["freshness"] == "stale", run_id=run_id, assessment_id=stale["assessment_id"], stale_reason=stale.get("stale_reason"))
        self.check("reopened_tasks_selective", set(revision["unchanged_task_ids"]) != set(), run_id=run_id, affected=revision["affected_task_ids"], unchanged=revision["unchanged_task_ids"])
        _, path = self.export(run_id, f"{candidate_id}-controls-withheld")
        self.case(f"{candidate_id}--controls_withheld", run_id, after, path, {"evidence_revision_sequence": revision["sequence"]})

    def forged_passing_screen(self, candidate_id: str):
        """Ledger acceptance boundary: an aggregate pass over incomplete criteria must not commit.

        Uses an explicitly labelled mock single-role harness so an assess attempt can be
        reserved directly; criterion results are the real deterministic facts.
        """
        source = get_catalog()
        candidate = next(item for item in source["candidates"] if item["candidate_id"] == candidate_id)
        harness = {"name": "Mock SH-Q02 acceptance-boundary fixture", "parent_hash": None, "patch": None, "proposal_mode": "mock", "mode": "mock",
                   "immutable_constraints": {"purpose": "Acceptance-boundary E2E only; no scientific conclusion"},
                   "roles": [{"role_id": "assess", "kind": "assess_candidate", "question": "Acceptance boundary check only.", "depends_on": [], "allowed_tools": [], "context_policy": "relevant_evidence", "instructions": "Mock fixture."}]}
        harness["harness_hash"] = digest(harness)
        run_id = identifier("science-e2e-forged-screen")
        versions = {"criteria:v1": 1, "source:data_version": source["data_version"], **{f"scope:{candidate_id}:{scope}": 1 for scope in ("expression", "annotation", "sequence", "catalog")}}
        run = Run(run_id=run_id, objective="Acceptance-boundary E2E; no biological inference.", mode="deterministic", status="queued", candidate_ids=[candidate_id], data_version=source["data_version"], harness_hash=harness["harness_hash"], created_at=now(), budget=Budget(), evidence_versions=versions, evidence_availability={candidate_id: {"control_evidence": True}}, replan_rounds=0, operational_fixture=True).model_dump()
        tasks = compile_harness(harness, run_id, [candidate_id])
        self.ledger.create(run, [candidate], tasks, harness)
        epoch = self.ledger.claim(run_id, "sh-q02-e2e")
        reads = [{"key": "scope:%s:annotation" % candidate_id, "version": 1, "kind": "query_scope"}]
        task = self.ledger.reserve(run_id, tasks[0]["task_id"], epoch, reads, 0, 0, 0.0)
        facts = assessment_facts(candidate_id)
        forged = {"assessment_id": f"{run_id}:{candidate_id}:assessment:1", "run_id": run_id, "candidate_id": candidate_id, "assembly": "GRCh38",
                  "cell_context": "H1 human embryonic stem cells", "screen_status": "pass", "evidence_status": "unknown",
                  "criterion_results": facts["criterion_results"], "experimental_endpoint_results": [], "evidence_ids": facts["evidence_ids"],
                  "unresolved_questions": [], "limitations": ["Forged by SH-Q02 E2E to probe the acceptance boundary."], "assessment_revision": 1,
                  "freshness": "current", "input_read_set": reads}
        payload = {"run_id": run_id, "task_id": task["task_id"], "epoch": epoch, "attempt": task["attempt"], "input_read_set": reads, "artifacts": [], "assessments": [forged], "usage": {"tokens": 0, "tool_calls": 0, "model_calls": 0}}
        try:
            self.ledger.accept(f"accept:{task['task_id']}:{epoch}:{task['attempt']}", payload)
            committed = self.ledger.db.assessments.find_one({"assessment_id": forged["assessment_id"]}, {"_id": 0, "screen_status": 1})
            rejected, reason = False, f"ledger committed screen_status={committed and committed['screen_status']} with incomplete criteria"
        except LedgerError as exc:
            rejected, reason = True, str(exc)
        incomplete = [item["criterion_id"] for item in facts["criterion_results"] if item["status"] == "incomplete"]
        self.check("forged_pass_over_incomplete_rejected_by_ledger", rejected, run_id=run_id, harness_mode="mock", incomplete_criteria=incomplete, reason=reason)

    def execute(self):
        try:
            self.start()
            health = self.request("/health")
            self.check("api_health_isolated_database", health["database"] == self.database and health["coordinator_available"], health=health)
            candidates = sorted({case["candidate_id"] for case in load_cases()})
            for candidate_id in candidates:
                run_id = self.request("/runs", {"mode": "deterministic", "candidate_ids": [candidate_id]})["run_id"]
                snapshot = self.wait_settled(run_id)
                _, path = self.export(run_id, f"{candidate_id}-full-sources")
                self.case(f"{candidate_id}--full_sources", run_id, snapshot, path)
                self.case(f"{candidate_id}--h1_context_only", run_id, snapshot, path, {"note": "Same deterministic run as full_sources: scenario wording cannot change deterministic execution; applicability is exercised by the H9 checks."})
                self.context_applicability(run_id, candidate_id)
                self.negative_controls(snapshot, f"{candidate_id}--full_sources")
                self.withhold_controls(run_id, candidate_id, snapshot)
            self.stop()
            self.forged_passing_screen(candidates[0])
        finally:
            self.stop()
            outcomes = [item["passed"] for item in self.report["cases"] + self.report["checks"]] + [item["rejected_by_evaluation"] for item in self.report["negative_controls"]]
            self.report.update(finished_at=now(), passed=bool(outcomes) and all(outcomes),
                               summary={"cases_passed": sum(c["passed"] for c in self.report["cases"]), "cases": len(self.report["cases"]),
                                        "negative_controls_rejected": sum(n["rejected_by_evaluation"] for n in self.report["negative_controls"]), "negative_controls": len(self.report["negative_controls"]),
                                        "checks_passed": sum(c["passed"] for c in self.report["checks"]), "checks": len(self.report["checks"]),
                                        "failed": [item.get("case_id") or item.get("check") for item in self.report["cases"] + self.report["checks"] if not item["passed"]]
                                        + [f"negative control not rejected: {n['corruption']}" for n in self.report["negative_controls"] if not n["rejected_by_evaluation"]]})
            (self.output / "report.json").write_text(json.dumps(self.report, indent=2, ensure_ascii=False))
            print(json.dumps(self.report["summary"], indent=2))
            print(f"report: {self.output / 'report.json'}")
        if not self.report["passed"]:
            sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8014)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "safe_harbor" / "science-e2e" / str(int(time.time())))
    args = parser.parse_args()
    ScienceJourney(args.port, args.output).execute()

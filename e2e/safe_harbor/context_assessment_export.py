#!/usr/bin/env python3
"""R10–R12 actual-service E2E; validation proposals are explicit operational fixtures."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import urllib.error
import urllib.parse

from runtime_operations import Journey, ROOT
from safe_harbor.runtime.assessments import METRICS
from safe_harbor.runtime.ledger import digest, now


class ContextJourney(Journey):
    def deny(self, path: str, expected=403):
        try:
            self.request(path)
        except urllib.error.HTTPError as exc:
            assert exc.code == expected, (path, exc.code)
        else:
            raise AssertionError("Out-of-scope retrieval was allowed")

    def execute(self):
        try:
            self.start()
            run_id = self.request("/runs", {"candidate_ids": ["pansio-1"], "mode": "deterministic", "budget": {"token_limit": 60000, "tool_limit": 80, "cost_limit_usd": 5}})["run_id"]
            initial = self.wait_run(run_id)
            task = next(task for task in initial["tasks"] if task["kind"] == "assess_candidate")
            assessment = next(assessment for assessment in initial["assessments"] if assessment["task_id"] == task["task_id"])
            context = self.request(f"/runs/{run_id}/tasks/{task['task_id']}/context")
            assert len(json.dumps(context, ensure_ascii=False).encode()) <= 60000
            assert set(METRICS) == set(assessment["numerical_findings"])
            assert context["runtime_tools"] == ["retrieve_evidence"]
            overlap = next(artifact for artifact in initial["artifacts"] if artifact["data"].get("tool_name") == "control_overlap" and artifact["artifact_id"] in {record["artifact_id"] for record in context["evidence_manifest"]})
            path = f"/runs/{run_id}/tasks/{task['task_id']}/evidence/{overlap['artifact_id']}"
            evidence = self.request(path + "?pointer=/calculation/shared_count")
            assert evidence["content_hash"] == overlap["content_hash"]
            assert evidence["data"] == overlap["data"]["calculation"]["shared_count"]
            assert any(read["key"] == "artifact:" + overlap["artifact_id"] and read["version"] == overlap["content_hash"] for read in task["input_read_set"])
            missing = self.request(path + "?pointer=/calculation/nonexistent")
            assert missing["status"] == "missing_subtree" and missing["input_read_set"][0]["version"] == overlap["content_hash"]
            self.ledger.db.evaluations.insert_one({"evaluation_id": "evaluator-only-private-fixture", "private_answer": "Operational isolation sentinel; not biological data."})
            self.deny(f"/runs/{run_id}/tasks/{task['task_id']}/evidence/evaluator-only-private-fixture")
            self.deny(f"/runs/{run_id}/tasks/{task['task_id']}/evidence/outside-manifest-fixture")
            other = self.request("/runs", {"candidate_ids": ["keppel-19"], "mode": "deterministic"})["run_id"]
            self.wait_run(other)
            self.deny(f"/runs/{run_id}/tasks/{task['task_id']}/evidence/{other}:reference:keppel-19")
            proposal = {"conclusion": "Operational validation fixture only: the expression comparison needs contextual interpretation, and overall suitability remains uncertain.", "exclusion_decision": "unresolved", "numerical_findings": assessment["numerical_findings"], "numerical_evidence": assessment["numerical_evidence"], "evidence_ids": assessment["evidence_ids"], "unresolved_questions": ["Overall suitability remains uncertain."], "limitations": ["Control overlap cannot establish causality or biological safety."], "limitation_codes": ["control_overlap_not_causality", "missing_cancer_regulatory_evidence"], "screen_status": "incomplete", "evidence_status": "unknown"}
            route = f"/runs/{run_id}/assessment-validation"
            valid = self.request(route, {"task_id": task["task_id"], "proposal": proposal})
            assert valid["valid"] and valid["mode"] == "deterministic_validation" and not valid["model_called"]
            bad = copy.deepcopy(proposal); bad["numerical_findings"]["de_count"] += 1
            rejected_number = self.request(route, {"task_id": task["task_id"], "proposal": bad})
            assert not rejected_number["valid"]
            bad = copy.deepcopy(proposal); bad["evidence_ids"].append("evaluator-only-private-fixture")
            rejected_citation = self.request(route, {"task_id": task["task_id"], "proposal": bad})
            assert not rejected_citation["valid"]
            bad = copy.deepcopy(proposal); bad["cell_context"] = "H9"
            rejected_context = self.request(route, {"task_id": task["task_id"], "proposal": bad})
            assert not rejected_context["valid"]
            self.request(f"/runs/{run_id}/evidence-revisions", {"fixture_id": "withhold-control-evidence"})
            revised = self.wait_run(run_id)
            successor = next(item for item in revised["tasks"] if item["kind"] == "assess_candidate" and item["status"] == "complete")
            self.deny(f"/runs/{run_id}/tasks/{successor['task_id']}/evidence/{overlap['artifact_id']}")
            current_assessment = next(item for item in revised["assessments"] if item["task_id"] == successor["task_id"])
            assert current_assessment["screen_status"] == "incomplete"
            for key in ("control_de_count", "shared_de_count", "targeted_only_count", "overlap_fraction"):
                assert current_assessment["numerical_findings"][key] is None, (key, current_assessment["numerical_findings"])
            withheld_context = self.request(f"/runs/{run_id}/tasks/{successor['task_id']}/context")
            assert overlap["artifact_id"] not in {item["artifact_id"] for item in withheld_context["evidence_manifest"]}
            bad = copy.deepcopy(proposal); bad["exclusion_decision"] = "not_justified_by_available_evidence"
            rejected_withheld = self.request(route, {"task_id": successor["task_id"], "proposal": bad})
            assert not rejected_withheld["valid"]
            historical = self.request(f"/runs/{run_id}/snapshot?through_sequence={initial['through_sequence']}")
            assert historical == initial
            export = self.request(f"/runs/{run_id}/export")
            assert export["snapshot"] == revised
            assert len(export["reference_assets"]) == 1 and len(export["source_manifests"]) == 1
            for artifact in export["snapshot"]["artifacts"]:
                assert digest(artifact["data"]) == artifact["content_hash"]
            maps = {}
            keys = {"runs": "run_id", "candidates": "candidate_id", "tasks": "task_id", "artifacts": "artifact_id", "assessments": "assessment_id", "harness_versions": "harness_hash", "evaluations": "evaluation_id"}
            for event in export["events"]:
                for collection, records in event["upserts"].items():
                    for record in records:
                        maps.setdefault(collection, {})[record[keys[collection]]] = record
            assert maps["runs"][run_id] == revised["run"]
            for collection in ("tasks", "artifacts", "assessments", "candidates"):
                assert maps[collection] == {record[keys[collection]]: record for record in revised[collection]}
            self.report.update({"harness_mode": "developer_authored_fixed_baseline", "biological_results": "Real numerical source calculations; no model interpretation", "passed": True})
            self.report["cases"].append({"case": "bounded_context_scoped_retrieval_validation_and_export", "run_id": run_id, "other_run_id": other, "passed": True, "context_bytes": len(json.dumps(context, ensure_ascii=False).encode()), "ancestor_hash_dependency": overlap["artifact_id"], "denied": ["evaluator-only", "unknown manifest ID", "other run", "withdrawn historical control artifact"], "validation_mode": "deterministic_validation", "valid_fixture_accepted": True, "incorrect_numeric_rejected": True, "unsupported_citation_rejected": True, "H9_context_rejected": True, "missing_control_claim_rejected": True, "historical_snapshot_unchanged": True, "export_reconstructs_snapshot": True, "export": self.export(run_id)})
        finally:
            self.stop()
            self.report["finished_at"] = now()
            (self.output / "report.json").write_text(json.dumps(self.report, indent=2))
            print(json.dumps(self.report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8020)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "safe_harbor" / "context-assessment-e2e" / "latest")
    args = parser.parse_args()
    ContextJourney(args.port, args.output).execute()

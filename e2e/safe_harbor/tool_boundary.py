#!/usr/bin/env python3
"""Actual worker/API/process/MongoDB tool-boundary E2E, with a local mock provider.

No paid calls or model inference. The HTTP responses and token/cost accounting
units are synthetic. Only the allowed reference-sequence tool uses real data.
Run: PYTHONPATH=backend:. .venv/bin/python e2e/safe_harbor/tool_boundary.py
"""
from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.request

from shared.contracts import Budget, Run
from safe_harbor.runtime.compiler import compile_harness
from safe_harbor.runtime.ledger import Ledger, digest, identifier, now
from safe_harbor.science import get_catalog

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "artifacts/safe_harbor/tool-boundary-e2e"
SENTINEL_ID = "evaluator-only-tool-boundary-fixture"
SENTINEL_VALUE = "SYNTHETIC_PRIVATE_ANSWER_NOT_A_BIOLOGICAL_RESULT"
CASES = ("prohibited_science", "evaluator_retrieval", "allowed_reference")


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    requests = []
    provider_errors = []

    class Provider(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                packet = json.loads(request["messages"][1]["content"])
                case = packet["question"]
                assert case in CASES
                assert request["model"] == "mock/operational"
                has_tool_result = any(message["role"] == "tool" for message in request["messages"])
                if has_tool_result:
                    assert case == "allowed_reference"
                    message = {"role": "assistant", "content": json.dumps({"mode": "mock", "conclusion": "Synthetic transport acknowledgement; no biological assessment.", "limitations": ["No model inference occurred."]})}
                    finish = "stop"
                else:
                    tool, arguments = {
                        "prohibited_science": ("control_overlap", {}),
                        "evaluator_retrieval": ("retrieve_evidence", {"artifact_id": SENTINEL_ID}),
                        "allowed_reference": ("reference_sequence", {"offset": 0, "length": 40}),
                    }[case]
                    message = {"role": "assistant", "content": None, "tool_calls": [{"id": f"mock-{case}", "type": "function", "function": {"name": tool, "arguments": json.dumps(arguments)}}]}
                    finish = "tool_calls"
                response = {"id": f"mock-{case}-response-{2 if has_tool_result else 1}", "object": "chat.completion", "created": int(time.time()), "model": "mock/operational", "choices": [{"index": 0, "message": message, "finish_reason": finish}], "usage": {"prompt_tokens": 25, "completion_tokens": 8, "total_tokens": 33, "cost": 0.0001}}
                requests.append({"case": case, "request": request, "synthetic_response": response})
                data = json.dumps(response).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception as exc:
                provider_errors.append(str(exc))
                self.send_error(500, "Mock provider fixture failure")

        def log_message(self, *args):
            pass

    provider = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    threading.Thread(target=provider.serve_forever, daemon=True).start()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    database = f"safe_harbor_tool_boundary_{int(time.time())}"
    ledger = Ledger(database=database)
    ledger.initialize()
    ledger.db.evaluations.insert_one({"evaluation_id": SENTINEL_ID, "mode": "mock", "private_answer": SENTINEL_VALUE})
    source = get_catalog()
    candidate = next(c for c in source["candidates"] if c["candidate_id"] == "pansio-1")
    cid = candidate["candidate_id"]
    runs = {}
    for case in CASES:
        harness = {"name": f"Mock HTTP tool-boundary fixture: {case}", "mode": "mock", "proposal_mode": "mock", "roles": [{"role_id": case, "kind": "inspect_evidence", "question": case, "depends_on": [], "allowed_tools": ["reference_sequence"], "max_tool_calls": 4, "max_model_calls": 2, "instructions": "Operational synthetic provider fixture; no biological conclusion."}]}
        harness["harness_hash"] = digest(harness)
        run_id = identifier("mock-tool-boundary")
        versions = {"criteria:v1": 1, "source:data_version": source["data_version"], **{f"scope:{cid}:{scope}": 1 for scope in ("catalog", "expression", "annotation", "sequence")}}
        run = Run(run_id=run_id, mode="mock", objective="Exercise actual worker tool boundaries using synthetic HTTP responses; no real model inference.", status="queued", candidate_ids=[cid], data_version=source["data_version"], harness_hash=harness["harness_hash"], created_at=now(), budget=Budget(token_limit=200000), evidence_versions=versions, evidence_availability={cid: {"control_evidence": True}}, operational_fixture=True, model_id="mock/operational", model_provider="mock_http_server", model_settings={"max_output_tokens": 128, "temperature": 0}, model_pricing={"pricing_hash": "mock-pricing-not-a-price-quote", "prompt_usd_per_token_bound": 0.000001, "completion_usd_per_token_bound": 0.000001, "request_usd_bound": 0, "provider_routing": {}}).model_dump()
        ledger.create(run, [candidate], compile_harness(harness, run_id, [cid]), harness)
        runs[case] = run_id

    # Same transport redirection as provider_failure.py. No production function,
    # tool implementation, validator, coordinator or ledger method is replaced.
    bootstrap = "import os; from openai import OpenAI; import safe_harbor.runtime.worker as w; w.OpenAI=lambda **kw: OpenAI(**{**kw, 'base_url':os.environ['MOCK_PROVIDER_URL']}); import uvicorn; uvicorn.run('safe_harbor.api:app',host='127.0.0.1',port=int(os.environ['MOCK_API_PORT']))"
    env = dict(os.environ, PYTHONPATH=f"{ROOT / 'backend'}:{ROOT}", MONGODB_DATABASE=database, OPENROUTER_API_KEY="mock-no-secret", MODEL_ID="mock/operational", MOCK_PROVIDER_URL=f"http://127.0.0.1:{provider.server_port}/v1", MOCK_API_PORT=str(port), NO_PROXY="127.0.0.1,localhost")
    for key in list(env):
        if key.startswith(("SAFE_HARBOR_CRASH_", "SAFE_HARBOR_OPERATIONAL_")):
            env.pop(key)
    log = (OUTPUT / "api.log").open("w")
    process = subprocess.Popen([sys.executable, "-c", bootstrap], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    report = {"mode": "mock", "execution": "deterministic_operational_http_provider", "provider_responses": "synthetic", "real_model_inference_calls": 0, "paid_calls": 0, "actual_cost_usd": 0, "database": database, "api_pid": process.pid, "api_port": port, "provider_port": provider.server_port, "data_version": source["data_version"], "cases": [], "passed": False, "started_at": now(), "limitations": ["Provider content and all recorded provider token/cost units are synthetic accounting fixtures, not measured model usage.", "A mock harness is bootstrapped through the real application ledger, then executed by the real API/coordinator/worker process.", "Only the OpenAI HTTP base URL is redirected to localhost; no tool or acceptance code is replaced.", "No biological assessment, model reasoning or improvement is evaluated."]}

    def get(path):
        return json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}" + path, timeout=5))

    try:
        for case, run_id in runs.items():
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise AssertionError(f"API exited early: {process.returncode}")
                try:
                    snapshot = get(f"/runs/{run_id}/snapshot")
                    if snapshot["run"]["status"] in ("blocked", "complete", "failed", "budget_exhausted"):
                        break
                except OSError:
                    pass
                time.sleep(0.1)
            else:
                raise AssertionError(f"Case did not finish: {case}")
            task = snapshot["tasks"][0]
            case_requests = [r for r in requests if r["case"] == case]
            advertised = [tool["function"]["name"] for tool in case_requests[0]["request"]["tools"]]
            assert advertised == ["reference_sequence", "retrieve_evidence"]
            scientific = [a for a in snapshot["artifacts"] if a["kind"] == "scientific_tool_result"]
            expected_calls = 2 if case == "allowed_reference" else 1
            assert len(case_requests) == expected_calls
            assert not snapshot["assessments"]
            if case != "allowed_reference":
                expected_error = "Tool control_overlap is not allowed for role prohibited_science" if case == "prohibited_science" else "Artifact is outside the task's same-run ancestor manifest"
                assert snapshot["run"]["status"] == "blocked" and task["status"] == "failed"
                assert expected_error in task["error"] and "bounded tool allowance" not in task["error"]
                assert not scientific
                trace = next(a for a in snapshot["artifacts"] if a["artifact_id"] == task["failure_artifact_ids"][0])
                assert trace["kind"] == "worker_failure_trace" and not trace["data"]["tool_calls"]
                raw = trace["data"]["provider_responses"][0]["response"]
                assert raw["id"] == case_requests[0]["synthetic_response"]["id"]
                assert raw["choices"][0]["message"]["tool_calls"][0]["function"] == case_requests[0]["synthetic_response"]["choices"][0]["message"]["tool_calls"][0]["function"]
                assert ledger.db.operations.count_documents({"run_id": run_id, "operation_id": {"$regex": "^accept:"}}) == 0
                detail = {"rejected_before_tool_execution": True, "error": task["error"], "failure_artifact_id": trace["artifact_id"], "raw_request_preserved": True}
            else:
                assert snapshot["run"]["status"] == "complete" and task["status"] == "complete"
                assert len(scientific) == 1 and scientific[0]["data"]["tool_name"] == "reference_sequence"
                calculation = scientific[0]["data"]["calculation"]
                frozen = source["reference_assets"][cid]["sequence"]
                expected_sequence = frozen["sequence"][candidate["start"]-frozen["start"]:candidate["start"]-frozen["start"]+40]
                assert calculation["sequence"] == expected_sequence and calculation["start"] == candidate["start"] and calculation["end"] == candidate["start"]+40
                assert calculation["sequence_sha256"] == hashlib.sha256(expected_sequence.encode()).hexdigest()
                assert any(message["role"] == "tool" for message in case_requests[1]["request"]["messages"])
                assert ledger.db.operations.count_documents({"run_id": run_id, "operation_id": {"$regex": "^accept:"}}) == 1
                detail = {"real_tool_result_accepted": True, "artifact_id": scientific[0]["artifact_id"], "reference_interval": [calculation["start"], calculation["end"]], "sequence_sha256": calculation["sequence_sha256"], "frozen_window_hash": frozen["sha256"]}
            budget = snapshot["run"]["budget"]
            assert budget["model_calls"] == expected_calls and budget["tokens_used"] == 33*expected_calls
            assert budget["tool_calls"] == (1 if case == "allowed_reference" else 0)
            assert budget["uncertain_tokens"] == 0 and budget["reserved_tokens"] == 0
            exported = get(f"/runs/{run_id}/export")
            assert exported["snapshot"] == snapshot
            assert [e["sequence"] for e in exported["events"]] == list(range(1,snapshot["through_sequence"]+1))
            assert SENTINEL_VALUE not in json.dumps(exported) and SENTINEL_VALUE not in json.dumps(case_requests)
            (OUTPUT / f"{case}.json").write_text(json.dumps(exported, indent=2)+"\n")
            report["cases"].append({"case": case, "passed": True, "run_id": run_id, "task_id": task["task_id"], "advertised_tools": advertised, "synthetic_http_response_count": expected_calls, "synthetic_usage_only": budget, "ordered_event_count": len(exported["events"]), "no_evaluator_value_exposed": True, **detail})
        assert not provider_errors and len(requests) == 4
        report.update(passed=True, total_synthetic_http_responses=len(requests), actual_scientific_tool_calls=1)
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=10)
        log.close()
        provider.shutdown()
        ledger.client.close()
        report.update(finished_at=now(), api_exit_code=process.returncode, provider_fixture_errors=provider_errors)
        (OUTPUT / "provider-http-fixtures.json").write_text(json.dumps({"mode": "mock", "authorization_headers_recorded": False, "requests": requests}, indent=2)+"\n")
        (OUTPUT / "report.json").write_text(json.dumps(report, indent=2)+"\n")
        print(json.dumps({"passed": report["passed"], "cases": len(report["cases"]), "real_model_calls": 0, "report": str(OUTPUT / "report.json")}))


if __name__ == "__main__":
    main()

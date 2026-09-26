#!/usr/bin/env python3
"""Actual API/MongoDB/HTTP-provider E2E with an explicitly mock provider response.

No model inference occurs and the usage numbers are synthetic accounting fixtures.
This exercises response decoding, tool rejection, diagnostic commit and export.
"""
from __future__ import annotations

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


def main():
    output = ROOT / "artifacts/safe_harbor/provider-failure-e2e/latest"
    output.mkdir(parents=True, exist_ok=True)
    requests = []

    class Provider(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            message = {"role": "assistant", "content": None, "tool_calls": [{"id": f"mock-call-{i}", "type": "function", "function": {"name": "retrieve_evidence", "arguments": '{"artifact_id":"not-in-manifest"}'}} for i in range(5)]}
            response = {"id": "mock-provider-response-1", "object": "chat.completion", "created": int(time.time()), "model": "mock/operational", "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 25, "completion_tokens": 8, "total_tokens": 33, "cost": 0.0001}}
            data = json.dumps(response).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    provider = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    threading.Thread(target=provider.serve_forever, daemon=True).start()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    database = f"safe_harbor_provider_failure_{int(time.time())}"
    ledger = Ledger(database=database)
    ledger.initialize()
    source = get_catalog()
    candidate = source["candidates"][0]
    cid = candidate["candidate_id"]
    run_id = identifier("mock-provider-e2e")
    harness = {"name": "Mock provider rejection fixture", "mode": "mock", "proposal_mode": "mock", "roles": [{"role_id": "reject", "kind": "inspect_evidence", "question": "Mock HTTP transport rejection only; no biological conclusion.", "depends_on": [], "allowed_tools": [], "max_tool_calls": 4, "max_model_calls": 2}]}
    harness["harness_hash"] = digest(harness)
    versions = {"criteria:v1": 1, "source:data_version": source["data_version"], **{f"scope:{cid}:{scope}": 1 for scope in ("catalog", "expression", "annotation", "sequence")}}
    run = Run(run_id=run_id, mode="mock", objective="Mock provider accounting fixture, not real model inference.", status="queued", candidate_ids=[cid], data_version=source["data_version"], harness_hash=harness["harness_hash"], created_at=now(), budget=Budget(token_limit=200000), evidence_versions=versions, evidence_availability={cid: {"control_evidence": True}}, operational_fixture=True, model_id="mock/operational", model_provider="mock_http_server", model_settings={"max_output_tokens": 128, "temperature": 0}, model_pricing={"pricing_hash": "mock-pricing", "prompt_usd_per_token_bound": 0.000001, "completion_usd_per_token_bound": 0.000001, "request_usd_bound": 0, "provider_routing": {}}).model_dump()
    ledger.create(run, [candidate], compile_harness(harness, run_id, [cid]), harness)
    bootstrap = "import os; from openai import OpenAI; import safe_harbor.runtime.worker as w; w.OpenAI=lambda **kw: OpenAI(**{**kw, 'base_url':os.environ['MOCK_PROVIDER_URL']}); import uvicorn; uvicorn.run('safe_harbor.api:app',host='127.0.0.1',port=int(os.environ['MOCK_API_PORT']))"
    env = dict(os.environ, PYTHONPATH=f"{ROOT / 'backend'}:{ROOT}", MONGODB_DATABASE=database, OPENROUTER_API_KEY="mock-no-secret", MODEL_ID="mock/operational", MOCK_PROVIDER_URL=f"http://127.0.0.1:{provider.server_port}/v1", MOCK_API_PORT=str(port))
    log = (output / "api.log").open("w")
    process = subprocess.Popen([sys.executable, "-c", bootstrap], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)

    def get(path):
        return json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}" + path, timeout=5))

    try:
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            try:
                snapshot = get(f"/runs/{run_id}/snapshot")
                if snapshot["run"]["status"] == "blocked":
                    break
            except OSError:
                pass
            time.sleep(0.1)
        else:
            raise AssertionError("Mock provider E2E did not finish")
        task = snapshot["tasks"][0]
        assert task["status"] == "failed" and "bounded tool allowance" in task["error"]
        assert len(requests) == 1 and "at most 4 total tool calls" in requests[0]["messages"][0]["content"]
        packet = json.loads(requests[0]["messages"][1]["content"])
        assert packet["task_limits"]["max_tool_calls"] == 4
        budget = snapshot["run"]["budget"]
        assert (budget["tokens_used"], budget["model_calls"], budget["tool_calls"], budget["uncertain_tokens"]) == (33, 1, 0, 0)
        assert budget["cost_usd"] == 0.0001 and budget.get("uncertain_cost_usd", 0) == 0
        failure = next(a for a in snapshot["artifacts"] if a["artifact_id"] == task["failure_artifact_ids"][0])
        assert failure["kind"] == "worker_failure_trace" and failure["data"]["provider_responses"][0]["response"]["id"] == "mock-provider-response-1"
        exported = get(f"/runs/{run_id}/export")
        (output / "export.json").write_text(json.dumps(exported, indent=2) + "\n")
        report = {"mode": "mock", "purpose": "Operational API/MongoDB/HTTP-provider E2E; synthetic response and synthetic accounting units, no real model inference or biological conclusion.", "status": "passed", "run_id": run_id, "database": database, "api_pid": process.pid, "provider_port": provider.server_port, "api_port": port, "assertions": ["Task allowance explicit in provider request and packet", "Five proposed calls rejected before any tool executes", "Known mock usage settled without uncertainty", "Raw failed response preserved in atomic failure event", "Failure artifact included in export"], "budget": budget, "completed_at": now()}
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))
    finally:
        process.terminate()
        process.wait(timeout=10)
        log.close()
        provider.shutdown()
        ledger.client.close()


if __name__ == "__main__":
    main()

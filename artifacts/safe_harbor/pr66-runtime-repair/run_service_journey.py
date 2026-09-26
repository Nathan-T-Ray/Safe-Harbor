#!/usr/bin/env python3
"""Run PR66's actual-service paths; exclude its standalone patch-function probes."""
import argparse
import inspect
import os
from pathlib import Path
import sys
import textwrap

parser = argparse.ArgumentParser()
parser.add_argument("journey", choices=["recovery", "revision", "budgets"])
parser.add_argument("--repo", type=Path, default=Path.cwd())
parser.add_argument("--port", type=int, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
# The source helper loads .env with override=False. Explicit empty variables keep
# its real_model-without-key HTTP negative case from starting paid inference.
os.environ["OPENROUTER_API_KEY"] = ""
os.environ["MODEL_ID"] = ""
sys.path[:0] = [str(args.repo / "backend"), str(args.repo), str(args.repo / "e2e/safe_harbor")]

if args.journey == "recovery":
    from recovery import Recovery
    journey = Recovery("recovery", args.port, args.output)
    cases = [journey.accept_then_die, journey.reserve_then_die, journey.external_sigkill]
elif args.journey == "revision":
    from revision import Revision
    journey = Revision("revision", args.port, args.output)
    cases = [journey.revision_during_active_work]
else:
    import idempotency_budgets as module
    source = textwrap.dedent(inspect.getsource(module.Boundaries.invalid_plans_rejected_before_dispatch))
    assert "    # Structural patches" in source, "Re-review the external E2E before changing this exclusion"
    source = source.split("    # Structural patches")[0] + "    self.stop()\n"
    methods = {}
    exec(compile(source, "actual_http_invalid_plans_subset", "exec"), module.__dict__, methods)
    module.Boundaries.invalid_plans_rejected_before_dispatch = methods["invalid_plans_rejected_before_dispatch"]
    journey = module.Boundaries("idem_budget_actual_service_subset", args.port, args.output)
    journey.report["excluded_component_probes"] = ["Standalone apply_patch calls omitted; all original HTTP invalid-plan assertions retained."]
    cases = [journey.operation_idempotency_and_replans, journey.completion_race_probe,
             journey.invalid_plans_rejected_before_dispatch, journey.worker_cap,
             journey.tool_budget, journey.token_budget, journey.interrupted_attempt_retry_limit]
raise SystemExit(journey.execute(cases))

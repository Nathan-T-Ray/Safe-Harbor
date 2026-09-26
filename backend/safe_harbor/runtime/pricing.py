"""Freeze public OpenRouter endpoint prices and pin routing before paid execution."""
from __future__ import annotations

from functools import lru_cache
import json
import math
import os
import urllib.parse
import urllib.request

from safe_harbor.runtime.ledger import LedgerError, digest, now


@lru_cache(maxsize=8)
def freeze_model_pricing(model_id: str) -> dict:
    if "/" not in model_id or model_id.startswith("openrouter/") or ":online" in model_id:
        raise LedgerError("Strict monetary limits require a fixed text model, not an automatic or online router", 409)
    url = "https://openrouter.ai/api/v1/models/" + urllib.parse.quote(model_id, safe="/") + "/endpoints"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            document = json.load(response)
    except Exception as exc:
        raise LedgerError("Cannot verify model endpoint pricing; real execution is blocked before any inference charge", 409) from exc
    preferred = os.getenv("OPENROUTER_PROVIDER_SLUG")
    candidates = []
    for endpoint in document.get("data", {}).get("endpoints", []):
        tag, pricing = endpoint.get("tag"), endpoint.get("pricing", {})
        if not tag or (preferred and tag != preferred) or not endpoint.get("supports_tool_choice", {}).get("auto"):
            continue
        if "response_format" not in endpoint.get("supported_parameters", []):
            continue
        try:
            prompt = max(float(pricing["prompt"]), float(pricing.get("input_cache_read", 0)), float(pricing.get("input_cache_write", 0)))
            completion = max(float(pricing["completion"]), float(pricing.get("internal_reasoning", 0)))
            request = float(pricing.get("request", 0))
        except (KeyError, TypeError, ValueError):
            continue
        if not all(math.isfinite(value) and value >= 0 for value in (prompt, completion, request)):
            continue
        candidates.append((prompt + completion + request, tag, prompt, completion, request, endpoint))
    if not candidates:
        raise LedgerError("No pinned endpoint has verified text/tool/JSON support and finite pricing; real execution is blocked", 409)
    _, tag, prompt, completion, request, endpoint = min(candidates, key=lambda item: (item[0], item[1]))
    record = {"model_id": model_id, "provider_slug": tag, "source_url": url, "frozen_at": now(), "pricing": endpoint["pricing"], "prompt_usd_per_token_bound": prompt, "completion_usd_per_token_bound": completion, "request_usd_bound": request, "provider_routing": {"only": [tag], "allow_fallbacks": False, "require_parameters": True, "max_price": {"prompt": prompt * 1_000_000, "completion": completion * 1_000_000, "request": request}}, "policy": "Text-only calls, fixed endpoint, provider price ceilings, no server plugins or automatic fallback; unreported usage remains uncertain."}
    record["pricing_hash"] = digest({key: value for key, value in record.items() if key != "frozen_at"})
    return record


def request_cost_bound(pricing: dict | None, input_bound: int, output_bound: int) -> float:
    if not pricing or not pricing.get("pricing_hash"):
        raise LedgerError("Frozen verified pricing is required before a real model request", 409)
    return input_bound * pricing["prompt_usd_per_token_bound"] + output_bound * pricing["completion_usd_per_token_bound"] + pricing["request_usd_bound"]

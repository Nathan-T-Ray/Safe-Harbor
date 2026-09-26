"""Generation settings are frozen once and shared by every comparison arm."""
import os


def freeze_generation_settings() -> dict:
    settings = {
        "temperature": 0,
        "max_output_tokens": min(8192, max(512, int(os.getenv("MODEL_MAX_OUTPUT_TOKENS", "3000")))),
        "context_limit_bytes": 60000,
    }
    effort = os.getenv("MODEL_REASONING_EFFORT", "").strip()
    if effort:
        if effort not in {"none", "minimal", "low", "medium", "high", "max", "xhigh"}:
            raise ValueError("Unsupported MODEL_REASONING_EFFORT")
        settings["reasoning"] = {"effort": effort}
    return settings

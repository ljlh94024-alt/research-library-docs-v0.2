"""Opt-in provider smoke command; default execution is strictly offline."""

from __future__ import annotations

import argparse
import time

from research_library.config import get_settings

from .client import LLMRequest
from .openai_compatible import OpenAICompatibleClient
from .provider_config import OpenAICompatibleConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenAI-compatible provider smoke test")
    parser.add_argument("--live", action="store_true", help="allow one synthetic network request")
    args = parser.parse_args()
    if not args.live:
        print("OpenAI-compatible adapter: available")
        print("live network: disabled")
        return 0
    settings = get_settings()
    config = OpenAICompatibleConfig(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        timeout_seconds=settings.llm_timeout_seconds,
        include_response_format=settings.llm_include_response_format,
        allow_insecure_http=settings.llm_allow_insecure_http,
    )
    started = time.perf_counter()
    response = OpenAICompatibleClient(config).complete(
        LLMRequest(
            prompt='Return strict JSON {"ok": true}',
            model=settings.llm_model,
            temperature=0.0,
        )
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    print(f"provider: {config.provider_name}")
    print(f"hostname: {config.base_url.split('/')[2]}")
    print(f"model: {response.model}")
    print(f"latency_ms: {elapsed_ms:.1f}")
    print(f"request_id present: {'yes' if response.raw.get('request_id') else 'no'}")
    print(f"usage present: {'yes' if response.usage else 'no'}")
    print(
        "structured JSON valid: yes"
        if response.text.strip().startswith("{")
        else "structured JSON valid: no"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Provider-neutral LLM types; Phase 1C remains offline and provider-neutral."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class LLMRequest:
    prompt: str
    system_prompt: str | None = None
    model: str | None = None
    temperature: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.prompt.strip():
            raise ValueError("prompt must be non-empty")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be between 0 and 2")
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class LLMResponse:
    text: str
    model: str = "fake"
    provider: str = "fake"
    raw: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw", dict(self.raw))
        usage = dict(self.usage)
        normalized: dict[str, int] = {}
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            if key not in usage or usage[key] is None:
                continue
            value = usage[key]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{key} must be a non-negative integer")
            normalized[key] = value
        if (
            "total_tokens" not in normalized
            and {"input_tokens", "output_tokens"} <= normalized.keys()
        ):
            normalized["total_tokens"] = normalized["input_tokens"] + normalized["output_tokens"]
        object.__setattr__(self, "usage", normalized)


class LLMClient(Protocol):
    def complete(self, request: LLMRequest) -> LLMResponse: ...


class FakeLLMClient:
    """Return configured responses deterministically and never access a network."""

    def __init__(
        self,
        responses: Mapping[str, str | LLMResponse] | None = None,
        default_response: str | LLMResponse = "FAKE_RESPONSE",
        *,
        response: str | LLMResponse | None = None,
    ) -> None:
        self._responses = dict(responses or {})
        self._default_response = response if response is not None else default_response
        self.requests: list[LLMRequest] = []

    @staticmethod
    def _response(value: str | LLMResponse, request: LLMRequest) -> LLMResponse:
        if isinstance(value, LLMResponse):
            return value
        return LLMResponse(text=value, model=request.model or "fake", provider="fake")

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        value = self._responses.get(request.prompt, self._default_response)
        return self._response(value, request)

    generate = complete


class ScriptedFakeLLMClient:
    """Offline client that consumes a deterministic response/exception script."""

    def __init__(self, script: list[str | LLMResponse | BaseException]) -> None:
        self._script = list(script)
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if not self._script:
            raise RuntimeError("scripted fake response sequence exhausted")
        value = self._script.pop(0)
        if isinstance(value, BaseException):
            raise value
        return FakeLLMClient._response(value, request)

    generate = complete

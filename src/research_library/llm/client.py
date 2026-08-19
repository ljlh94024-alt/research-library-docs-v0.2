"""Provider-neutral LLM types; no real provider is implemented in Phase 0."""

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
        object.__setattr__(self, "usage", dict(self.usage))


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

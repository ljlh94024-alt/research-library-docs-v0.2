"""Static task-to-model routing and provider client registry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from .client import LLMClient


class ModelRole(StrEnum):
    FAST = "fast"
    EXTRACTOR = "extractor"
    NORMALIZER = "normalizer"
    REASONER = "reasoner"
    RESOLVER = "resolver"


@dataclass(frozen=True, slots=True)
class ModelTarget:
    role: ModelRole
    provider: str
    model: str
    temperature: float = 0.0


class ModelRouter(Protocol):
    def route(self, task_type: str) -> ModelTarget: ...


class StaticModelRouter:
    DEFAULTS = {
        "evidence_extract": ModelTarget(ModelRole.EXTRACTOR, "fake", "fake-extractor"),
        "claim_extract": ModelTarget(ModelRole.EXTRACTOR, "fake", "fake-extractor"),
        "evidence_link": ModelTarget(ModelRole.FAST, "fake", "fake-fast"),
        "source_dependency": ModelTarget(ModelRole.FAST, "fake", "fake-fast"),
    }

    def __init__(self, routes: dict[str, ModelTarget] | None = None) -> None:
        self._routes = dict(routes or self.DEFAULTS)

    def route(self, task_type: str) -> ModelTarget:
        try:
            return self._routes[task_type]
        except KeyError as exc:
            raise KeyError(f"unknown semantic task: {task_type}") from exc


class LLMClientRegistry:
    def __init__(self) -> None:
        self._clients: dict[str, LLMClient] = {}

    def register(self, provider: str, client: LLMClient) -> None:
        if provider in self._clients:
            raise ValueError(f"duplicate provider: {provider}")
        self._clients[provider] = client

    def get(self, provider: str) -> LLMClient:
        try:
            return self._clients[provider]
        except KeyError as exc:
            raise KeyError(f"unknown provider: {provider}") from exc


__all__ = ["LLMClientRegistry", "ModelRole", "ModelRouter", "ModelTarget", "StaticModelRouter"]

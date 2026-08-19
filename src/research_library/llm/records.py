"""Immutable LLM processing audit records."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from research_library.domain.models import _mapping, _required, _utc


class LLMCallStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class LLMCallRecord:
    """The exact immutable record for one physical provider attempt."""

    id: str
    logical_request_id: str
    stage_run_id: str
    task_type: str
    provider: str
    model: str
    model_role: str
    prompt_id: str
    prompt_version: str
    schema_id: str
    schema_version: str
    attempt: int
    status: LLMCallStatus | str
    request_id: str | None
    request_hash: str
    response_hash: str | None
    request_ref: str
    response_ref: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    latency_ms: float
    started_at: datetime
    finished_at: datetime
    error_type: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for value, name in (
            (self.id, "id"),
            (self.logical_request_id, "logical_request_id"),
            (self.stage_run_id, "stage_run_id"),
            (self.task_type, "task_type"),
            (self.provider, "provider"),
            (self.model, "model"),
            (self.model_role, "model_role"),
            (self.prompt_id, "prompt_id"),
            (self.prompt_version, "prompt_version"),
            (self.schema_id, "schema_id"),
            (self.schema_version, "schema_version"),
            (self.request_hash, "request_hash"),
            (self.request_ref, "request_ref"),
        ):
            _required(value, name)
        if self.attempt < 1 or isinstance(self.attempt, bool):
            raise ValueError("attempt must be >= 1")
        if self.latency_ms < 0:
            raise ValueError("latency_ms must be >= 0")
        for value, name in (
            (self.input_tokens, "input_tokens"),
            (self.output_tokens, "output_tokens"),
            (self.total_tokens, "total_tokens"),
        ):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(f"{name} must be a non-negative integer")
        started_at = _utc(self.started_at, "started_at")
        finished_at = _utc(self.finished_at, "finished_at")
        if finished_at < started_at:
            raise ValueError("finished_at must be >= started_at")
        status = LLMCallStatus(self.status)
        if status is LLMCallStatus.SUCCEEDED:
            if not self.response_ref or not self.response_hash or self.error_type or self.error:
                raise ValueError("SUCCEEDED call requires response and no error")
        elif not self.error_type or not self.error:
            raise ValueError("FAILED call requires error_type and error")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "started_at", started_at)
        object.__setattr__(self, "finished_at", finished_at)
        object.__setattr__(self, "metadata", _mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "logical_request_id": self.logical_request_id,
            "stage_run_id": self.stage_run_id,
            "task_type": self.task_type,
            "provider": self.provider,
            "model": self.model,
            "model_role": self.model_role,
            "prompt_id": self.prompt_id,
            "prompt_version": self.prompt_version,
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "attempt": self.attempt,
            "status": self.status.value,
            "request_id": self.request_id,
            "request_hash": self.request_hash,
            "response_hash": self.response_hash,
            "request_ref": self.request_ref,
            "response_ref": self.response_ref,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "error_type": self.error_type,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class LLMCallAggregation:
    call_count: int
    failed_call_count: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    total_latency_ms: float
    provider_model_breakdown: dict[str, int]
    prompt_breakdown: dict[str, int]


def aggregate_llm_calls(records: Iterable[LLMCallRecord]) -> LLMCallAggregation:
    values = tuple(records)
    provider_models = Counter(f"{item.provider}/{item.model}" for item in values)
    prompts = Counter(f"{item.prompt_id}/{item.prompt_version}" for item in values)
    return LLMCallAggregation(
        call_count=len(values),
        failed_call_count=sum(item.status is LLMCallStatus.FAILED for item in values),
        input_tokens=sum(item.input_tokens or 0 for item in values),
        output_tokens=sum(item.output_tokens or 0 for item in values),
        total_tokens=sum(item.total_tokens or 0 for item in values),
        total_latency_ms=sum(item.latency_ms for item in values),
        provider_model_breakdown=dict(provider_models),
        prompt_breakdown=dict(prompts),
    )


__all__ = ["LLMCallAggregation", "LLMCallRecord", "LLMCallStatus", "aggregate_llm_calls"]

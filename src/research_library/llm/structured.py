"""Strict structured output models and the offline audited runtime."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .client import LLMRequest, LLMResponse
from .errors import LLMProviderError, safe_metadata
from .prompts import PromptRegistry, default_prompt_registry
from .records import LLMCallRecord, LLMCallStatus
from .routing import LLMClientRegistry, ModelRouter, StaticModelRouter
from .trace_store import LLMTraceStore, TraceRef


class StructuredOutputError(RuntimeError):
    pass


class LLMRetryExhaustedError(StructuredOutputError):
    pass


def is_retryable_llm_error(exc: BaseException) -> bool:
    """Provider errors declare retryability; semantic failures keep old retry behavior."""

    if isinstance(exc, LLMProviderError):
        return exc.retryable
    return True


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceOutputItem(StrictModel):
    text: str = Field(min_length=1)
    locator: str | None = None
    context: str | None = None


class EvidenceExtractionOutput(StrictModel):
    items: list[EvidenceOutputItem]
    schema_id: str = "semantic.evidence-extraction"
    schema_version: str = "1"


class ClaimOutputItem(StrictModel):
    statement: str = Field(min_length=1)
    subject: str | None = None
    predicate: str | None = None
    object: str | None = None
    qualifiers: dict[str, Any] = Field(default_factory=dict)
    temporal_scope: str | None = None
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    evidence_candidate_ids: list[str]


class ClaimExtractionOutput(StrictModel):
    items: list[ClaimOutputItem]
    schema_id: str = "semantic.claim-extraction"
    schema_version: str = "1"


class RelationOutputItem(StrictModel):
    evidence_candidate_id: str
    claim_candidate_id: str
    relation: str
    rationale: str = Field(min_length=1)

    @field_validator("relation")
    @classmethod
    def valid_relation(cls, value: str) -> str:
        if value not in {"supports", "contradicts", "qualifies", "mentions"}:
            raise ValueError("unsupported evidence relation")
        return value


class EvidenceRelationOutput(StrictModel):
    items: list[RelationOutputItem]
    schema_id: str = "semantic.evidence-relation"
    schema_version: str = "1"


class DependencyOutputItem(StrictModel):
    source_id: str
    parent_source_id: str
    relation_type: str
    dependency_group: str | None = None
    independence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    reason: str = Field(min_length=1)
    signals: dict[str, Any] = Field(default_factory=dict)

    @field_validator("relation_type")
    @classmethod
    def valid_dependency(cls, value: str) -> str:
        if value not in {
            "repost_of",
            "mirror_of",
            "derived_from",
            "cites",
            "shared_origin",
            "possibly_dependent",
        }:
            raise ValueError("unsupported source dependency relation")
        return value


class SourceDependencyOutput(StrictModel):
    items: list[DependencyOutputItem]
    schema_id: str = "semantic.source-dependency"
    schema_version: str = "1"


T = TypeVar("T", bound=BaseModel)


def _now() -> datetime:
    return datetime.now(UTC)


def _safe_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    forbidden = {"authorization", "api_key", "apikey", "cookie", "credential", "secret", "token"}
    result = dict(metadata)
    if any(any(part in str(key).casefold() for part in forbidden) for key in result):
        raise ValueError("secret-like metadata is not allowed in an LLM trace")
    return result


class StructuredLLMRuntime:
    def __init__(
        self,
        *,
        prompts: PromptRegistry | None = None,
        router: ModelRouter | None = None,
        clients: LLMClientRegistry | None = None,
        trace_store: LLMTraceStore | None = None,
        repository: Any | None = None,
        max_attempts: int = 2,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self.prompts = prompts or default_prompt_registry()
        self.router = router or StaticModelRouter()
        self.clients = clients or LLMClientRegistry()
        self.trace_store = trace_store or LLMTraceStore()
        self.repository = repository
        self.max_attempts = max_attempts
        self.records: list[LLMCallRecord] = []

    def _persist(self, record: LLMCallRecord) -> None:
        self.records.append(record)
        if self.repository is not None:
            self.repository.save_llm_call(record)

    def invoke(
        self,
        *,
        stage_run_id: str,
        task_type: str,
        prompt_id: str,
        prompt_version: str,
        schema: type[T],
        variables: Mapping[str, object],
        logical_request_id: str | None = None,
        reference_metadata: Mapping[str, Any] | None = None,
    ) -> T:
        spec = self.prompts.get(prompt_id, prompt_version)
        target = self.router.route(task_type)
        client = self.clients.get(target.provider)
        system_prompt, prompt = spec.render(
            {**variables, "schema_id": spec.schema_id, "schema_version": spec.schema_version}
        )
        logical_id = logical_request_id or f"logical-request-{uuid4().hex}"
        base_metadata = _safe_metadata(
            {
                "task_type": task_type,
                "prompt_id": prompt_id,
                "prompt_version": prompt_version,
                "schema_id": spec.schema_id,
                "schema_version": spec.schema_version,
                "logical_request_id": logical_id,
                **dict(reference_metadata or {}),
            }
        )
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            metadata = {**base_metadata, "attempt": attempt}
            request = LLMRequest(
                prompt=prompt,
                system_prompt=system_prompt,
                model=target.model,
                temperature=target.temperature,
                metadata=metadata,
            )
            request_ref = self.trace_store.write(
                "request",
                {
                    "system_prompt": system_prompt,
                    "prompt": prompt,
                    "model": target.model,
                    "provider": target.provider,
                    "temperature": target.temperature,
                    "metadata": metadata,
                    "schema_id": spec.schema_id,
                    "schema_version": spec.schema_version,
                },
            )
            started = _now()
            monotonic = time.perf_counter()
            response: LLMResponse | None = None
            response_ref: TraceRef | None = None
            try:
                response = client.complete(request)
                response_ref = self.trace_store.write(
                    "response",
                    {
                        "text": response.text,
                        "model": response.model,
                        "provider": response.provider,
                        "request_id": response.raw.get("request_id"),
                        "usage": response.usage,
                    },
                )
                raw = json.loads(response.text)
                if not isinstance(raw, dict):
                    raise StructuredOutputError("structured response must be a JSON object")
                parsed = schema.model_validate(raw)
                if getattr(parsed, "schema_id", spec.schema_id) != spec.schema_id:
                    raise StructuredOutputError(
                        "structured response schema_id does not match request"
                    )
                if getattr(parsed, "schema_version", spec.schema_version) != spec.schema_version:
                    raise StructuredOutputError(
                        "structured response schema_version does not match request"
                    )
                self._validate_references(parsed, variables)
                finished = _now()
                self._persist(
                    self._record(
                        stage_run_id,
                        request_ref,
                        response_ref,
                        started,
                        finished,
                        monotonic,
                        response,
                        logical_id,
                        attempt,
                        target,
                        spec,
                        LLMCallStatus.SUCCEEDED,
                        None,
                    )
                )
                return parsed
            except Exception as exc:
                last_error = exc
                finished = _now()
                self._persist(
                    self._record(
                        stage_run_id,
                        request_ref,
                        response_ref,
                        started,
                        finished,
                        monotonic,
                        response,
                        logical_id,
                        attempt,
                        target,
                        spec,
                        LLMCallStatus.FAILED,
                        exc,
                        metadata=(
                            exc.audit_metadata
                            if isinstance(exc, LLMProviderError)
                            else None
                        ),
                    )
                )
                if not is_retryable_llm_error(exc):
                    raise
        raise LLMRetryExhaustedError(
            f"structured request exhausted after {self.max_attempts} attempts: {last_error}"
        ) from last_error

    @staticmethod
    def _validate_references(parsed: BaseModel, variables: Mapping[str, object]) -> None:
        evidence_ids = {str(item) for item in variables.get("evidence_candidate_ids", ())}
        claim_ids = {str(item) for item in variables.get("claim_candidate_ids", ())}
        if isinstance(parsed, ClaimExtractionOutput):
            for item in parsed.items:
                unknown = set(item.evidence_candidate_ids) - evidence_ids
                if unknown:
                    raise StructuredOutputError(
                        f"unknown evidence candidate IDs: {sorted(unknown)}"
                    )
        if isinstance(parsed, EvidenceRelationOutput):
            for item in parsed.items:
                if (
                    item.evidence_candidate_id not in evidence_ids
                    or item.claim_candidate_id not in claim_ids
                ):
                    raise StructuredOutputError(
                        "relation references an input candidate that is not present"
                    )
        if isinstance(parsed, SourceDependencyOutput):
            source_ids = {str(item) for item in variables.get("source_ids", ())}
            for item in parsed.items:
                if (
                    item.source_id == item.parent_source_id
                    or item.source_id not in source_ids
                    or item.parent_source_id not in source_ids
                ):
                    raise StructuredOutputError("invalid source dependency reference")

    @staticmethod
    def _record(
        stage_run_id: str,
        request_ref: TraceRef,
        response_ref: TraceRef | None,
        started: datetime,
        finished: datetime,
        monotonic: float,
        response: LLMResponse | None,
        logical_id: str,
        attempt: int,
        target: Any,
        spec: Any,
        status: LLMCallStatus,
        error: Exception | None,
        metadata: Mapping[str, Any] | None = None,
    ) -> LLMCallRecord:
        usage = response.usage if response is not None else {}
        error_type = type(error).__name__ if error else None
        error_text = str(error) if error else None
        return LLMCallRecord(
            id=f"llm-call-{logical_id}-{attempt}",
            logical_request_id=logical_id,
            stage_run_id=stage_run_id,
            task_type=spec.task_type,
            provider=response.provider if response else target.provider,
            model=response.model if response else target.model,
            model_role=target.role.value,
            prompt_id=spec.prompt_id,
            prompt_version=spec.version,
            schema_id=spec.schema_id,
            schema_version=spec.schema_version,
            attempt=attempt,
            status=status,
            request_id=response.raw.get("request_id") if response else None,
            request_hash=request_ref.content_hash,
            response_hash=response_ref.content_hash if response_ref else None,
            request_ref=request_ref.ref,
            response_ref=response_ref.ref if response_ref else None,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            total_tokens=usage.get("total_tokens"),
            latency_ms=max(0.0, (finished - started).total_seconds() * 1000.0),
            started_at=started,
            finished_at=finished,
            error_type=error_type,
            error=error_text,
            metadata=safe_metadata(
                metadata,
                **(response.raw if response is not None else {}),
                monotonic_elapsed_ms=max(0.0, (time.perf_counter() - monotonic) * 1000.0),
            ),
        )


__all__ = [
    "ClaimExtractionOutput",
    "DependencyOutputItem",
    "EvidenceExtractionOutput",
    "EvidenceOutputItem",
    "EvidenceRelationOutput",
    "LLMRetryExhaustedError",
    "SourceDependencyOutput",
    "StructuredLLMRuntime",
    "StructuredOutputError",
    "StrictModel",
    "is_retryable_llm_error",
]

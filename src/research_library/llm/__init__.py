"""Internal LLM boundary and deterministic Phase 0 fake."""

from .client import FakeLLMClient, LLMClient, LLMRequest, LLMResponse, ScriptedFakeLLMClient
from .prompts import PromptRegistry, PromptSpec, default_prompt_registry
from .records import LLMCallAggregation, LLMCallRecord, LLMCallStatus, aggregate_llm_calls
from .routing import LLMClientRegistry, ModelRole, ModelRouter, ModelTarget, StaticModelRouter
from .structured import (
    ClaimExtractionOutput,
    EvidenceExtractionOutput,
    EvidenceRelationOutput,
    LLMRetryExhaustedError,
    SourceDependencyOutput,
    StructuredLLMRuntime,
    StructuredOutputError,
)
from .trace_store import LLMTraceIntegrityError, LLMTraceStore, TraceRef

__all__ = [
    "ClaimExtractionOutput",
    "EvidenceExtractionOutput",
    "EvidenceRelationOutput",
    "FakeLLMClient",
    "LLMCallRecord",
    "LLMCallAggregation",
    "LLMCallStatus",
    "LLMClient",
    "LLMClientRegistry",
    "LLMRequest",
    "LLMResponse",
    "LLMRetryExhaustedError",
    "LLMTraceIntegrityError",
    "LLMTraceStore",
    "ModelRole",
    "ModelRouter",
    "ModelTarget",
    "PromptRegistry",
    "PromptSpec",
    "ScriptedFakeLLMClient",
    "SourceDependencyOutput",
    "StaticModelRouter",
    "StructuredLLMRuntime",
    "StructuredOutputError",
    "TraceRef",
    "aggregate_llm_calls",
    "default_prompt_registry",
]

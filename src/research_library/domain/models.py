"""Domain dataclasses and state enums.

This module deliberately has no infrastructure imports.  Persistence adapters
translate these objects to and from their own storage representation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, StrEnum
from pathlib import PurePosixPath
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


def _id() -> str:
    return str(uuid4())


def _required(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _utc(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _mapping(value: Mapping[str, Any], name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return dict(value)


def _enum(value: Enum | str, enum_type: type[Enum], name: str) -> Enum:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except ValueError as exc:
        choices = ", ".join(str(item.value) for item in enum_type)
        raise ValueError(f"{name} must be one of: {choices}") from exc


def _confidence(value: float | None) -> float | None:
    if value is not None and not 0.0 <= value <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    return value


def _reasons(value: Mapping[str, list[str]], name: str = "reasons") -> dict[str, list[str]]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError(f"{name} must contain at least one reason category")
    normalized: dict[str, list[str]] = {}
    for key, reasons in value.items():
        _required(str(key), f"{name} category")
        if not isinstance(reasons, list) or not all(isinstance(item, str) for item in reasons):
            raise TypeError(f"{name}[{key!r}] must be a list of strings")
        normalized[str(key)] = list(reasons)
    if not any(reason.strip() for items in normalized.values() for reason in items):
        raise ValueError(f"{name} must contain at least one reason (non-empty)")
    return normalized


class SourceType(StrEnum):
    WEB = "web"
    PAPER = "paper"
    GITHUB = "github"
    PDF = "pdf"
    BOOK = "book"
    API = "api"
    DATASET = "dataset"
    OTHER = "other"


class EvidenceLinkType(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    QUALIFIES = "qualifies"
    MENTIONS = "mentions"


EvidenceRelation = EvidenceLinkType


class ContradictionType(StrEnum):
    DIRECT = "direct"
    TEMPORAL = "temporal"
    SCOPE = "scope"
    NUMERIC = "numeric"
    OTHER = "other"


class ContradictionSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ContradictionStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ResolvedClaimStatus(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    CONFLICTING = "conflicting"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    HISTORICAL_CHANGE = "historical_change"
    # Deprecated values remain readable for Phase 0 rows. Phase 1 writers must
    # use only the five canonical statuses above.
    PARTIALLY_SUPPORTED = "partially_supported"
    SUPERSEDED = "superseded"
    INVALID = "invalid"


class ResolutionInputRole(StrEnum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    QUALIFYING = "qualifying"
    REJECTED = "rejected"


class SourceDependencyRelation(StrEnum):
    REPOST_OF = "repost_of"
    MIRROR_OF = "mirror_of"
    DERIVED_FROM = "derived_from"
    CITES = "cites"
    SHARED_ORIGIN = "shared_origin"
    POSSIBLY_DEPENDENT = "possibly_dependent"


class KnowledgeAtomStatus(StrEnum):
    ACTIVE = "active"
    WITHHELD = "withheld"


class PipelineRunStatus(StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class StageRunStatus(StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Source:
    id: str = field(default_factory=_id)
    source_type: SourceType = SourceType.OTHER
    canonical_uri: str = ""
    title: str | None = None
    publisher: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        _required(self.id, "id")
        _required(self.canonical_uri, "canonical_uri")
        object.__setattr__(self, "source_type", _enum(self.source_type, SourceType, "source_type"))
        object.__setattr__(self, "metadata", _mapping(self.metadata, "metadata"))
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    id: str = field(default_factory=_id)
    source_id: str = ""
    retrieved_at: datetime = field(default_factory=utc_now)
    content_hash: str = ""
    content_ref: str = ""
    mime_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_by_stage_run_id: str | None = None

    def __post_init__(self) -> None:
        _required(self.id, "id")
        _required(self.source_id, "source_id")
        _utc(self.retrieved_at, "retrieved_at")
        if len(self.content_hash) != 64 or any(
            char not in "0123456789abcdef" for char in self.content_hash.lower()
        ):
            raise ValueError("content_hash must be a lowercase or uppercase SHA-256 hex digest")
        path = PurePosixPath(self.content_ref.replace("\\", "/"))
        if not self.content_ref or path.is_absolute() or ".." in path.parts:
            raise ValueError("content_ref must be a non-empty relative path")
        object.__setattr__(self, "retrieved_at", self.retrieved_at.astimezone(UTC))
        object.__setattr__(self, "content_hash", self.content_hash.lower())
        object.__setattr__(self, "metadata", _mapping(self.metadata, "metadata"))


@dataclass(frozen=True, slots=True)
class Evidence:
    id: str = field(default_factory=_id)
    snapshot_id: str = ""
    text: str = ""
    locator: str | None = None
    context: str | None = None
    extraction_method: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    created_by_stage_run_id: str | None = None

    def __post_init__(self) -> None:
        _required(self.id, "id")
        _required(self.snapshot_id, "snapshot_id")
        _required(self.text, "text")
        object.__setattr__(self, "metadata", _mapping(self.metadata, "metadata"))
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class Claim:
    id: str = field(default_factory=_id)
    statement: str = ""
    subject: str | None = None
    predicate: str | None = None
    object: str | None = None
    qualifiers: dict[str, Any] = field(default_factory=dict)
    temporal_scope: str | None = None
    extraction_confidence: float | None = None
    created_at: datetime = field(default_factory=utc_now)
    created_by_stage_run_id: str | None = None

    def __post_init__(self) -> None:
        _required(self.id, "id")
        _required(self.statement, "statement")
        _confidence(self.extraction_confidence)
        object.__setattr__(self, "qualifiers", _mapping(self.qualifiers, "qualifiers"))
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class ClaimGroup:
    id: str = field(default_factory=_id)
    canonical_key: str = ""
    name: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    created_by_stage_run_id: str | None = None
    canonical_statement: str | None = None
    subject: str | None = None
    predicate: str | None = None
    qualifiers: dict[str, Any] = field(default_factory=dict)
    temporal_scope: str | None = None

    def __post_init__(self) -> None:
        _required(self.id, "id")
        _required(self.canonical_key, "canonical_key")
        canonical_statement = self.canonical_statement or self.name or self.canonical_key
        _required(canonical_statement, "canonical_statement")
        object.__setattr__(self, "canonical_statement", canonical_statement)
        object.__setattr__(self, "qualifiers", _mapping(self.qualifiers, "qualifiers"))
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class ClaimGroupMembership:
    """An auditable claim-to-group normalization decision."""

    claim_group_id: str = ""
    claim_id: str = ""
    created_at: datetime | None = field(default_factory=utc_now)
    created_by_stage_run_id: str | None = None

    def __post_init__(self) -> None:
        _required(self.claim_group_id, "claim_group_id")
        _required(self.claim_id, "claim_id")
        if self.created_at is not None:
            object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))

    @property
    def id(self) -> str:
        return f"{self.claim_group_id}:{self.claim_id}"


@dataclass(frozen=True, slots=True)
class EvidenceLink:
    id: str = field(default_factory=_id)
    evidence_id: str = ""
    claim_id: str = ""
    relation_type: EvidenceLinkType = EvidenceLinkType.SUPPORTS
    rationale: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    created_by_stage_run_id: str | None = None

    def __post_init__(self) -> None:
        _required(self.id, "id")
        _required(self.evidence_id, "evidence_id")
        _required(self.claim_id, "claim_id")
        object.__setattr__(
            self, "relation_type", _enum(self.relation_type, EvidenceLinkType, "relation_type")
        )
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class Contradiction:
    id: str = field(default_factory=_id)
    claim_a_id: str = ""
    claim_b_id: str = ""
    type: ContradictionType = ContradictionType.DIRECT
    severity: ContradictionSeverity = ContradictionSeverity.MEDIUM
    reason: str = ""
    status: ContradictionStatus = ContradictionStatus.OPEN
    created_at: datetime = field(default_factory=utc_now)
    resolved_at: datetime | None = None
    created_by_stage_run_id: str | None = None

    def __post_init__(self) -> None:
        _required(self.id, "id")
        _required(self.claim_a_id, "claim_a_id")
        _required(self.claim_b_id, "claim_b_id")
        if self.claim_a_id == self.claim_b_id:
            raise ValueError("a contradiction needs two different claims")
        object.__setattr__(self, "type", _enum(self.type, ContradictionType, "type"))
        object.__setattr__(
            self, "severity", _enum(self.severity, ContradictionSeverity, "severity")
        )
        object.__setattr__(self, "status", _enum(self.status, ContradictionStatus, "status"))
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))
        if self.resolved_at is not None:
            object.__setattr__(self, "resolved_at", _utc(self.resolved_at, "resolved_at"))


@dataclass(frozen=True, slots=True)
class ResolvedClaim:
    id: str = field(default_factory=_id)
    claim_group_id: str = ""
    canonical_statement: str = ""
    status: ResolvedClaimStatus = ResolvedClaimStatus.UNRESOLVED
    confidence: float | None = None
    resolution_reason: str | None = None
    validity: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    created_by_stage_run_id: str | None = None
    resolution_decision_id: str | None = None
    confidence_assessment_id: str | None = None

    def __post_init__(self) -> None:
        _required(self.id, "id")
        _required(self.claim_group_id, "claim_group_id")
        _required(self.canonical_statement, "canonical_statement")
        object.__setattr__(self, "status", _enum(self.status, ResolvedClaimStatus, "status"))
        _confidence(self.confidence)
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class ResolutionDecision:
    id: str = field(default_factory=_id)
    claim_group_id: str = ""
    canonical_statement: str = ""
    status: ResolvedClaimStatus = ResolvedClaimStatus.UNRESOLVED
    resolution_reason: str = ""
    validity: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    created_by_stage_run_id: str | None = None

    def __post_init__(self) -> None:
        _required(self.id, "id")
        _required(self.claim_group_id, "claim_group_id")
        _required(self.canonical_statement, "canonical_statement")
        _required(self.resolution_reason, "resolution_reason")
        status = _enum(self.status, ResolvedClaimStatus, "status")
        if status.value not in {
            ResolvedClaimStatus.RESOLVED.value,
            ResolvedClaimStatus.UNRESOLVED.value,
            ResolvedClaimStatus.CONFLICTING.value,
            ResolvedClaimStatus.INSUFFICIENT_EVIDENCE.value,
            ResolvedClaimStatus.HISTORICAL_CHANGE.value,
        }:
            raise ValueError("ResolutionDecision status must use a canonical Phase 1 value")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class ResolutionClaimInput:
    id: str = field(default_factory=_id)
    resolution_decision_id: str = ""
    claim_id: str = ""
    role: ResolutionInputRole = ResolutionInputRole.SUPPORTING
    reason: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    created_by_stage_run_id: str | None = None

    def __post_init__(self) -> None:
        _required(self.id, "id")
        _required(self.resolution_decision_id, "resolution_decision_id")
        _required(self.claim_id, "claim_id")
        object.__setattr__(self, "role", _enum(self.role, ResolutionInputRole, "role"))
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class ResolutionEvidenceInput:
    id: str = field(default_factory=_id)
    resolution_decision_id: str = ""
    evidence_id: str = ""
    role: ResolutionInputRole = ResolutionInputRole.SUPPORTING
    reason: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    created_by_stage_run_id: str | None = None

    def __post_init__(self) -> None:
        _required(self.id, "id")
        _required(self.resolution_decision_id, "resolution_decision_id")
        _required(self.evidence_id, "evidence_id")
        object.__setattr__(self, "role", _enum(self.role, ResolutionInputRole, "role"))
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class ConfidenceAssessment:
    id: str = field(default_factory=_id)
    resolution_decision_id: str = ""
    policy_version: str = ""
    source_quality: float = 0.0
    evidence_directness: float = 0.0
    source_independence: float = 0.0
    agreement: float = 0.0
    freshness: float = 0.0
    extraction_confidence: float = 0.0
    contradiction_penalty: float = 0.0
    publish_cap: float | None = None
    evidence_floor_met: bool = False
    score: float = 0.0
    reasons: dict[str, list[str]] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    created_by_stage_run_id: str | None = None

    def __post_init__(self) -> None:
        _required(self.id, "id")
        _required(self.resolution_decision_id, "resolution_decision_id")
        _required(self.policy_version, "policy_version")
        for name in (
            "source_quality",
            "evidence_directness",
            "source_independence",
            "agreement",
            "freshness",
            "extraction_confidence",
            "contradiction_penalty",
            "score",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if not isinstance(self.evidence_floor_met, bool):
            raise TypeError("evidence_floor_met must be bool")
        _confidence(self.publish_cap)
        object.__setattr__(self, "reasons", _reasons(self.reasons))
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class SourceDependency:
    id: str = field(default_factory=_id)
    source_id: str = ""
    parent_source_id: str = ""
    relation_type: SourceDependencyRelation = SourceDependencyRelation.POSSIBLY_DEPENDENT
    dependency_group: str | None = None
    independence_score: float | None = None
    reason: str | None = None
    signals: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = field(default_factory=utc_now)
    created_by_stage_run_id: str | None = None

    def __post_init__(self) -> None:
        _required(self.id, "id")
        _required(self.source_id, "source_id")
        _required(self.parent_source_id, "parent_source_id")
        if self.source_id == self.parent_source_id:
            raise ValueError("a source dependency cannot refer to itself")
        object.__setattr__(
            self,
            "relation_type",
            _enum(self.relation_type, SourceDependencyRelation, "relation_type"),
        )
        _confidence(self.independence_score)
        object.__setattr__(self, "signals", _mapping(self.signals, "signals"))
        if self.created_at is not None:
            object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class KnowledgeAtom:
    id: str = field(default_factory=_id)
    resolved_claim_id: str = ""
    statement: str = ""
    confidence: float | None = None
    qualifiers: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    created_by_stage_run_id: str | None = None
    subject: str | None = None
    predicate: str | None = None
    object: str | None = None
    status: KnowledgeAtomStatus = KnowledgeAtomStatus.WITHHELD
    validity: str | None = None

    def __post_init__(self) -> None:
        _required(self.id, "id")
        _required(self.resolved_claim_id, "resolved_claim_id")
        _required(self.statement, "statement")
        _confidence(self.confidence)
        object.__setattr__(self, "status", _enum(self.status, KnowledgeAtomStatus, "status"))
        object.__setattr__(self, "qualifiers", _mapping(self.qualifiers, "qualifiers"))
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class PipelineRun:
    id: str = field(default_factory=_id)
    pipeline_version: str = "phase0"
    status: PipelineRunStatus = PipelineRunStatus.STARTED
    started_at: datetime = field(default_factory=utc_now)
    finished_at: datetime | None = None
    input_ref: str | None = None
    output_ref: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _required(self.id, "id")
        _required(self.pipeline_version, "pipeline_version")
        object.__setattr__(self, "status", _enum(self.status, PipelineRunStatus, "status"))
        object.__setattr__(self, "started_at", _utc(self.started_at, "started_at"))
        if self.finished_at is not None:
            object.__setattr__(self, "finished_at", _utc(self.finished_at, "finished_at"))
        object.__setattr__(self, "metadata", _mapping(self.metadata, "metadata"))
        if self.status is PipelineRunStatus.STARTED:
            if (
                self.finished_at is not None
                or self.error is not None
                or self.output_ref is not None
            ):
                raise ValueError(
                    "STARTED PipelineRun cannot have finished_at, error, or output_ref"
                )
        elif self.status is PipelineRunStatus.SUCCEEDED:
            if self.finished_at is None:
                raise ValueError("SUCCEEDED PipelineRun requires finished_at")
            if self.error is not None:
                raise ValueError("SUCCEEDED PipelineRun cannot have error")
            if self.finished_at < self.started_at:
                raise ValueError("PipelineRun finished_at must be >= started_at")
        elif self.status is PipelineRunStatus.FAILED:
            if self.finished_at is None:
                raise ValueError("FAILED PipelineRun requires finished_at")
            if not self.error or not self.error.strip():
                raise ValueError("FAILED PipelineRun requires a non-empty error")
            if self.finished_at < self.started_at:
                raise ValueError("PipelineRun finished_at must be >= started_at")


@dataclass(frozen=True, slots=True)
class StageRun:
    id: str = field(default_factory=_id)
    pipeline_run_id: str = ""
    stage_name: str = ""
    stage_version: str = "phase0"
    status: StageRunStatus = StageRunStatus.STARTED
    model: str | None = None
    provider: str | None = None
    prompt_id: str | None = None
    prompt_version: str | None = None
    input_ref: str | None = None
    output_ref: str | None = None
    started_at: datetime = field(default_factory=utc_now)
    finished_at: datetime | None = None
    error_type: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        _required(self.id, "id")
        _required(self.pipeline_run_id, "pipeline_run_id")
        _required(self.stage_name, "stage_name")
        _required(self.stage_version, "stage_version")
        object.__setattr__(self, "status", _enum(self.status, StageRunStatus, "status"))
        object.__setattr__(self, "started_at", _utc(self.started_at, "started_at"))
        if self.finished_at is not None:
            object.__setattr__(self, "finished_at", _utc(self.finished_at, "finished_at"))
        if self.status is StageRunStatus.STARTED:
            if (
                self.finished_at is not None
                or self.error is not None
                or self.error_type is not None
            ):
                raise ValueError("STARTED StageRun cannot have finished_at, error, or error_type")
        elif self.status is StageRunStatus.SUCCEEDED:
            if self.finished_at is None:
                raise ValueError("SUCCEEDED StageRun requires finished_at")
            if self.error is not None or self.error_type is not None:
                raise ValueError("SUCCEEDED StageRun cannot have error or error_type")
            if self.finished_at < self.started_at:
                raise ValueError("StageRun finished_at must be >= started_at")
        elif self.status is StageRunStatus.FAILED:
            if self.finished_at is None:
                raise ValueError("FAILED StageRun requires finished_at")
            if not self.error or not self.error.strip():
                raise ValueError("FAILED StageRun requires a non-empty error")
            if not self.error_type or not self.error_type.strip():
                raise ValueError("FAILED StageRun requires a non-empty error_type")
            if self.finished_at < self.started_at:
                raise ValueError("StageRun finished_at must be >= started_at")

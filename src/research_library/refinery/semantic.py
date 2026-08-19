"""Provider-neutral semantic candidate contracts for Phase 1B and later phases."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from research_library.domain import EvidenceLinkType, SourceDependencyRelation


@dataclass(frozen=True, slots=True)
class EvidenceCandidate:
    candidate_id: str
    snapshot_id: str
    text: str
    locator: str | None = None
    context: str | None = None
    extraction_method: str = "semantic-backend"


@dataclass(frozen=True, slots=True)
class ClaimCandidate:
    candidate_id: str
    statement: str
    subject: str | None
    predicate: str | None
    object: str | None
    qualifiers: Mapping[str, Any] = field(default_factory=dict)
    temporal_scope: str | None = None
    extraction_confidence: float = 0.0
    evidence_candidate_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EvidenceRelationCandidate:
    evidence_candidate_id: str
    claim_candidate_id: str
    relation_type: EvidenceLinkType
    rationale: str


@dataclass(frozen=True, slots=True)
class DependencySignal:
    source_id: str
    parent_source_id: str
    relation_type: SourceDependencyRelation
    dependency_group: str | None
    independence_score: float | None
    reason: str
    signals: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SemanticBatch:
    evidence: tuple[EvidenceCandidate, ...]
    claims: tuple[ClaimCandidate, ...]
    relations: tuple[EvidenceRelationCandidate, ...]
    dependencies: tuple[DependencySignal, ...] = ()
    reference_time: datetime | None = None


@runtime_checkable
class SemanticBackend(Protocol):
    """Replaceable semantic seam; implementations return candidates, not rows."""

    def seed_inputs(
        self, repository: Any, fixture_id: str, snapshot_keys: tuple[str, ...] | None = None
    ) -> tuple[Any, ...]: ...

    def collect(self, fixture_id: str, snapshot_ids: tuple[str, ...]) -> SemanticBatch: ...


__all__ = [
    "ClaimCandidate",
    "DependencySignal",
    "EvidenceCandidate",
    "EvidenceRelationCandidate",
    "SemanticBackend",
    "SemanticBatch",
]

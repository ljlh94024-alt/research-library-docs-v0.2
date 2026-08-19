"""Typed boundaries for the Phase 1A Knowledge Refinery stages.

These contracts deliberately contain identifiers and execution context only.
Semantic extraction, linking, contradiction detection, resolution, confidence,
and atom-building policies belong to later phases.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol, TypeVar, runtime_checkable

from research_library.storage.repository import Repository

CANONICAL_STAGE_NAMES = (
    "evidence_extract",
    "claim_extract",
    "normalize",
    "evidence_link",
    "independence",
    "contradiction",
    "resolve",
    "confidence",
    "atom_build",
)

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


def _ids(value: Iterable[str], name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{name} must be an iterable of IDs, not a string")
    try:
        normalized = tuple(value)
    except TypeError as exc:
        raise TypeError(f"{name} must be an iterable of IDs") from exc
    for index, item in enumerate(normalized):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{name}[{index}] must be a non-empty string")
    return normalized


def _id(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class EvidenceExtractInput:
    snapshot_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_ids", _ids(self.snapshot_ids, "snapshot_ids"))


@dataclass(frozen=True, slots=True)
class EvidenceExtractOutput:
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_ids", _ids(self.evidence_ids, "evidence_ids"))


@dataclass(frozen=True, slots=True)
class ClaimExtractInput:
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_ids", _ids(self.evidence_ids, "evidence_ids"))


@dataclass(frozen=True, slots=True)
class ClaimExtractOutput:
    claim_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_ids", _ids(self.claim_ids, "claim_ids"))


@dataclass(frozen=True, slots=True)
class NormalizeInput:
    claim_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_ids", _ids(self.claim_ids, "claim_ids"))


@dataclass(frozen=True, slots=True)
class NormalizeOutput:
    claim_group_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "claim_group_ids", _ids(self.claim_group_ids, "claim_group_ids")
        )


@dataclass(frozen=True, slots=True)
class EvidenceLinkInput:
    claim_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_ids", _ids(self.claim_ids, "claim_ids"))
        object.__setattr__(self, "evidence_ids", _ids(self.evidence_ids, "evidence_ids"))


@dataclass(frozen=True, slots=True)
class EvidenceLinkOutput:
    evidence_link_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "evidence_link_ids", _ids(self.evidence_link_ids, "evidence_link_ids")
        )


@dataclass(frozen=True, slots=True)
class IndependenceInput:
    source_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_ids", _ids(self.source_ids, "source_ids"))


@dataclass(frozen=True, slots=True)
class IndependenceOutput:
    source_dependency_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_dependency_ids",
            _ids(self.source_dependency_ids, "source_dependency_ids"),
        )


@dataclass(frozen=True, slots=True)
class ContradictionInput:
    claim_group_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "claim_group_ids", _ids(self.claim_group_ids, "claim_group_ids")
        )


@dataclass(frozen=True, slots=True)
class ContradictionOutput:
    contradiction_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "contradiction_ids", _ids(self.contradiction_ids, "contradiction_ids")
        )


@dataclass(frozen=True, slots=True)
class ResolveInput:
    claim_group_ids: tuple[str, ...]
    contradiction_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "claim_group_ids", _ids(self.claim_group_ids, "claim_group_ids")
        )
        object.__setattr__(
            self, "contradiction_ids", _ids(self.contradiction_ids, "contradiction_ids")
        )


@dataclass(frozen=True, slots=True)
class ResolveOutput:
    resolution_decision_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "resolution_decision_ids",
            _ids(self.resolution_decision_ids, "resolution_decision_ids"),
        )


@dataclass(frozen=True, slots=True)
class ConfidenceInput:
    resolution_decision_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "resolution_decision_ids",
            _ids(self.resolution_decision_ids, "resolution_decision_ids"),
        )


@dataclass(frozen=True, slots=True)
class ConfidenceOutput:
    confidence_assessment_ids: tuple[str, ...]
    resolved_claim_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "confidence_assessment_ids",
            _ids(self.confidence_assessment_ids, "confidence_assessment_ids"),
        )
        object.__setattr__(
            self, "resolved_claim_ids", _ids(self.resolved_claim_ids, "resolved_claim_ids")
        )


@dataclass(frozen=True, slots=True)
class AtomBuildInput:
    resolved_claim_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "resolved_claim_ids", _ids(self.resolved_claim_ids, "resolved_claim_ids")
        )


@dataclass(frozen=True, slots=True)
class AtomBuildOutput:
    knowledge_atom_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "knowledge_atom_ids", _ids(self.knowledge_atom_ids, "knowledge_atom_ids")
        )


@dataclass(frozen=True, slots=True)
class StageContext:
    pipeline_run_id: str
    stage_run_id: str
    repository: Repository

    def __post_init__(self) -> None:
        _id(self.pipeline_run_id, "pipeline_run_id")
        _id(self.stage_run_id, "stage_run_id")


@runtime_checkable
class RefineryStage(Protocol[InputT, OutputT]):
    """Structural execution contract implemented by each refinery stage."""

    name: str
    version: str

    def run(self, context: StageContext, input: InputT) -> OutputT: ...

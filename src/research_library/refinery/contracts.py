"""Typed boundaries for the Phase 1A Knowledge Refinery stages.

These contracts deliberately contain identifiers and execution context only.
Semantic extraction, linking, contradiction detection, resolution, confidence,
and atom-building policies belong to later phases.
"""

from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True, slots=True)
class EvidenceExtractInput:
    snapshot_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceExtractOutput:
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ClaimExtractInput:
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ClaimExtractOutput:
    claim_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NormalizeInput:
    claim_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NormalizeOutput:
    claim_group_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceLinkInput:
    claim_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceLinkOutput:
    evidence_link_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IndependenceInput:
    source_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IndependenceOutput:
    source_dependency_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ContradictionInput:
    claim_group_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ContradictionOutput:
    contradiction_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResolveInput:
    claim_group_ids: tuple[str, ...]
    contradiction_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResolveOutput:
    resolution_decision_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConfidenceInput:
    resolution_decision_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConfidenceOutput:
    confidence_assessment_ids: tuple[str, ...]
    resolved_claim_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AtomBuildInput:
    resolved_claim_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AtomBuildOutput:
    knowledge_atom_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StageContext:
    pipeline_run_id: str
    stage_run_id: str
    repository: Repository

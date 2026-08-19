"""Repository contracts and provenance result types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from research_library.domain import (
    Claim,
    ClaimGroup,
    ClaimGroupMembership,
    ConfidenceAssessment,
    Contradiction,
    Evidence,
    EvidenceLink,
    KnowledgeAtom,
    PipelineRun,
    ResolutionClaimInput,
    ResolutionDecision,
    ResolutionEvidenceInput,
    ResolvedClaim,
    Source,
    SourceDependency,
    SourceSnapshot,
    StageRun,
)


@dataclass(frozen=True, slots=True)
class ProvenanceChain:
    """The persisted chain below one KnowledgeAtom."""

    atom: KnowledgeAtom
    resolved_claim: ResolvedClaim
    claim_group: ClaimGroup
    claims: tuple[Claim, ...]
    evidence_links: tuple[EvidenceLink, ...]
    evidences: tuple[Evidence, ...]
    snapshots: tuple[SourceSnapshot, ...]
    sources: tuple[Source, ...]
    claim_group_memberships: tuple[ClaimGroupMembership, ...] = ()
    resolution_decision: ResolutionDecision | None = None
    resolution_claim_inputs: tuple[ResolutionClaimInput, ...] = ()
    resolution_evidence_inputs: tuple[ResolutionEvidenceInput, ...] = ()
    confidence_assessment: ConfidenceAssessment | None = None

    @property
    def claim(self) -> Claim:
        return self.claims[0]

    @property
    def evidence(self) -> Evidence:
        return self.evidences[0]

    @property
    def snapshot(self) -> SourceSnapshot:
        return self.snapshots[0]

    @property
    def source(self) -> Source:
        return self.sources[0]


@dataclass(frozen=True, slots=True)
class ProcessingStep:
    entity_type: str
    entity_id: str
    stage_run: StageRun
    pipeline_run: PipelineRun


@dataclass(frozen=True, slots=True)
class ProcessingGap:
    entity_type: str
    entity_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class ProcessingProvenance:
    atom_id: str
    steps: tuple[ProcessingStep, ...]
    gaps: tuple[ProcessingGap, ...] = ()

    @property
    def is_complete(self) -> bool:
        return not self.gaps


class Repository(Protocol):
    """Storage boundary used by application and pipeline code."""

    def save_source(self, source: Source) -> Source: ...

    def get_source(self, source_id: str) -> Source | None: ...

    def save_snapshot(self, snapshot: SourceSnapshot) -> SourceSnapshot: ...

    def get_snapshot(self, snapshot_id: str) -> SourceSnapshot | None: ...

    def create_snapshot(
        self,
        source_id: str,
        content: bytes | str,
        *,
        snapshot_id: str | None = None,
        retrieved_at: datetime | None = None,
        mime_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        created_by_stage_run_id: str | None = None,
    ) -> SourceSnapshot: ...

    def read_snapshot(self, snapshot_id: str) -> bytes: ...

    def save_evidence(self, evidence: Evidence) -> Evidence: ...

    def get_evidence(self, evidence_id: str) -> Evidence | None: ...

    def save_claim(self, claim: Claim) -> Claim: ...

    def get_claim(self, claim_id: str) -> Claim | None: ...

    def save_claim_group(self, claim_group: ClaimGroup) -> ClaimGroup: ...

    def get_claim_group(self, group_id: str) -> ClaimGroup | None: ...

    def save_claim_group_membership(
        self, membership: ClaimGroupMembership
    ) -> ClaimGroupMembership: ...

    def save_claim_group_member(
        self, membership: ClaimGroupMembership
    ) -> ClaimGroupMembership: ...

    def get_claim_group_membership(
        self, claim_group_id: str, claim_id: str
    ) -> ClaimGroupMembership | None: ...

    def list_claim_group_memberships(
        self, claim_group_id: str | None = None, claim_id: str | None = None
    ) -> tuple[ClaimGroupMembership, ...]: ...

    def add_claim_to_group(self, claim_group_id: str, claim_id: str) -> ClaimGroupMembership: ...

    def list_claims_for_group(self, claim_group_id: str) -> tuple[Claim, ...]: ...

    def save_evidence_link(self, link: EvidenceLink) -> EvidenceLink: ...

    def get_evidence_link(self, link_id: str) -> EvidenceLink | None: ...

    def list_evidence_links_for_claim(self, claim_id: str) -> tuple[EvidenceLink, ...]: ...

    def list_evidence_links_for_evidence(self, evidence_id: str) -> tuple[EvidenceLink, ...]: ...

    def save_contradiction(self, contradiction: Contradiction) -> Contradiction: ...

    def get_contradiction(self, contradiction_id: str) -> Contradiction | None: ...

    def save_resolved_claim(self, resolved_claim: ResolvedClaim) -> ResolvedClaim: ...

    def get_resolved_claim(self, resolved_claim_id: str) -> ResolvedClaim | None: ...

    def save_source_dependency(self, dependency: SourceDependency) -> SourceDependency: ...

    def get_source_dependency(self, dependency_id: str) -> SourceDependency | None: ...

    def list_source_dependencies(
        self,
        source_id: str | None = None,
        dependency_group: str | None = None,
    ) -> tuple[SourceDependency, ...]: ...

    def save_resolution_decision(self, decision: ResolutionDecision) -> ResolutionDecision: ...

    def get_resolution_decision(self, decision_id: str) -> ResolutionDecision | None: ...

    def list_resolution_decisions_for_group(
        self, claim_group_id: str
    ) -> tuple[ResolutionDecision, ...]: ...

    def save_resolution_claim_input(self, item: ResolutionClaimInput) -> ResolutionClaimInput: ...

    def list_resolution_claim_inputs(
        self, resolution_decision_id: str
    ) -> tuple[ResolutionClaimInput, ...]: ...

    def save_resolution_evidence_input(
        self, item: ResolutionEvidenceInput
    ) -> ResolutionEvidenceInput: ...

    def list_resolution_evidence_inputs(
        self, resolution_decision_id: str
    ) -> tuple[ResolutionEvidenceInput, ...]: ...

    def save_confidence_assessment(
        self, assessment: ConfidenceAssessment
    ) -> ConfidenceAssessment: ...

    def get_confidence_assessment(
        self, assessment_id: str
    ) -> ConfidenceAssessment | None: ...

    def list_confidence_assessments_for_decision(
        self, resolution_decision_id: str
    ) -> tuple[ConfidenceAssessment, ...]: ...

    def save_knowledge_atom(self, atom: KnowledgeAtom) -> KnowledgeAtom: ...

    def get_knowledge_atom(self, atom_id: str) -> KnowledgeAtom | None: ...

    def get_provenance(self, atom_id: str) -> ProvenanceChain: ...

    def get_processing_provenance(self, atom_id: str) -> ProcessingProvenance: ...

    def save_pipeline_run(self, run: PipelineRun) -> PipelineRun: ...

    def save_stage_run(self, run: StageRun) -> StageRun: ...

    def get_pipeline_run(self, run_id: str) -> PipelineRun | None: ...

    def get_stage_run(self, stage_run_id: str) -> StageRun | None: ...

    def list_pipeline_runs(self) -> tuple[PipelineRun, ...]: ...

    def list_stage_runs(self, pipeline_run_id: str | None = None) -> tuple[StageRun, ...]: ...

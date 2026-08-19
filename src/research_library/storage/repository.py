"""Repository contracts and provenance result types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from research_library.domain import (
    Claim,
    ClaimGroup,
    Contradiction,
    Evidence,
    EvidenceLink,
    KnowledgeAtom,
    PipelineRun,
    ResolvedClaim,
    Source,
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


class Repository(Protocol):
    """Storage boundary used by application and pipeline code."""

    def save_source(self, source: Source) -> Source: ...

    def get_source(self, source_id: str) -> Source | None: ...

    def save_snapshot(self, snapshot: SourceSnapshot) -> SourceSnapshot: ...

    def get_snapshot(self, snapshot_id: str) -> SourceSnapshot | None: ...

    def save_evidence(self, evidence: Evidence) -> Evidence: ...

    def get_evidence(self, evidence_id: str) -> Evidence | None: ...

    def save_claim(self, claim: Claim) -> Claim: ...

    def get_claim(self, claim_id: str) -> Claim | None: ...

    def save_claim_group(self, claim_group: ClaimGroup) -> ClaimGroup: ...

    def save_evidence_link(self, link: EvidenceLink) -> EvidenceLink: ...

    def save_contradiction(self, contradiction: Contradiction) -> Contradiction: ...

    def save_resolved_claim(self, resolved_claim: ResolvedClaim) -> ResolvedClaim: ...

    def save_knowledge_atom(self, atom: KnowledgeAtom) -> KnowledgeAtom: ...

    def get_knowledge_atom(self, atom_id: str) -> KnowledgeAtom | None: ...

    def get_provenance(self, atom_id: str) -> ProvenanceChain: ...

    def save_pipeline_run(self, run: PipelineRun) -> PipelineRun: ...

    def save_stage_run(self, run: StageRun) -> StageRun: ...

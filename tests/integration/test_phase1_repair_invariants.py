from datetime import UTC, datetime

import pytest
from tests.integration.test_phase1_repository import _phase1_chain

from research_library.domain import (
    Claim,
    ClaimGroup,
    ClaimGroupMembership,
    ConfidenceAssessment,
    Evidence,
    EvidenceLink,
    KnowledgeAtom,
    KnowledgeAtomStatus,
    PipelineRun,
    ResolutionDecision,
    ResolvedClaim,
    Source,
    SourceDependency,
    StageRun,
)
from research_library.storage import StorageIntegrityError

NOW = datetime(2026, 8, 19, tzinfo=UTC)


def test_phase1_outputs_reject_wrong_canonical_stage_owners(repository) -> None:
    chain = _phase1_chain(repository)
    stages = chain["stages"]
    wrong = stages["resolve"].id

    parent = repository.save_source(
        Source(id="ownership-parent", canonical_uri="https://example.test/parent")
    )
    source = repository.save_source(
        Source(id="ownership-source", canonical_uri="https://example.test/source")
    )
    with pytest.raises(StorageIntegrityError, match="SourceDependency.*independence"):
        repository.save_source_dependency(
            SourceDependency(
                id="ownership-dependency",
                source_id=source.id,
                parent_source_id=parent.id,
                created_at=NOW,
                created_by_stage_run_id=wrong,
            )
        )
    with pytest.raises(StorageIntegrityError, match="SourceSnapshot.*evidence_extract"):
        repository.create_snapshot(
            source.id,
            b"wrong owner",
            snapshot_id="ownership-snapshot",
            created_by_stage_run_id=wrong,
        )
    with pytest.raises(StorageIntegrityError, match="Evidence.*evidence_extract"):
        repository.save_evidence(
            Evidence(
                id="ownership-evidence",
                snapshot_id=chain["snapshot"].id,
                text="wrong owner",
                created_by_stage_run_id=wrong,
            )
        )
    with pytest.raises(StorageIntegrityError, match="Claim.*claim_extract"):
        repository.save_claim(
            Claim(
                id="ownership-claim",
                statement="wrong owner",
                created_by_stage_run_id=wrong,
            )
        )
    with pytest.raises(StorageIntegrityError, match="ClaimGroup.*normalize"):
        repository.save_claim_group(
            ClaimGroup(
                id="ownership-group",
                canonical_key="ownership-group-key",
                canonical_statement="wrong owner",
                created_by_stage_run_id=wrong,
            )
        )

    member_claim = repository.save_claim(
        Claim(
            id="ownership-member-claim",
            statement="membership claim",
            created_by_stage_run_id=stages["claim_extract"].id,
        )
    )
    with pytest.raises(StorageIntegrityError, match="ClaimGroupMembership.*normalize"):
        repository.save_claim_group_membership(
            ClaimGroupMembership(
                claim_group_id=chain["group"].id,
                claim_id=member_claim.id,
                created_by_stage_run_id=wrong,
            )
        )
    with pytest.raises(StorageIntegrityError, match="EvidenceLink.*evidence_link"):
        repository.save_evidence_link(
            EvidenceLink(
                id="ownership-link",
                evidence_id=chain["evidence"].id,
                claim_id=chain["claim"].id,
                created_by_stage_run_id=wrong,
            )
        )
    with pytest.raises(StorageIntegrityError, match="ResolutionDecision.*resolve"):
        repository.save_resolution_decision(
            ResolutionDecision(
                id="ownership-decision",
                claim_group_id=chain["group"].id,
                canonical_statement=chain["decision"].canonical_statement,
                resolution_reason="wrong owner",
                created_by_stage_run_id=stages["confidence"].id,
            )
        )
    with pytest.raises(StorageIntegrityError, match="ConfidenceAssessment.*confidence"):
        repository.save_confidence_assessment(
            ConfidenceAssessment(
                id="ownership-assessment",
                resolution_decision_id=chain["decision"].id,
                policy_version="phase1a-test",
                score=0.5,
                reasons={"fixture": ["wrong owner"]},
                created_by_stage_run_id=wrong,
            )
        )
    with pytest.raises(StorageIntegrityError, match="ResolvedClaim.*confidence"):
        repository.save_resolved_claim(
            ResolvedClaim(
                id="ownership-resolved",
                claim_group_id=chain["group"].id,
                canonical_statement=chain["decision"].canonical_statement,
                status=chain["decision"].status,
                confidence=chain["assessment"].score,
                resolution_decision_id=chain["decision"].id,
                confidence_assessment_id=chain["assessment"].id,
                created_by_stage_run_id=stages["atom_build"].id,
            )
        )
    with pytest.raises(StorageIntegrityError, match="KnowledgeAtom.*atom_build"):
        repository.save_knowledge_atom(
            KnowledgeAtom(
                id="ownership-atom",
                resolved_claim_id=chain["resolved"].id,
                statement=chain["resolved"].canonical_statement,
                confidence=chain["resolved"].confidence,
                status=KnowledgeAtomStatus.ACTIVE,
                created_by_stage_run_id=stages["confidence"].id,
            )
        )


def test_phase1_only_resolution_objects_require_canonical_owner_even_outside_pipeline_gate(
    repository,
) -> None:
    pipeline = repository.save_pipeline_run(
        PipelineRun(id="phase0-resolution-pipeline", pipeline_version="phase0")
    )
    stage = repository.save_stage_run(
        StageRun(id="phase0-resolution-stage", pipeline_run_id=pipeline.id, stage_name="fixture")
    )
    group = repository.save_claim_group(
        ClaimGroup(id="phase0-resolution-group", canonical_key="phase0-resolution")
    )
    with pytest.raises(StorageIntegrityError, match="ResolutionDecision.*resolve"):
        repository.save_resolution_decision(
            ResolutionDecision(
                id="phase0-resolution-decision",
                claim_group_id=group.id,
                canonical_statement="fact",
                resolution_reason="fixture",
                created_by_stage_run_id=stage.id,
            )
        )

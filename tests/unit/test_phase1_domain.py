from datetime import UTC, datetime

import pytest

from research_library.domain import (
    ClaimGroup,
    ConfidenceAssessment,
    KnowledgeAtom,
    KnowledgeAtomStatus,
    ResolutionDecision,
    ResolvedClaimStatus,
    SourceDependency,
    SourceDependencyRelation,
)

NOW = datetime(2026, 8, 19, tzinfo=UTC)


def test_claim_group_persists_normalized_comparison_fields() -> None:
    group = ClaimGroup(
        id="group-1",
        canonical_key="release-year",
        canonical_statement="The release year is variable",
        subject="project",
        predicate="release_year",
        qualifiers={"region": "global"},
        temporal_scope="2025-2026",
        created_at=NOW,
    )
    assert group.canonical_statement == "The release year is variable"
    assert group.qualifiers == {"region": "global"}


def test_canonical_and_legacy_resolved_statuses_are_distinguishable() -> None:
    assert ResolvedClaimStatus.HISTORICAL_CHANGE.value == "historical_change"
    assert ResolvedClaimStatus.PARTIALLY_SUPPORTED.value == "partially_supported"
    with pytest.raises(ValueError, match="canonical Phase 1"):
        ResolutionDecision(
            claim_group_id="group-1",
            canonical_statement="fact",
            status=ResolvedClaimStatus.PARTIALLY_SUPPORTED,
            resolution_reason="legacy status must not be newly written",
        )


def test_resolution_decision_requires_reason_and_utc_time() -> None:
    with pytest.raises(ValueError, match="resolution_reason"):
        ResolutionDecision(claim_group_id="group-1", canonical_statement="fact")
    with pytest.raises(ValueError, match="timezone-aware"):
        ResolutionDecision(
            claim_group_id="group-1",
            canonical_statement="fact",
            resolution_reason="reason",
            created_at=datetime(2026, 8, 19),
        )


def test_confidence_assessment_requires_components_and_explainable_reasons() -> None:
    assessment = ConfidenceAssessment(
        resolution_decision_id="decision-1",
        policy_version="phase1a-v1",
        source_quality=0.9,
        evidence_directness=0.8,
        source_independence=0.7,
        agreement=0.9,
        freshness=0.8,
        extraction_confidence=0.95,
        contradiction_penalty=0.1,
        publish_cap=0.85,
        evidence_floor_met=True,
        score=0.8,
        reasons={"agreement": ["two independent supporting claims"]},
        created_at=NOW,
    )
    assert assessment.reasons["agreement"]
    with pytest.raises(ValueError, match="between 0 and 1"):
        ConfidenceAssessment(
            resolution_decision_id="decision-1",
            policy_version="phase1a-v1",
            score=1.01,
            reasons={"score": ["bad"]},
        )
    with pytest.raises(ValueError, match="at least one reason"):
        ConfidenceAssessment(
            resolution_decision_id="decision-1",
            policy_version="phase1a-v1",
            reasons={"score": []},
        )


def test_source_dependency_rejects_self_reference_and_accepts_relation() -> None:
    with pytest.raises(ValueError, match="cannot refer to itself"):
        SourceDependency(source_id="source-1", parent_source_id="source-1")
    dependency = SourceDependency(
        source_id="source-1",
        parent_source_id="source-2",
        relation_type=SourceDependencyRelation.MIRROR_OF,
        independence_score=0.1,
        reason="same upstream publication",
        signals={"same_domain": True},
    )
    assert dependency.relation_type is SourceDependencyRelation.MIRROR_OF


def test_knowledge_atom_has_explicit_publication_states() -> None:
    atom = KnowledgeAtom(
        resolved_claim_id="resolved-1",
        statement="fact",
        status=KnowledgeAtomStatus.ACTIVE,
        subject="subject",
        predicate="predicate",
        object="object",
        confidence=0.8,
    )
    assert atom.status is KnowledgeAtomStatus.ACTIVE

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from research_library.domain import (
    Claim,
    ClaimGroup,
    ConfidenceAssessment,
    Evidence,
    EvidenceLink,
    KnowledgeAtom,
    KnowledgeAtomStatus,
    PipelineRun,
    ResolutionClaimInput,
    ResolutionDecision,
    ResolutionEvidenceInput,
    ResolutionInputRole,
    ResolvedClaim,
    ResolvedClaimStatus,
    Source,
    SourceDependency,
    StageRun,
)
from research_library.storage import ImmutableRecordError, StorageIntegrityError

NOW = datetime(2026, 8, 19, tzinfo=UTC)


def _phase1_chain(repository, *, decision_status=ResolvedClaimStatus.RESOLVED):
    pipeline = repository.save_pipeline_run(PipelineRun(id="phase1-pipeline", started_at=NOW))
    stage = repository.save_stage_run(
        StageRun(
            id="phase1-stage",
            pipeline_run_id=pipeline.id,
            stage_name="resolve",
            started_at=NOW,
        )
    )
    source = repository.save_source(
        Source(id="phase1-source", canonical_uri="https://example.test/phase1", created_at=NOW)
    )
    parent = repository.save_source(
        Source(id="phase1-parent", canonical_uri="https://example.test/parent", created_at=NOW)
    )
    dependency = repository.save_source_dependency(
        SourceDependency(
            id="phase1-dependency",
            source_id=source.id,
            parent_source_id=parent.id,
            dependency_group="origin-1",
            independence_score=0.2,
            reason="mirror signal",
            signals={"same_domain": True},
            created_at=NOW,
            created_by_stage_run_id=stage.id,
        )
    )
    snapshot = repository.create_snapshot(
        source.id,
        b"phase 1 evidence",
        snapshot_id="phase1-snapshot",
        retrieved_at=NOW,
        created_by_stage_run_id=stage.id,
    )
    evidence = repository.save_evidence(
        Evidence(
            id="phase1-evidence",
            snapshot_id=snapshot.id,
            text="phase 1 quote",
            created_at=NOW,
            created_by_stage_run_id=stage.id,
        )
    )
    claim = repository.save_claim(
        Claim(
            id="phase1-claim",
            statement="the project has a refinery",
            subject="project",
            predicate="has",
            object="refinery",
            created_at=NOW,
            created_by_stage_run_id=stage.id,
        )
    )
    group = repository.save_claim_group(
        ClaimGroup(
            id="phase1-group",
            canonical_key="project-has",
            canonical_statement="The project has a refinery",
            subject="project",
            predicate="has",
            qualifiers={"scope": "current"},
            created_at=NOW,
            created_by_stage_run_id=stage.id,
        )
    )
    repository.add_claim_to_group(group.id, claim.id)
    link = repository.save_evidence_link(
        EvidenceLink(
            id="phase1-link",
            evidence_id=evidence.id,
            claim_id=claim.id,
            created_at=NOW,
            created_by_stage_run_id=stage.id,
        )
    )
    decision = repository.save_resolution_decision(
        ResolutionDecision(
            id="phase1-decision",
            claim_group_id=group.id,
            canonical_statement="The project has a refinery",
            status=decision_status,
            resolution_reason="the direct evidence is in scope",
            created_at=NOW,
            created_by_stage_run_id=stage.id,
        )
    )
    claim_input = repository.save_resolution_claim_input(
        ResolutionClaimInput(
            id="phase1-claim-input",
            resolution_decision_id=decision.id,
            claim_id=claim.id,
            role=ResolutionInputRole.SUPPORTING,
            reason="selected direct claim",
            created_at=NOW,
            created_by_stage_run_id=stage.id,
        )
    )
    evidence_input = repository.save_resolution_evidence_input(
        ResolutionEvidenceInput(
            id="phase1-evidence-input",
            resolution_decision_id=decision.id,
            evidence_id=evidence.id,
            role=ResolutionInputRole.SUPPORTING,
            reason="selected direct evidence",
            created_at=NOW,
            created_by_stage_run_id=stage.id,
        )
    )
    assessment = repository.save_confidence_assessment(
        ConfidenceAssessment(
            id="phase1-assessment",
            resolution_decision_id=decision.id,
            policy_version="phase1a-test",
            source_quality=0.9,
            evidence_directness=0.9,
            source_independence=0.8,
            agreement=0.9,
            freshness=0.8,
            extraction_confidence=0.95,
            contradiction_penalty=0.0,
            publish_cap=None,
            evidence_floor_met=True,
            score=0.85,
            reasons={"directness": ["direct quote"]},
            created_at=NOW,
            created_by_stage_run_id=stage.id,
        )
    )
    resolved = repository.save_resolved_claim(
        ResolvedClaim(
            id="phase1-resolved",
            claim_group_id=group.id,
            canonical_statement=decision.canonical_statement,
            status=decision.status,
            confidence=assessment.score,
            resolution_reason=decision.resolution_reason,
            resolution_decision_id=decision.id,
            confidence_assessment_id=assessment.id,
            created_at=NOW,
            created_by_stage_run_id=stage.id,
        )
    )
    atom = repository.save_knowledge_atom(
        KnowledgeAtom(
            id="phase1-atom",
            resolved_claim_id=resolved.id,
            subject="project",
            predicate="has",
            object="refinery",
            statement=decision.canonical_statement,
            confidence=assessment.score,
            status=KnowledgeAtomStatus.ACTIVE,
            created_at=NOW,
            created_by_stage_run_id=stage.id,
        )
    )
    return locals()


def test_phase1_repository_persists_formal_resolution_and_provenance(repository) -> None:
    chain = _phase1_chain(repository)
    assert repository.get_source_dependency("phase1-dependency") == chain["dependency"]
    assert repository.list_resolution_decisions_for_group("phase1-group") == (chain["decision"],)
    assert repository.list_resolution_claim_inputs("phase1-decision") == (
        chain["claim_input"],
    )
    assert repository.list_resolution_evidence_inputs("phase1-decision") == (
        chain["evidence_input"],
    )
    assert repository.list_confidence_assessments_for_decision("phase1-decision") == (
        chain["assessment"],
    )

    provenance = repository.get_provenance(chain["atom"].id)
    assert provenance.resolution_decision == chain["decision"]
    assert provenance.resolution_claim_inputs == (chain["claim_input"],)
    assert provenance.resolution_evidence_inputs == (chain["evidence_input"],)
    assert provenance.confidence_assessment == chain["assessment"]
    assert provenance.claims == (chain["claim"],)
    assert provenance.evidences == (chain["evidence"],)

    processing = repository.get_processing_provenance(chain["atom"].id)
    assert {
        step.entity_type for step in processing.steps
    } >= {
        "resolution_decision",
        "resolution_claim_input",
        "resolution_evidence_input",
        "confidence_assessment",
        "resolved_claim",
        "knowledge_atom",
    }


def test_phase1_immutable_records_support_exact_replay_only(repository) -> None:
    chain = _phase1_chain(repository)
    assert repository.save_source_dependency(chain["dependency"]) == chain["dependency"]
    assert repository.save_resolution_decision(chain["decision"]) == chain["decision"]
    assert repository.save_resolution_claim_input(chain["claim_input"]) == chain["claim_input"]
    assert repository.save_resolution_evidence_input(chain["evidence_input"]) == chain[
        "evidence_input"
    ]
    assert repository.save_confidence_assessment(chain["assessment"]) == chain["assessment"]

    with pytest.raises(ImmutableRecordError):
        repository.save_source_dependency(
            SourceDependency(
                id="phase1-dependency",
                source_id="phase1-source",
                parent_source_id="phase1-parent",
                relation_type="cites",
                created_at=NOW,
            )
        )
    with pytest.raises(ImmutableRecordError):
        repository.save_resolution_decision(
            ResolutionDecision(
                id="phase1-decision",
                claim_group_id="phase1-group",
                canonical_statement="changed",
                resolution_reason="different payload",
            )
        )
    with pytest.raises(ImmutableRecordError):
        repository.save_confidence_assessment(
            ConfidenceAssessment(
                id="phase1-assessment",
                resolution_decision_id="phase1-decision",
                policy_version="phase1a-test",
                score=0.7,
                reasons={"score": ["changed"]},
            )
        )


def test_resolution_input_integrity_requires_group_membership(repository) -> None:
    chain = _phase1_chain(repository)
    other = repository.save_claim(Claim(id="other-claim", statement="other", created_at=NOW))
    with pytest.raises(StorageIntegrityError, match="claim group"):
        repository.save_resolution_claim_input(
            ResolutionClaimInput(
                id="bad-claim-input",
                resolution_decision_id=chain["decision"].id,
                claim_id=other.id,
            )
        )
    with pytest.raises(StorageIntegrityError, match="evidence does not exist"):
        repository.save_resolution_evidence_input(
            ResolutionEvidenceInput(
                id="bad-evidence-input",
                resolution_decision_id=chain["decision"].id,
                evidence_id="missing-evidence",
            )
        )


def test_resolved_claim_cross_object_consistency_is_enforced(repository) -> None:
    chain = _phase1_chain(repository)
    cases = (
        {
            "id": "wrong-group",
            "claim_group_id": "other-group",
        },
        {
            "id": "wrong-status",
            "status": ResolvedClaimStatus.CONFLICTING,
        },
        {
            "id": "wrong-statement",
            "canonical_statement": "different statement",
        },
        {
            "id": "wrong-assessment",
            "confidence_assessment_id": "missing-assessment",
        },
        {
            "id": "wrong-confidence",
            "confidence": 0.7,
        },
    )
    for overrides in cases:
        values = {
            "claim_group_id": chain["group"].id,
            "canonical_statement": chain["decision"].canonical_statement,
            "status": chain["decision"].status,
            "confidence": chain["assessment"].score,
            "resolution_decision_id": chain["decision"].id,
            "confidence_assessment_id": chain["assessment"].id,
            "created_at": NOW,
        }
        values.update(overrides)
        with pytest.raises(StorageIntegrityError):
            repository.save_resolved_claim(ResolvedClaim(**values))


def test_resolved_claim_requires_both_phase1_links_or_neither(repository) -> None:
    chain = _phase1_chain(repository)
    with pytest.raises(StorageIntegrityError, match="both"):
        repository.save_resolved_claim(
            ResolvedClaim(
                id="partial-links",
                claim_group_id=chain["group"].id,
                canonical_statement=chain["decision"].canonical_statement,
                confidence=chain["assessment"].score,
                resolution_decision_id=chain["decision"].id,
            )
        )


def test_knowledge_atom_publication_invariants(repository) -> None:
    chain = _phase1_chain(repository)
    unresolved = repository.save_claim_group(
        ClaimGroup(
            id="unresolved-group",
            canonical_key="unresolved",
            canonical_statement="unresolved fact",
            created_at=NOW,
        )
    )
    unresolved_claim = repository.save_resolved_claim(
        ResolvedClaim(
            id="unresolved-resolved-claim",
            claim_group_id=unresolved.id,
            canonical_statement="unresolved fact",
            status=ResolvedClaimStatus.UNRESOLVED,
            confidence=0.4,
            created_at=NOW,
        )
    )
    no_confidence_claim = repository.save_resolved_claim(
        ResolvedClaim(
            id="no-confidence-resolved",
            claim_group_id=chain["group"].id,
            canonical_statement=chain["decision"].canonical_statement,
            status=ResolvedClaimStatus.RESOLVED,
            confidence=None,
            created_at=NOW,
        )
    )
    with pytest.raises(StorageIntegrityError, match="requires a resolved claim"):
        repository.save_knowledge_atom(
            KnowledgeAtom(
                id="active-unresolved",
                resolved_claim_id=unresolved_claim.id,
                statement="fact",
                confidence=unresolved_claim.confidence,
                status=KnowledgeAtomStatus.ACTIVE,
            )
        )
    with pytest.raises(StorageIntegrityError, match="non-null confidence"):
        repository.save_knowledge_atom(
            KnowledgeAtom(
                id="active-no-confidence",
                resolved_claim_id=no_confidence_claim.id,
                statement="fact",
                status=KnowledgeAtomStatus.ACTIVE,
            )
        )

    withheld = repository.save_knowledge_atom(
        KnowledgeAtom(
            id="withheld-conflicting",
            resolved_claim_id=unresolved_claim.id,
            statement="fact",
            confidence=None,
            status=KnowledgeAtomStatus.WITHHELD,
        )
    )
    assert withheld.status is KnowledgeAtomStatus.WITHHELD
    with pytest.raises(StorageIntegrityError, match="must match"):
        repository.save_knowledge_atom(
            KnowledgeAtom(
                id="active-mismatch",
                resolved_claim_id=chain["resolved"].id,
                statement="fact",
                confidence=0.1,
                status=KnowledgeAtomStatus.ACTIVE,
            )
        )


def test_non_null_phase1_provenance_reference_fails_loudly(repository) -> None:
    chain = _phase1_chain(repository)
    database_path = Path(repository.db_path)
    corrupting_engine = create_engine(f"sqlite+pysqlite:///{database_path.resolve().as_posix()}")
    raw = corrupting_engine.raw_connection()
    try:
        raw.execute("PRAGMA foreign_keys=OFF")
        raw.execute(
            "UPDATE resolved_claims SET resolution_decision_id = ?, "
            "confidence_assessment_id = ? WHERE id = ?",
            ("missing-decision", "missing-assessment", chain["resolved"].id),
        )
        raw.commit()
    finally:
        raw.close()
        corrupting_engine.dispose()
    with pytest.raises(StorageIntegrityError, match="missing decision"):
        repository.get_provenance(chain["atom"].id)

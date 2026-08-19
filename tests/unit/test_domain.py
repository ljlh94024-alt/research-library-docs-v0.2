from datetime import UTC, datetime

import pytest

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


def test_phase0_domain_objects_have_stable_ids_and_utc() -> None:
    now = datetime(2026, 8, 19, tzinfo=UTC)
    source = Source(canonical_uri="https://example.test", created_at=now)
    snapshot = SourceSnapshot(
        source_id=source.id,
        retrieved_at=now,
        content_hash="a" * 64,
        content_ref=f"{source.id}/snapshot/content",
    )
    evidence = Evidence(snapshot_id=snapshot.id, text="A source passage", created_at=now)
    claim = Claim(statement="A fact", created_at=now)
    group = ClaimGroup(canonical_key="a-fact", created_at=now)
    link = EvidenceLink(evidence_id=evidence.id, claim_id=claim.id, created_at=now)
    contradiction = Contradiction(
        claim_a_id=claim.id, claim_b_id="other-claim", reason="different", created_at=now
    )
    resolved = ResolvedClaim(claim_group_id=group.id, canonical_statement="A fact", created_at=now)
    atom = KnowledgeAtom(resolved_claim_id=resolved.id, statement="A fact", created_at=now)
    run = PipelineRun(started_at=now)
    stage = StageRun(pipeline_run_id=run.id, stage_name="fixture", started_at=now)

    objects = [
        source,
        snapshot,
        evidence,
        claim,
        group,
        link,
        contradiction,
        resolved,
        atom,
        run,
        stage,
    ]
    assert all(item.id for item in objects)
    assert all(
        getattr(item, "created_at", getattr(item, "started_at", now)).tzinfo is not None
        for item in objects
    )


def test_domain_rejects_naive_time_and_bad_confidence() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Source(canonical_uri="https://example.test", created_at=datetime(2026, 8, 19))
    with pytest.raises(ValueError, match="between 0 and 1"):
        Claim(statement="bad", extraction_confidence=1.1)

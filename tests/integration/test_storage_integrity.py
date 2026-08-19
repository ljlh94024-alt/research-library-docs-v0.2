from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from research_library.domain import (
    Claim,
    ClaimGroup,
    Contradiction,
    ContradictionStatus,
    Evidence,
    EvidenceLink,
    KnowledgeAtom,
    ResolvedClaim,
    Source,
    SourceSnapshot,
    SourceType,
)
from research_library.storage import ImmutableRecordError, StorageIntegrityError
from research_library.storage.schema import source_dependencies

TIMESTAMP = datetime(2026, 1, 1, tzinfo=UTC)


def _source(repository) -> Source:
    return repository.save_source(
        Source(source_type=SourceType.PAPER, canonical_uri="https://example.test/paper")
    )


def test_foreign_keys_are_enabled_on_every_new_connection(repository) -> None:
    with repository.engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    repository.engine.dispose()
    with repository.engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1


def test_snapshot_prevalidates_source_without_creating_files(repository, tmp_path) -> None:
    with pytest.raises(StorageIntegrityError, match="source does not exist"):
        repository.create_snapshot("missing-source", b"bytes", snapshot_id="snapshot-1")
    snapshot_root = Path(repository.snapshot_store.root)
    assert not snapshot_root.exists() or not any(snapshot_root.rglob("*"))


def test_snapshot_prevalidates_stage_without_creating_files(repository) -> None:
    source = _source(repository)
    with pytest.raises(StorageIntegrityError, match="stage run does not exist"):
        repository.create_snapshot(
            source.id,
            b"bytes",
            snapshot_id="snapshot-missing-stage",
            created_by_stage_run_id="missing-stage",
        )
    assert not Path(repository.snapshot_store.root).exists()


def test_snapshot_rolls_back_new_file_when_database_save_fails(repository, monkeypatch) -> None:
    source = _source(repository)

    def fail(_snapshot):
        raise StorageIntegrityError("forced database failure")

    monkeypatch.setattr(repository, "save_snapshot", fail)
    with pytest.raises(StorageIntegrityError, match="forced database failure"):
        repository.create_snapshot(source.id, b"new bytes", snapshot_id="snapshot-cleanup")
    assert not any(Path(repository.snapshot_store.root).rglob("*"))


def test_snapshot_existing_file_is_preserved_when_replay_save_fails(
    repository, monkeypatch
) -> None:
    source = _source(repository)
    snapshot = repository.create_snapshot(
        source.id,
        b"existing bytes",
        snapshot_id="snapshot-existing",
        metadata={"v": 1},
    )
    path = Path(repository.snapshot_store.root) / snapshot.content_ref

    def fail(_snapshot):
        raise StorageIntegrityError("forced replay database failure")

    monkeypatch.setattr(repository, "save_snapshot", fail)
    with pytest.raises(StorageIntegrityError, match="forced replay database failure"):
        repository.create_snapshot(
            source.id,
            b"existing bytes",
            snapshot_id=snapshot.id,
            retrieved_at=snapshot.retrieved_at,
            metadata={"v": 1},
        )
    assert path.read_bytes() == b"existing bytes"


def test_save_snapshot_does_not_read_database_after_commit(repository, monkeypatch) -> None:
    source = _source(repository)
    snapshot = SourceSnapshot(
        id="snapshot-no-post-commit-read",
        source_id=source.id,
        content_hash="b" * 64,
        content_ref="source-lifecycle/snapshot-no-post-commit-read/content",
        retrieved_at=TIMESTAMP,
    )

    def fail_after_commit(_snapshot_id):
        raise AssertionError("post-commit get_snapshot must not be called")

    monkeypatch.setattr(repository, "get_snapshot", fail_after_commit)
    persisted = repository.save_snapshot(snapshot)
    assert persisted.id == snapshot.id


def test_snapshot_exact_replay_is_idempotent_and_metadata_change_is_rejected(repository) -> None:
    source = _source(repository)
    snapshot = repository.create_snapshot(
        source.id,
        b"same bytes",
        snapshot_id="snapshot-replay",
        mime_type="text/plain",
        metadata={"fixture": True},
    )
    replay = repository.create_snapshot(
        source.id,
        b"same bytes",
        snapshot_id="snapshot-replay",
        retrieved_at=snapshot.retrieved_at,
        mime_type="text/plain",
        metadata={"fixture": True},
    )
    assert replay == snapshot
    with pytest.raises(ImmutableRecordError):
        repository.create_snapshot(
            source.id,
            b"same bytes",
            snapshot_id="snapshot-replay",
            retrieved_at=snapshot.retrieved_at,
            mime_type="text/markdown",
            metadata={"fixture": True},
        )
    with repository.engine.connect() as connection:
        assert connection.execute(
            sa.text("SELECT COUNT(*) FROM source_snapshots WHERE id = 'snapshot-replay'")
        ).scalar_one() == 1


def test_immutable_entities_replay_exactly_and_reject_divergence(repository) -> None:
    source = _source(repository)
    snapshot = repository.create_snapshot(source.id, b"content", snapshot_id="immutable-snapshot")
    evidence = repository.save_evidence(Evidence(snapshot_id=snapshot.id, text="quote"))
    claim = repository.save_claim(
        Claim(id="immutable-claim", statement="fact", extraction_confidence=0.5)
    )
    group = repository.save_claim_group(ClaimGroup(id="immutable-group", canonical_key="fact"))
    repository.add_claim_to_group(group.id, claim.id)
    link = repository.save_evidence_link(
        EvidenceLink(id="immutable-link", evidence_id=evidence.id, claim_id=claim.id)
    )
    resolved = repository.save_resolved_claim(
        ResolvedClaim(
            id="immutable-resolved",
            claim_group_id=group.id,
            canonical_statement="fact",
            confidence=0.8,
        )
    )
    atom = repository.save_knowledge_atom(
        KnowledgeAtom(
            id="immutable-atom",
            resolved_claim_id=resolved.id,
            statement="fact",
            confidence=0.8,
        )
    )

    assert repository.save_evidence(evidence) == evidence
    assert repository.save_claim(claim) == claim
    assert repository.save_claim_group(group) == group
    assert repository.save_evidence_link(link) == link
    assert repository.save_resolved_claim(resolved) == resolved
    assert repository.save_knowledge_atom(atom) == atom
    with pytest.raises(ImmutableRecordError):
        repository.save_claim(Claim(id=claim.id, statement="changed", extraction_confidence=0.5))
    with pytest.raises(ImmutableRecordError):
        repository.save_knowledge_atom(
            KnowledgeAtom(
                id=atom.id,
                resolved_claim_id=resolved.id,
                statement="changed",
                confidence=0.8,
            )
        )


def test_stage_run_foreign_keys_are_enforced_for_outputs(repository) -> None:
    with pytest.raises(StorageIntegrityError):
        repository.save_claim(
            Claim(id="bad-stage-claim", statement="bad", created_by_stage_run_id="missing")
        )
    with pytest.raises(StorageIntegrityError):
        repository.save_evidence(
            Evidence(
                id="bad-stage-evidence",
                snapshot_id="missing",
                text="bad",
                created_by_stage_run_id="missing",
            )
        )


def test_confidence_checks_reject_values_outside_zero_to_one(repository) -> None:
    source = _source(repository)
    claim = repository.save_claim(
        Claim(id="confidence-claim", statement="fact", extraction_confidence=0.5)
    )
    group = repository.save_claim_group(
        ClaimGroup(id="confidence-group", canonical_key="confidence")
    )
    resolved = repository.save_resolved_claim(
        ResolvedClaim(
            id="confidence-resolved",
            claim_group_id=group.id,
            canonical_statement="fact",
            confidence=0.5,
        )
    )
    atom = repository.save_knowledge_atom(
        KnowledgeAtom(
            id="confidence-atom",
            resolved_claim_id=resolved.id,
            statement="fact",
            confidence=0.5,
        )
    )
    with repository.engine.begin() as connection:
        connection.execute(
            source_dependencies.insert().values(
                id="confidence-dependency",
                source_id=source.id,
                parent_source_id=source.id,
                independence_score=0.5,
            )
        )

    cases = (
        ("claims", "extraction_confidence", claim.id),
        ("resolved_claims", "confidence", resolved.id),
        ("knowledge_atoms", "confidence", atom.id),
        ("source_dependencies", "independence_score", "confidence-dependency"),
    )
    for table, column, row_id in cases:
        with pytest.raises(IntegrityError):
            with repository.engine.begin() as connection:
                connection.execute(
                    sa.text(f"UPDATE {table} SET {column} = 1.01 WHERE id = :id"),
                    {"id": row_id},
                )


def test_mutable_records_update_without_replacing_immutable_facts(repository) -> None:
    source = _source(repository)
    updated_source = Source(
        id=source.id,
        source_type=source.source_type,
        canonical_uri=source.canonical_uri,
        title="updated title",
        publisher=source.publisher,
        metadata=source.metadata,
        created_at=source.created_at,
    )
    repository.save_source(updated_source)
    assert repository.get_source(source.id).title == "updated title"

    claim_a = repository.save_claim(Claim(id="mutable-claim-a", statement="first"))
    claim_b = repository.save_claim(Claim(id="mutable-claim-b", statement="second"))
    contradiction = repository.save_contradiction(
        Contradiction(
            id="mutable-contradiction",
            claim_a_id=claim_a.id,
            claim_b_id=claim_b.id,
            reason="fixture",
        )
    )
    updated_contradiction = Contradiction(
        id=contradiction.id,
        claim_a_id=claim_a.id,
        claim_b_id=claim_b.id,
        reason="resolved by review",
        status=ContradictionStatus.RESOLVED,
        created_at=contradiction.created_at,
    )
    repository.save_contradiction(updated_contradiction)
    assert repository.get_contradiction(contradiction.id).status is ContradictionStatus.RESOLVED

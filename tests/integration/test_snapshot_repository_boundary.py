from pathlib import Path

import pytest

from research_library.domain import Source, SourceSnapshot
from research_library.storage import SnapshotIntegrityError


def _source(repository) -> Source:
    return repository.save_source(Source(id="boundary-source", canonical_uri="https://example.test"))


def test_direct_save_rejects_missing_content_and_leaves_database_empty(repository) -> None:
    source = _source(repository)
    snapshot = SourceSnapshot(
        id="missing-content",
        source_id=source.id,
        content_hash="a" * 64,
        content_ref="boundary-source/missing-content/content",
    )
    with pytest.raises(SnapshotIntegrityError, match="content missing"):
        repository.save_snapshot(snapshot)
    assert repository.get_snapshot(snapshot.id) is None


def test_direct_save_rejects_content_hash_mismatch(repository) -> None:
    source = _source(repository)
    content_ref, actual_hash = repository.snapshot_store.store(
        source.id, "hash-mismatch", b"actual bytes"
    )
    snapshot = SourceSnapshot(
        id="hash-mismatch",
        source_id=source.id,
        content_hash="b" * 64,
        content_ref=content_ref,
    )
    assert actual_hash != snapshot.content_hash
    with pytest.raises(SnapshotIntegrityError, match="SHA-256 mismatch"):
        repository.save_snapshot(snapshot)
    assert repository.get_snapshot(snapshot.id) is None


def test_exact_replay_rejects_missing_content(repository) -> None:
    source = _source(repository)
    snapshot = repository.create_snapshot(source.id, b"original", snapshot_id="replay-missing")
    path = Path(repository.snapshot_store.root) / snapshot.content_ref
    path.unlink()
    with pytest.raises(SnapshotIntegrityError, match="content missing"):
        repository.save_snapshot(snapshot)


def test_exact_replay_rejects_tampered_content(repository) -> None:
    source = _source(repository)
    snapshot = repository.create_snapshot(source.id, b"original", snapshot_id="replay-tampered")
    path = Path(repository.snapshot_store.root) / snapshot.content_ref
    path.write_bytes(b"tampered")
    with pytest.raises(SnapshotIntegrityError, match="SHA-256 mismatch"):
        repository.save_snapshot(snapshot)


def test_read_snapshot_converts_missing_file_to_snapshot_integrity_error(repository) -> None:
    source = _source(repository)
    snapshot = repository.create_snapshot(source.id, b"original", snapshot_id="read-missing")
    (Path(repository.snapshot_store.root) / snapshot.content_ref).unlink()
    with pytest.raises(SnapshotIntegrityError, match="content missing"):
        repository.read_snapshot(snapshot.id)

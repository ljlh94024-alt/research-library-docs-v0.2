import hashlib

import pytest

from research_library.storage.snapshot import ImmutableSnapshotError, SnapshotFilesystem


def test_snapshot_store_uses_relative_ref_and_sha256(tmp_path) -> None:
    store = SnapshotFilesystem(tmp_path / "snapshots")
    ref, digest = store.store("source-1", "snapshot-1", "hello")
    assert ref == "source-1/snapshot-1/content"
    assert digest == hashlib.sha256(b"hello").hexdigest()
    assert store.verify(ref, digest)
    assert store.read(ref, digest) == b"hello"


def test_snapshot_store_does_not_overwrite_existing_content(tmp_path) -> None:
    store = SnapshotFilesystem(tmp_path / "snapshots")
    store.store("source-1", "snapshot-1", "old")
    with pytest.raises(ImmutableSnapshotError):
        store.store("source-1", "snapshot-1", "new")

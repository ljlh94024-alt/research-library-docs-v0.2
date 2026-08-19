"""Immutable local filesystem storage for SourceSnapshot content."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath

from .errors import StorageIntegrityError


class ImmutableSnapshotError(StorageIntegrityError):
    """Raised when a snapshot's existing content would be replaced."""


class SnapshotIntegrityError(StorageIntegrityError):
    """Raised when stored bytes do not match the recorded hash."""


class SnapshotFilesystem:
    """Store bytes below a configured snapshot root using portable references."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    @staticmethod
    def content_hash(content: bytes | str) -> str:
        data = content.encode("utf-8") if isinstance(content, str) else content
        return hashlib.sha256(data).hexdigest()

    def _path_for_ref(self, content_ref: str) -> Path:
        ref = PurePosixPath(content_ref.replace("\\", "/"))
        if not content_ref or ref.is_absolute() or ".." in ref.parts:
            raise ValueError("content_ref must be a safe relative path")
        return self.root.joinpath(*ref.parts)

    def store(
        self,
        source_id: str,
        snapshot_id: str,
        content: bytes | str,
        content_ref: str | None = None,
    ) -> tuple[str, str]:
        data = content.encode("utf-8") if isinstance(content, str) else content
        if not isinstance(data, bytes):
            raise TypeError("snapshot content must be bytes or str")
        ref = content_ref or f"{source_id}/{snapshot_id}/content"
        path = self._path_for_ref(ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = self.content_hash(data)
        if path.exists():
            existing = path.read_bytes()
            if existing != data:
                raise ImmutableSnapshotError(f"snapshot content already exists: {ref}")
            return ref.replace("\\", "/"), digest
        with path.open("xb") as handle:
            handle.write(data)
        return ref.replace("\\", "/"), digest

    def store_with_status(
        self,
        source_id: str,
        snapshot_id: str,
        content: bytes | str,
        content_ref: str | None = None,
    ) -> tuple[str, str, bool]:
        """Store content and report whether this call created a new file."""

        data = content.encode("utf-8") if isinstance(content, str) else content
        if not isinstance(data, bytes):
            raise TypeError("snapshot content must be bytes or str")
        ref = content_ref or f"{source_id}/{snapshot_id}/content"
        path = self._path_for_ref(ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = self.content_hash(data)
        if path.exists():
            if path.read_bytes() != data:
                raise ImmutableSnapshotError(f"snapshot content already exists: {ref}")
            return ref.replace("\\", "/"), digest, False
        with path.open("xb") as handle:
            handle.write(data)
        return ref.replace("\\", "/"), digest, True

    def discard_uncommitted(self, content_ref: str, expected_hash: str) -> bool:
        """Remove only a just-written file whose bytes still match ``expected_hash``."""

        path = self._path_for_ref(content_ref)
        if not path.exists() or self.content_hash(path.read_bytes()) != expected_hash.lower():
            return False
        path.unlink()
        parent = path.parent
        while parent != self.root and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
        return True

    def read(self, content_ref: str, expected_hash: str | None = None) -> bytes:
        path = self._path_for_ref(content_ref)
        try:
            data = path.read_bytes()
        except FileNotFoundError as exc:
            raise SnapshotIntegrityError(f"snapshot content missing: {content_ref}") from exc
        if expected_hash is not None and self.content_hash(data) != expected_hash.lower():
            raise SnapshotIntegrityError(f"SHA-256 mismatch for {content_ref}")
        return data

    def verify(self, content_ref: str, expected_hash: str) -> bool:
        self.read(content_ref, expected_hash)
        return True

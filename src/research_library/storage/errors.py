"""Semantic storage errors for violated persistence invariants."""


class StorageIntegrityError(RuntimeError):
    """Raised when persisted references or constraints are invalid."""

    snapshot_cleanup_safe = True


class ImmutableRecordError(StorageIntegrityError):
    """Raised when an append-only entity is replayed with different data."""


class InvalidStateTransitionError(StorageIntegrityError):
    """Raised when a persisted lifecycle record attempts an illegal transition."""


class SnapshotCommitUncertainError(StorageIntegrityError):
    """Raised when a snapshot transaction may have committed before failing."""

    snapshot_cleanup_safe = False

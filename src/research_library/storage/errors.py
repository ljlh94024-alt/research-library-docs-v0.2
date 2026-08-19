"""Semantic storage errors for violated persistence invariants."""


class StorageIntegrityError(RuntimeError):
    """Raised when persisted references or constraints are invalid."""


class ImmutableRecordError(StorageIntegrityError):
    """Raised when an append-only entity is replayed with different data."""

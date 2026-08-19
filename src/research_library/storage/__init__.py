"""Storage contracts and the Phase 0 SQLite/filesystem implementation."""

from research_library.llm.records import LLMCallRecord, LLMCallStatus

from .errors import (
    ImmutableRecordError,
    InvalidStateTransitionError,
    SnapshotCommitUncertainError,
    StorageIntegrityError,
)
from .repository import (
    ProcessingGap,
    ProcessingProvenance,
    ProcessingStep,
    ProvenanceChain,
    Repository,
)
from .snapshot import ImmutableSnapshotError, SnapshotFilesystem, SnapshotIntegrityError
from .sqlite import SQLiteRepository

__all__ = [
    "ImmutableSnapshotError",
    "LLMCallRecord",
    "LLMCallStatus",
    "ImmutableRecordError",
    "InvalidStateTransitionError",
    "ProcessingGap",
    "ProcessingProvenance",
    "ProcessingStep",
    "ProvenanceChain",
    "Repository",
    "SQLiteRepository",
    "SnapshotFilesystem",
    "SnapshotIntegrityError",
    "SnapshotCommitUncertainError",
    "StorageIntegrityError",
]

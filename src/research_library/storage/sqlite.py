"""SQLite repository for the Phase 0 domain model."""

from __future__ import annotations

import json
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from research_library.config import get_settings
from research_library.domain import (
    Claim,
    ClaimGroup,
    ConfidenceAssessment,
    Contradiction,
    ContradictionSeverity,
    ContradictionStatus,
    ContradictionType,
    Evidence,
    EvidenceLink,
    EvidenceLinkType,
    KnowledgeAtom,
    KnowledgeAtomStatus,
    PipelineRun,
    PipelineRunStatus,
    ResolutionClaimInput,
    ResolutionDecision,
    ResolutionEvidenceInput,
    ResolutionInputRole,
    ResolvedClaim,
    ResolvedClaimStatus,
    Source,
    SourceDependency,
    SourceDependencyRelation,
    SourceSnapshot,
    SourceType,
    StageRun,
    StageRunStatus,
)

from .errors import (
    ImmutableRecordError,
    InvalidStateTransitionError,
    SnapshotCommitUncertainError,
    StorageIntegrityError,
)
from .migration_safety import run_migrations_with_safety
from .repository import ProcessingGap, ProcessingProvenance, ProcessingStep, ProvenanceChain
from .schema import (
    claim_group_members,
    claim_groups,
    claims,
    confidence_assessments,
    contradictions,
    evidence,
    evidence_links,
    knowledge_atoms,
    pipeline_runs,
    resolution_claim_inputs,
    resolution_decisions,
    resolution_evidence_inputs,
    resolved_claims,
    source_dependencies,
    source_snapshots,
    sources,
    stage_runs,
)
from .snapshot import SnapshotFilesystem


def _json(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)


def _from_json(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        return json.loads(value)
    return dict(value)


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value is not None else None


def _dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _float(value: str | float | None) -> float | None:
    return float(value) if value is not None else None


def _db_url(db_path: str | Path) -> tuple[str, dict[str, Any]]:
    if str(db_path) == ":memory:":
        return "sqlite+pysqlite:///:memory:", {
            "poolclass": StaticPool,
            "connect_args": {"check_same_thread": False},
        }
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+pysqlite:///{path.resolve().as_posix()}", {
        "connect_args": {"check_same_thread": False}
    }


class SQLiteRepository(AbstractContextManager["SQLiteRepository"]):
    """Repository using SQLite for relations and local files for snapshots."""

    def __init__(
        self,
        db_path: str | Path = "data/research_library.db",
        snapshot_root: str | Path | None = None,
        *,
        engine: Engine | None = None,
    ) -> None:
        self.db_path = str(db_path)
        if engine is None:
            url, kwargs = _db_url(db_path)
            self.engine = create_engine(url, future=True, **kwargs)
        else:
            self.engine = engine
        self.snapshot_store = SnapshotFilesystem(snapshot_root or get_settings().snapshot_root)
        self._enable_foreign_keys()
        self._run_migrations()

    def _enable_foreign_keys(self) -> None:
        if self.engine.dialect.name != "sqlite":
            return

        @event.listens_for(self.engine, "connect")
        def _set_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")

    def _run_migrations(self) -> None:
        migration_dir = Path(__file__).parent / "migrations"
        config = Config()
        config.set_main_option("script_location", str(migration_dir))
        config.set_main_option("sqlalchemy.url", str(self.engine.url).replace("%", "%%"))
        with self.engine.connect() as connection:
            config.attributes["connection"] = connection
            run_migrations_with_safety(
                connection,
                lambda: command.upgrade(config, "head"),
            )

    def close(self) -> None:
        self.engine.dispose()

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()

    @staticmethod
    def _row(connection: Any, table: Any, object_id: str) -> Any | None:
        return connection.execute(select(table).where(table.c.id == object_id)).mappings().first()

    @staticmethod
    def _values_match(
        existing: Any, values: dict[str, Any], fields: tuple[str, ...] | None = None
    ) -> bool:
        keys = fields or tuple(values)
        for key in keys:
            expected = values[key]
            actual = existing[key]
            if key in {"metadata", "qualifiers", "signals", "reasons"}:
                if _from_json(actual) != (expected or {}):
                    return False
            elif actual != expected:
                return False
        return True

    @classmethod
    def _persist_lifecycle(
        cls,
        connection: Any,
        table: Any,
        values: dict[str, Any],
        *,
        entity_type: str,
        immutable_fields: tuple[str, ...],
        mutable_fields: tuple[str, ...],
        status_field: str | None = None,
        terminal_statuses: tuple[str, ...] = (),
    ) -> Any:
        existing = connection.execute(
            select(table).where(table.c.id == values["id"])
        ).mappings().first()
        if existing is None:
            try:
                connection.execute(insert(table).values(**values))
            except IntegrityError as exc:
                raise StorageIntegrityError(
                    f"cannot persist {entity_type} {values['id']}: relational integrity failed"
                ) from exc
            return cls._row(connection, table, values["id"])

        if not cls._values_match(existing, values, immutable_fields):
            raise ImmutableRecordError(
                f"{entity_type} {values['id']} has immutable identity changes"
            )

        if status_field is not None:
            old_status = existing[status_field]
            new_status = values[status_field]
            if old_status != new_status:
                if old_status in terminal_statuses:
                    raise InvalidStateTransitionError(
                        f"{entity_type} {values['id']} cannot leave terminal state {old_status}"
                    )
                if old_status != "started" and not (
                    entity_type == "Contradiction" and old_status == "open"
                ):
                    raise InvalidStateTransitionError(
                        f"{entity_type} {values['id']} has invalid state transition "
                        f"{old_status} -> {new_status}"
                    )
            elif old_status in terminal_statuses and not cls._values_match(
                existing, values, mutable_fields
            ):
                raise InvalidStateTransitionError(
                    f"{entity_type} {values['id']} is terminal and only exact replay is allowed"
                )

        updates = {field: values[field] for field in mutable_fields}
        if updates:
            connection.execute(
                update(table).where(table.c.id == values["id"]).values(**updates)
            )
        return cls._row(connection, table, values["id"])

    @classmethod
    def _insert_immutable(
        cls, connection: Any, table: Any, values: dict[str, Any], entity_type: str
    ) -> bool:
        existing = connection.execute(
            select(table).where(table.c.id == values["id"])
        ).mappings().first()
        if existing is not None:
            if cls._values_match(existing, values):
                return False
            raise ImmutableRecordError(f"{entity_type} {values['id']} is immutable")
        try:
            connection.execute(insert(table).values(**values))
        except IntegrityError as exc:
            raise StorageIntegrityError(
                f"cannot persist {entity_type} {values['id']}: relational integrity failed"
            ) from exc
        return True

    def save_source(self, source: Source) -> Source:
        values = {
            "id": source.id,
            "source_type": source.source_type.value,
            "canonical_uri": source.canonical_uri,
            "title": source.title,
            "publisher": source.publisher,
            "metadata": source.metadata,
            "created_at": _iso(source.created_at),
        }
        with self.engine.begin() as connection:
            row = self._persist_lifecycle(
                connection,
                sources,
                values,
                entity_type="Source",
                immutable_fields=("id", "source_type", "canonical_uri", "created_at"),
                mutable_fields=("title", "publisher", "metadata"),
            )
        if row is None:
            raise StorageIntegrityError(f"source disappeared after save: {source.id}")
        return self._source(row)

    def get_source(self, source_id: str) -> Source | None:
        with self.engine.connect() as connection:
            row = self._row(connection, sources, source_id)
        return self._source(row) if row else None

    @staticmethod
    def _source(row: Any) -> Source:
        return Source(
            id=row["id"],
            source_type=SourceType(row["source_type"]),
            canonical_uri=row["canonical_uri"],
            title=row["title"],
            publisher=row["publisher"],
            metadata=_from_json(row["metadata"]),
            created_at=_dt(row["created_at"]),
        )

    def create_snapshot(
        self,
        source_id: str,
        content: bytes | str,
        *,
        snapshot_id: str | None = None,
        retrieved_at: datetime | None = None,
        mime_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        created_by_stage_run_id: str | None = None,
    ) -> SourceSnapshot:
        from uuid import uuid4

        snapshot_id = snapshot_id or str(uuid4())
        if self.get_source(source_id) is None:
            raise StorageIntegrityError(f"source does not exist: {source_id}")
        if (
            created_by_stage_run_id is not None
            and self.get_stage_run(created_by_stage_run_id) is None
        ):
            raise StorageIntegrityError(f"stage run does not exist: {created_by_stage_run_id}")

        content_ref, content_hash, created_new = self.snapshot_store.store_with_status(
            source_id, snapshot_id, content
        )
        snapshot = SourceSnapshot(
            id=snapshot_id,
            source_id=source_id,
            retrieved_at=retrieved_at or datetime.now(UTC),
            content_hash=content_hash,
            content_ref=content_ref,
            mime_type=mime_type,
            metadata=metadata or {},
            created_by_stage_run_id=created_by_stage_run_id,
        )
        try:
            return self.save_snapshot(snapshot)
        except Exception as exc:
            if created_new and getattr(exc, "snapshot_cleanup_safe", False):
                self.snapshot_store.discard_uncommitted(content_ref, content_hash)
            raise

    def save_snapshot(self, snapshot: SourceSnapshot) -> SourceSnapshot:
        self.snapshot_store.verify(snapshot.content_ref, snapshot.content_hash)
        values = {
            "id": snapshot.id,
            "source_id": snapshot.source_id,
            "retrieved_at": _iso(snapshot.retrieved_at),
            "content_hash": snapshot.content_hash,
            "content_ref": snapshot.content_ref,
            "mime_type": snapshot.mime_type,
            "metadata": snapshot.metadata,
            "created_by_stage_run_id": snapshot.created_by_stage_run_id,
        }
        connection = self.engine.connect()
        transaction = connection.begin()
        try:
            self._insert_immutable(connection, source_snapshots, values, "SourceSnapshot")
            row = self._row(connection, source_snapshots, snapshot.id)
            if row is None:
                raise StorageIntegrityError(f"snapshot disappeared before commit: {snapshot.id}")
            persisted = self._snapshot(row)
            try:
                transaction.commit()
            except Exception as exc:
                raise SnapshotCommitUncertainError(
                    f"snapshot transaction outcome is uncertain: {snapshot.id}"
                ) from exc
            return persisted
        except SnapshotCommitUncertainError:
            if transaction.is_active:
                transaction.rollback()
            raise
        except Exception:
            if transaction.is_active:
                transaction.rollback()
            raise
        finally:
            connection.close()

    def get_snapshot(self, snapshot_id: str) -> SourceSnapshot | None:
        with self.engine.connect() as connection:
            row = self._row(connection, source_snapshots, snapshot_id)
        return self._snapshot(row) if row else None

    @staticmethod
    def _snapshot(row: Any) -> SourceSnapshot:
        return SourceSnapshot(
            id=row["id"],
            source_id=row["source_id"],
            retrieved_at=_dt(row["retrieved_at"]),
            content_hash=row["content_hash"],
            content_ref=row["content_ref"],
            mime_type=row["mime_type"],
            metadata=_from_json(row["metadata"]),
            created_by_stage_run_id=row["created_by_stage_run_id"],
        )

    def read_snapshot(self, snapshot_id: str) -> bytes:
        snapshot = self.get_snapshot(snapshot_id)
        if snapshot is None:
            raise KeyError(snapshot_id)
        return self.snapshot_store.read(snapshot.content_ref, snapshot.content_hash)

    def save_evidence(self, item: Evidence) -> Evidence:
        values = {
            "id": item.id,
            "snapshot_id": item.snapshot_id,
            "text": item.text,
            "locator": item.locator,
            "context": item.context,
            "extraction_method": item.extraction_method,
            "metadata": item.metadata,
            "created_at": _iso(item.created_at),
            "created_by_stage_run_id": item.created_by_stage_run_id,
        }
        with self.engine.begin() as connection:
            self._insert_immutable(connection, evidence, values, "Evidence")
        persisted = self.get_evidence(item.id)
        if persisted is None:
            raise StorageIntegrityError(f"evidence disappeared after save: {item.id}")
        return persisted

    def get_evidence(self, evidence_id: str) -> Evidence | None:
        with self.engine.connect() as connection:
            row = self._row(connection, evidence, evidence_id)
        if not row:
            return None
        return Evidence(
            id=row["id"],
            snapshot_id=row["snapshot_id"],
            text=row["text"],
            locator=row["locator"],
            context=row["context"],
            extraction_method=row["extraction_method"],
            metadata=_from_json(row["metadata"]),
            created_at=_dt(row["created_at"]),
            created_by_stage_run_id=row["created_by_stage_run_id"],
        )

    def save_claim(self, item: Claim) -> Claim:
        values = {
            "id": item.id,
            "statement": item.statement,
            "subject": item.subject,
            "predicate": item.predicate,
            "object": item.object,
            "qualifiers": item.qualifiers,
            "temporal_scope": item.temporal_scope,
            "extraction_confidence": item.extraction_confidence,
            "created_at": _iso(item.created_at),
            "created_by_stage_run_id": item.created_by_stage_run_id,
        }
        with self.engine.begin() as connection:
            self._insert_immutable(connection, claims, values, "Claim")
        persisted = self.get_claim(item.id)
        if persisted is None:
            raise StorageIntegrityError(f"claim disappeared after save: {item.id}")
        return persisted

    def get_claim(self, claim_id: str) -> Claim | None:
        with self.engine.connect() as connection:
            row = self._row(connection, claims, claim_id)
        if not row:
            return None
        return Claim(
            id=row["id"],
            statement=row["statement"],
            subject=row["subject"],
            predicate=row["predicate"],
            object=row["object"],
            qualifiers=_from_json(row["qualifiers"]),
            temporal_scope=row["temporal_scope"],
            extraction_confidence=_float(row["extraction_confidence"]),
            created_at=_dt(row["created_at"]),
            created_by_stage_run_id=row["created_by_stage_run_id"],
        )

    def save_claim_group(self, item: ClaimGroup) -> ClaimGroup:
        values = {
            "id": item.id,
            "canonical_key": item.canonical_key,
            "name": item.name,
            "canonical_statement": item.canonical_statement,
            "subject": item.subject,
            "predicate": item.predicate,
            "qualifiers": item.qualifiers,
            "temporal_scope": item.temporal_scope,
            "created_at": _iso(item.created_at),
            "created_by_stage_run_id": item.created_by_stage_run_id,
        }
        with self.engine.begin() as connection:
            self._insert_immutable(connection, claim_groups, values, "ClaimGroup")
        persisted = self.get_claim_group(item.id)
        if persisted is None:
            raise StorageIntegrityError(f"claim group disappeared after save: {item.id}")
        return persisted

    def get_claim_group(self, group_id: str) -> ClaimGroup | None:
        with self.engine.connect() as connection:
            row = self._row(connection, claim_groups, group_id)
        if not row:
            return None
        return ClaimGroup(
            id=row["id"],
            canonical_key=row["canonical_key"],
            name=row["name"],
            canonical_statement=row["canonical_statement"],
            subject=row["subject"],
            predicate=row["predicate"],
            qualifiers=_from_json(row["qualifiers"]),
            temporal_scope=row["temporal_scope"],
            created_at=_dt(row["created_at"]),
            created_by_stage_run_id=row["created_by_stage_run_id"],
        )

    def add_claim_to_group(self, claim_group_id: str, claim_id: str) -> None:
        with self.engine.begin() as connection:
            try:
                connection.execute(
                    insert(claim_group_members).values(
                        claim_group_id=claim_group_id, claim_id=claim_id
                    )
                )
            except IntegrityError:
                existing = connection.execute(
                    select(claim_group_members).where(
                        claim_group_members.c.claim_group_id == claim_group_id,
                        claim_group_members.c.claim_id == claim_id,
                    )
                ).first()
                if existing is None:
                    raise

    save_claim_group_member = add_claim_to_group

    def list_claims_for_group(self, claim_group_id: str) -> tuple[Claim, ...]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(claims)
                    .join(claim_group_members, claim_group_members.c.claim_id == claims.c.id)
                    .where(claim_group_members.c.claim_group_id == claim_group_id)
                    .order_by(claims.c.created_at, claims.c.id)
                )
                .mappings()
                .all()
            )
        return tuple(
            self.get_claim(row["id"]) for row in rows if self.get_claim(row["id"]) is not None
        )

    def save_evidence_link(self, item: EvidenceLink) -> EvidenceLink:
        values = {
            "id": item.id,
            "evidence_id": item.evidence_id,
            "claim_id": item.claim_id,
            "relation_type": item.relation_type.value,
            "rationale": item.rationale,
            "created_at": _iso(item.created_at),
            "created_by_stage_run_id": item.created_by_stage_run_id,
        }
        with self.engine.begin() as connection:
            self._insert_immutable(connection, evidence_links, values, "EvidenceLink")
        persisted = self.get_evidence_link(item.id)
        if persisted is None:
            raise StorageIntegrityError(f"evidence link disappeared after save: {item.id}")
        return persisted

    def get_evidence_link(self, link_id: str) -> EvidenceLink | None:
        with self.engine.connect() as connection:
            row = self._row(connection, evidence_links, link_id)
        if not row:
            return None
        return EvidenceLink(
            id=row["id"],
            evidence_id=row["evidence_id"],
            claim_id=row["claim_id"],
            relation_type=EvidenceLinkType(row["relation_type"]),
            rationale=row["rationale"],
            created_at=_dt(row["created_at"]),
            created_by_stage_run_id=row["created_by_stage_run_id"],
        )

    def list_evidence_links_for_claim(self, claim_id: str) -> tuple[EvidenceLink, ...]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(evidence_links.c.id)
                .where(evidence_links.c.claim_id == claim_id)
                .order_by(evidence_links.c.created_at, evidence_links.c.id)
            ).all()
        return tuple(link for row in rows if (link := self.get_evidence_link(row[0])) is not None)

    def list_evidence_links_for_evidence(self, evidence_id: str) -> tuple[EvidenceLink, ...]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(evidence_links.c.id)
                .where(evidence_links.c.evidence_id == evidence_id)
                .order_by(evidence_links.c.created_at, evidence_links.c.id)
            ).all()
        return tuple(link for row in rows if (link := self.get_evidence_link(row[0])) is not None)

    def save_source_dependency(self, item: SourceDependency) -> SourceDependency:
        if item.created_at is None:
            raise StorageIntegrityError("new SourceDependency writes require created_at")
        values = {
            "id": item.id,
            "source_id": item.source_id,
            "parent_source_id": item.parent_source_id,
            "relation_type": item.relation_type.value,
            "dependency_group": item.dependency_group,
            "independence_score": item.independence_score,
            "reason": item.reason,
            "signals": item.signals,
            "created_at": _iso(item.created_at),
            "created_by_stage_run_id": item.created_by_stage_run_id,
        }
        with self.engine.begin() as connection:
            self._insert_immutable(connection, source_dependencies, values, "SourceDependency")
        persisted = self.get_source_dependency(item.id)
        if persisted is None:
            raise StorageIntegrityError(f"source dependency disappeared after save: {item.id}")
        return persisted

    def get_source_dependency(self, dependency_id: str) -> SourceDependency | None:
        with self.engine.connect() as connection:
            row = self._row(connection, source_dependencies, dependency_id)
        if not row:
            return None
        return SourceDependency(
            id=row["id"],
            source_id=row["source_id"],
            parent_source_id=row["parent_source_id"],
            relation_type=SourceDependencyRelation(row["relation_type"]),
            dependency_group=row["dependency_group"],
            independence_score=_float(row["independence_score"]),
            reason=row["reason"],
            signals=_from_json(row["signals"]),
            created_at=_dt(row["created_at"]),
            created_by_stage_run_id=row["created_by_stage_run_id"],
        )

    def list_source_dependencies(
        self, source_id: str | None = None
    ) -> tuple[SourceDependency, ...]:
        statement = select(source_dependencies.c.id).order_by(
            source_dependencies.c.created_at, source_dependencies.c.id
        )
        if source_id is not None:
            statement = statement.where(source_dependencies.c.source_id == source_id)
        with self.engine.connect() as connection:
            rows = connection.execute(statement).all()
        return tuple(
            item
            for row in rows
            if (item := self.get_source_dependency(row[0])) is not None
        )

    def save_contradiction(self, item: Contradiction) -> Contradiction:
        values = {
            "id": item.id,
            "claim_a_id": item.claim_a_id,
            "claim_b_id": item.claim_b_id,
            "type": item.type.value,
            "severity": item.severity.value,
            "reason": item.reason,
            "status": item.status.value,
            "created_at": _iso(item.created_at),
            "resolved_at": _iso(item.resolved_at),
            "created_by_stage_run_id": item.created_by_stage_run_id,
        }
        with self.engine.begin() as connection:
            self._persist_lifecycle(
                connection,
                contradictions,
                values,
                entity_type="Contradiction",
                immutable_fields=(
                    "id",
                    "claim_a_id",
                    "claim_b_id",
                    "type",
                    "created_at",
                    "created_by_stage_run_id",
                ),
                mutable_fields=("severity", "reason", "status", "resolved_at"),
                status_field="status",
                terminal_statuses=(
                    ContradictionStatus.RESOLVED.value,
                    ContradictionStatus.DISMISSED.value,
                ),
            )
        persisted = self.get_contradiction(item.id)
        if persisted is None:
            raise StorageIntegrityError(f"contradiction disappeared after save: {item.id}")
        return persisted

    def get_contradiction(self, contradiction_id: str) -> Contradiction | None:
        with self.engine.connect() as connection:
            row = self._row(connection, contradictions, contradiction_id)
        if not row:
            return None
        return Contradiction(
            id=row["id"],
            claim_a_id=row["claim_a_id"],
            claim_b_id=row["claim_b_id"],
            type=ContradictionType(row["type"]),
            severity=ContradictionSeverity(row["severity"]),
            reason=row["reason"],
            status=ContradictionStatus(row["status"]),
            created_at=_dt(row["created_at"]),
            resolved_at=_dt(row["resolved_at"]),
            created_by_stage_run_id=row["created_by_stage_run_id"],
        )

    @staticmethod
    def _validate_resolved_claim_links(connection: Any, item: ResolvedClaim) -> None:
        has_decision = item.resolution_decision_id is not None
        has_assessment = item.confidence_assessment_id is not None
        if has_decision != has_assessment:
            raise StorageIntegrityError(
                "Phase 1 ResolvedClaim must link both a ResolutionDecision and "
                "ConfidenceAssessment"
            )
        if not has_decision:
            return

        decision = connection.execute(
            select(resolution_decisions).where(
                resolution_decisions.c.id == item.resolution_decision_id
            )
        ).mappings().first()
        assessment = connection.execute(
            select(confidence_assessments).where(
                confidence_assessments.c.id == item.confidence_assessment_id
            )
        ).mappings().first()
        if decision is None:
            raise StorageIntegrityError(
                f"resolution decision does not exist: {item.resolution_decision_id}"
            )
        if assessment is None:
            raise StorageIntegrityError(
                f"confidence assessment does not exist: {item.confidence_assessment_id}"
            )
        if assessment["resolution_decision_id"] != decision["id"]:
            raise StorageIntegrityError("confidence assessment belongs to another decision")
        if item.claim_group_id != decision["claim_group_id"]:
            raise StorageIntegrityError("resolved claim group does not match its decision")
        if item.status.value != decision["status"]:
            raise StorageIntegrityError("resolved claim status does not match its decision")
        if item.canonical_statement != decision["canonical_statement"]:
            raise StorageIntegrityError(
                "resolved claim canonical_statement does not match its decision"
            )
        if item.confidence != assessment["score"]:
            raise StorageIntegrityError("resolved claim confidence does not match its assessment")

    def save_resolved_claim(self, item: ResolvedClaim) -> ResolvedClaim:
        values = {
            "id": item.id,
            "claim_group_id": item.claim_group_id,
            "canonical_statement": item.canonical_statement,
            "status": item.status.value,
            "confidence": item.confidence,
            "resolution_reason": item.resolution_reason,
            "validity": item.validity,
            "resolution_decision_id": item.resolution_decision_id,
            "confidence_assessment_id": item.confidence_assessment_id,
            "created_at": _iso(item.created_at),
            "created_by_stage_run_id": item.created_by_stage_run_id,
        }
        with self.engine.begin() as connection:
            self._validate_resolved_claim_links(connection, item)
            self._insert_immutable(connection, resolved_claims, values, "ResolvedClaim")
        persisted = self.get_resolved_claim(item.id)
        if persisted is None:
            raise StorageIntegrityError(f"resolved claim disappeared after save: {item.id}")
        return persisted

    def get_resolved_claim(self, resolved_claim_id: str) -> ResolvedClaim | None:
        with self.engine.connect() as connection:
            row = self._row(connection, resolved_claims, resolved_claim_id)
        if not row:
            return None
        return ResolvedClaim(
            id=row["id"],
            claim_group_id=row["claim_group_id"],
            canonical_statement=row["canonical_statement"],
            status=ResolvedClaimStatus(row["status"]),
            confidence=_float(row["confidence"]),
            resolution_reason=row["resolution_reason"],
            validity=row["validity"],
            resolution_decision_id=row["resolution_decision_id"],
            confidence_assessment_id=row["confidence_assessment_id"],
            created_at=_dt(row["created_at"]),
            created_by_stage_run_id=row["created_by_stage_run_id"],
        )

    def save_resolution_decision(self, item: ResolutionDecision) -> ResolutionDecision:
        values = {
            "id": item.id,
            "claim_group_id": item.claim_group_id,
            "canonical_statement": item.canonical_statement,
            "status": item.status.value,
            "resolution_reason": item.resolution_reason,
            "validity": item.validity,
            "created_at": _iso(item.created_at),
            "created_by_stage_run_id": item.created_by_stage_run_id,
        }
        with self.engine.begin() as connection:
            self._insert_immutable(connection, resolution_decisions, values, "ResolutionDecision")
        persisted = self.get_resolution_decision(item.id)
        if persisted is None:
            raise StorageIntegrityError(f"resolution decision disappeared after save: {item.id}")
        return persisted

    def get_resolution_decision(self, decision_id: str) -> ResolutionDecision | None:
        with self.engine.connect() as connection:
            row = self._row(connection, resolution_decisions, decision_id)
        if not row:
            return None
        return ResolutionDecision(
            id=row["id"],
            claim_group_id=row["claim_group_id"],
            canonical_statement=row["canonical_statement"],
            status=ResolvedClaimStatus(row["status"]),
            resolution_reason=row["resolution_reason"],
            validity=row["validity"],
            created_at=_dt(row["created_at"]),
            created_by_stage_run_id=row["created_by_stage_run_id"],
        )

    def list_resolution_decisions_for_group(
        self, claim_group_id: str
    ) -> tuple[ResolutionDecision, ...]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(resolution_decisions.c.id)
                .where(resolution_decisions.c.claim_group_id == claim_group_id)
                .order_by(resolution_decisions.c.created_at, resolution_decisions.c.id)
            ).all()
        return tuple(
            item
            for row in rows
            if (item := self.get_resolution_decision(row[0])) is not None
        )

    def save_resolution_claim_input(self, item: ResolutionClaimInput) -> ResolutionClaimInput:
        values = {
            "id": item.id,
            "resolution_decision_id": item.resolution_decision_id,
            "claim_id": item.claim_id,
            "role": item.role.value,
            "reason": item.reason,
            "created_at": _iso(item.created_at),
            "created_by_stage_run_id": item.created_by_stage_run_id,
        }
        with self.engine.begin() as connection:
            decision = connection.execute(
                select(resolution_decisions).where(
                    resolution_decisions.c.id == item.resolution_decision_id
                )
            ).mappings().first()
            if decision is None:
                raise StorageIntegrityError(
                    f"resolution decision does not exist: {item.resolution_decision_id}"
                )
            if connection.execute(
                select(claims.c.id).where(claims.c.id == item.claim_id)
            ).scalar_one_or_none() is None:
                raise StorageIntegrityError(f"claim does not exist: {item.claim_id}")
            member = connection.execute(
                select(claim_group_members).where(
                    claim_group_members.c.claim_group_id == decision["claim_group_id"],
                    claim_group_members.c.claim_id == item.claim_id,
                )
            ).first()
            if member is None:
                raise StorageIntegrityError(
                    "resolution claim input claim does not belong to decision claim group"
                )
            self._insert_immutable(
                connection, resolution_claim_inputs, values, "ResolutionClaimInput"
            )
        persisted = self._get_resolution_claim_input(item.id)
        if persisted is None:
            raise StorageIntegrityError(f"resolution claim input disappeared after save: {item.id}")
        return persisted

    def _get_resolution_claim_input(self, input_id: str) -> ResolutionClaimInput | None:
        with self.engine.connect() as connection:
            row = self._row(connection, resolution_claim_inputs, input_id)
        if not row:
            return None
        return ResolutionClaimInput(
            id=row["id"],
            resolution_decision_id=row["resolution_decision_id"],
            claim_id=row["claim_id"],
            role=ResolutionInputRole(row["role"]),
            reason=row["reason"],
            created_at=_dt(row["created_at"]),
            created_by_stage_run_id=row["created_by_stage_run_id"],
        )

    def list_resolution_claim_inputs(
        self, resolution_decision_id: str
    ) -> tuple[ResolutionClaimInput, ...]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(resolution_claim_inputs.c.id)
                .where(
                    resolution_claim_inputs.c.resolution_decision_id
                    == resolution_decision_id
                )
                .order_by(resolution_claim_inputs.c.created_at, resolution_claim_inputs.c.id)
            ).all()
        items = tuple(self._get_resolution_claim_input(row[0]) for row in rows)
        if any(item is None for item in items):
            raise StorageIntegrityError("resolution claim input row is unreadable")
        return tuple(item for item in items if item is not None)

    def save_resolution_evidence_input(
        self, item: ResolutionEvidenceInput
    ) -> ResolutionEvidenceInput:
        values = {
            "id": item.id,
            "resolution_decision_id": item.resolution_decision_id,
            "evidence_id": item.evidence_id,
            "role": item.role.value,
            "reason": item.reason,
            "created_at": _iso(item.created_at),
            "created_by_stage_run_id": item.created_by_stage_run_id,
        }
        with self.engine.begin() as connection:
            if connection.execute(
                select(resolution_decisions.c.id).where(
                    resolution_decisions.c.id == item.resolution_decision_id
                )
            ).scalar_one_or_none() is None:
                raise StorageIntegrityError(
                    f"resolution decision does not exist: {item.resolution_decision_id}"
                )
            if connection.execute(
                select(evidence.c.id).where(evidence.c.id == item.evidence_id)
            ).scalar_one_or_none() is None:
                raise StorageIntegrityError(f"evidence does not exist: {item.evidence_id}")
            self._insert_immutable(
                connection, resolution_evidence_inputs, values, "ResolutionEvidenceInput"
            )
        persisted = self._get_resolution_evidence_input(item.id)
        if persisted is None:
            raise StorageIntegrityError(
                f"resolution evidence input disappeared after save: {item.id}"
            )
        return persisted

    def _get_resolution_evidence_input(self, input_id: str) -> ResolutionEvidenceInput | None:
        with self.engine.connect() as connection:
            row = self._row(connection, resolution_evidence_inputs, input_id)
        if not row:
            return None
        return ResolutionEvidenceInput(
            id=row["id"],
            resolution_decision_id=row["resolution_decision_id"],
            evidence_id=row["evidence_id"],
            role=ResolutionInputRole(row["role"]),
            reason=row["reason"],
            created_at=_dt(row["created_at"]),
            created_by_stage_run_id=row["created_by_stage_run_id"],
        )

    def list_resolution_evidence_inputs(
        self, resolution_decision_id: str
    ) -> tuple[ResolutionEvidenceInput, ...]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(resolution_evidence_inputs.c.id)
                .where(
                    resolution_evidence_inputs.c.resolution_decision_id
                    == resolution_decision_id
                )
                .order_by(resolution_evidence_inputs.c.created_at, resolution_evidence_inputs.c.id)
            ).all()
        items = tuple(self._get_resolution_evidence_input(row[0]) for row in rows)
        if any(item is None for item in items):
            raise StorageIntegrityError("resolution evidence input row is unreadable")
        return tuple(item for item in items if item is not None)

    def save_confidence_assessment(
        self, item: ConfidenceAssessment
    ) -> ConfidenceAssessment:
        values = {
            "id": item.id,
            "resolution_decision_id": item.resolution_decision_id,
            "policy_version": item.policy_version,
            "source_quality": item.source_quality,
            "evidence_directness": item.evidence_directness,
            "source_independence": item.source_independence,
            "agreement": item.agreement,
            "freshness": item.freshness,
            "extraction_confidence": item.extraction_confidence,
            "contradiction_penalty": item.contradiction_penalty,
            "publish_cap": item.publish_cap,
            "evidence_floor_met": item.evidence_floor_met,
            "score": item.score,
            "reasons": item.reasons,
            "created_at": _iso(item.created_at),
            "created_by_stage_run_id": item.created_by_stage_run_id,
        }
        with self.engine.begin() as connection:
            if connection.execute(
                select(resolution_decisions.c.id).where(
                    resolution_decisions.c.id == item.resolution_decision_id
                )
            ).scalar_one_or_none() is None:
                raise StorageIntegrityError(
                    f"resolution decision does not exist: {item.resolution_decision_id}"
                )
            self._insert_immutable(
                connection, confidence_assessments, values, "ConfidenceAssessment"
            )
        persisted = self.get_confidence_assessment(item.id)
        if persisted is None:
            raise StorageIntegrityError(f"confidence assessment disappeared after save: {item.id}")
        return persisted

    def get_confidence_assessment(self, assessment_id: str) -> ConfidenceAssessment | None:
        with self.engine.connect() as connection:
            row = self._row(connection, confidence_assessments, assessment_id)
        if not row:
            return None
        return ConfidenceAssessment(
            id=row["id"],
            resolution_decision_id=row["resolution_decision_id"],
            policy_version=row["policy_version"],
            source_quality=_float(row["source_quality"]),
            evidence_directness=_float(row["evidence_directness"]),
            source_independence=_float(row["source_independence"]),
            agreement=_float(row["agreement"]),
            freshness=_float(row["freshness"]),
            extraction_confidence=_float(row["extraction_confidence"]),
            contradiction_penalty=_float(row["contradiction_penalty"]),
            publish_cap=_float(row["publish_cap"]),
            evidence_floor_met=bool(row["evidence_floor_met"]),
            score=_float(row["score"]),
            reasons=_from_json(row["reasons"]),
            created_at=_dt(row["created_at"]),
            created_by_stage_run_id=row["created_by_stage_run_id"],
        )

    def list_confidence_assessments_for_decision(
        self, resolution_decision_id: str
    ) -> tuple[ConfidenceAssessment, ...]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(confidence_assessments.c.id)
                .where(
                    confidence_assessments.c.resolution_decision_id
                    == resolution_decision_id
                )
                .order_by(confidence_assessments.c.created_at, confidence_assessments.c.id)
            ).all()
        return tuple(
            item
            for row in rows
            if (item := self.get_confidence_assessment(row[0])) is not None
        )

    @staticmethod
    def _validate_knowledge_atom_semantics(connection: Any, item: KnowledgeAtom) -> None:
        if item.status is not KnowledgeAtomStatus.ACTIVE:
            return
        resolved = connection.execute(
            select(resolved_claims).where(resolved_claims.c.id == item.resolved_claim_id)
        ).mappings().first()
        if resolved is None:
            raise StorageIntegrityError(f"resolved claim does not exist: {item.resolved_claim_id}")
        if resolved["status"] != ResolvedClaimStatus.RESOLVED.value:
            raise StorageIntegrityError("ACTIVE KnowledgeAtom requires a resolved claim")
        if item.confidence is None or resolved["confidence"] is None:
            raise StorageIntegrityError("ACTIVE KnowledgeAtom requires non-null confidence")
        if item.confidence != resolved["confidence"]:
            raise StorageIntegrityError(
                "ACTIVE KnowledgeAtom confidence must match its resolved claim"
            )

    def save_knowledge_atom(self, item: KnowledgeAtom) -> KnowledgeAtom:
        values = {
            "id": item.id,
            "resolved_claim_id": item.resolved_claim_id,
            "subject": item.subject,
            "predicate": item.predicate,
            "object": item.object,
            "statement": item.statement,
            "confidence": item.confidence,
            "status": item.status.value,
            "validity": item.validity,
            "qualifiers": item.qualifiers,
            "created_at": _iso(item.created_at),
            "created_by_stage_run_id": item.created_by_stage_run_id,
        }
        with self.engine.begin() as connection:
            self._validate_knowledge_atom_semantics(connection, item)
            self._insert_immutable(connection, knowledge_atoms, values, "KnowledgeAtom")
        persisted = self.get_knowledge_atom(item.id)
        if persisted is None:
            raise StorageIntegrityError(f"knowledge atom disappeared after save: {item.id}")
        return persisted

    def get_knowledge_atom(self, atom_id: str) -> KnowledgeAtom | None:
        with self.engine.connect() as connection:
            row = self._row(connection, knowledge_atoms, atom_id)
        if not row:
            return None
        return KnowledgeAtom(
            id=row["id"],
            resolved_claim_id=row["resolved_claim_id"],
            subject=row["subject"],
            predicate=row["predicate"],
            object=row["object"],
            statement=row["statement"],
            confidence=_float(row["confidence"]),
            status=KnowledgeAtomStatus(row["status"]),
            validity=row["validity"],
            qualifiers=_from_json(row["qualifiers"]),
            created_at=_dt(row["created_at"]),
            created_by_stage_run_id=row["created_by_stage_run_id"],
        )

    def get_provenance(self, atom_id: str) -> ProvenanceChain:
        atom = self.get_knowledge_atom(atom_id)
        if atom is None:
            raise KeyError(f"knowledge atom not found: {atom_id}")
        resolved = self.get_resolved_claim(atom.resolved_claim_id)
        if resolved is None:
            raise ValueError(f"knowledge atom has no resolved claim: {atom_id}")
        resolution_decision = None
        resolution_claim_inputs = ()
        resolution_evidence_inputs = ()
        confidence_assessment = None
        if (resolved.resolution_decision_id is None) != (
            resolved.confidence_assessment_id is None
        ):
            raise StorageIntegrityError(
                f"resolved claim has a partial Phase 1 link set: {resolved.id}"
            )
        if resolved.resolution_decision_id is not None:
            if resolved.confidence_assessment_id is None:
                raise StorageIntegrityError(
                    f"resolved claim has a decision but no confidence assessment: {resolved.id}"
                )
            resolution_decision = self.get_resolution_decision(resolved.resolution_decision_id)
            confidence_assessment = self.get_confidence_assessment(
                resolved.confidence_assessment_id
            )
            if resolution_decision is None:
                raise StorageIntegrityError(
                    f"resolved claim references missing decision: {resolved.resolution_decision_id}"
                )
            if confidence_assessment is None:
                raise StorageIntegrityError(
                    "resolved claim references missing confidence assessment: "
                    f"{resolved.confidence_assessment_id}"
                )
            resolution_claim_inputs = self.list_resolution_claim_inputs(resolution_decision.id)
            resolution_evidence_inputs = self.list_resolution_evidence_inputs(
                resolution_decision.id
            )
        group = self.get_claim_group(resolved.claim_group_id)
        if group is None:
            raise ValueError(f"resolved claim has no claim group: {resolved.id}")
        claim_items = self.list_claims_for_group(group.id)
        candidate_claim_ids = {item.id for item in claim_items}
        for item_input in resolution_claim_inputs:
            claim = self.get_claim(item_input.claim_id)
            if claim is None:
                raise StorageIntegrityError(
                    f"resolution claim input references missing claim: {item_input.claim_id}"
                )
            if claim.id not in candidate_claim_ids:
                raise StorageIntegrityError(
                    "resolution claim input claim is outside the decision claim group"
                )
        links: list[EvidenceLink] = []
        for claim in claim_items:
            links.extend(self.list_evidence_links_for_claim(claim.id))
        evidence_items: list[Evidence] = []
        for link in links:
            item = self.get_evidence(link.evidence_id)
            if item is not None and item.id not in {existing.id for existing in evidence_items}:
                evidence_items.append(item)
        for item_input in resolution_evidence_inputs:
            item = self.get_evidence(item_input.evidence_id)
            if item is None:
                raise StorageIntegrityError(
                    "resolution evidence input references missing evidence: "
                    f"{item_input.evidence_id}"
                )
            if item.id not in {existing.id for existing in evidence_items}:
                evidence_items.append(item)
        snapshots: list[SourceSnapshot] = []
        for item in evidence_items:
            snapshot = self.get_snapshot(item.snapshot_id)
            if snapshot is not None and snapshot.id not in {existing.id for existing in snapshots}:
                snapshots.append(snapshot)
        source_items: list[Source] = []
        for snapshot in snapshots:
            source = self.get_source(snapshot.source_id)
            if source is not None and source.id not in {existing.id for existing in source_items}:
                source_items.append(source)
        if not claim_items or not evidence_items or not snapshots or not source_items:
            raise ValueError(f"knowledge atom provenance chain is incomplete: {atom_id}")
        return ProvenanceChain(
            atom=atom,
            resolved_claim=resolved,
            claim_group=group,
            claims=claim_items,
            evidence_links=tuple(links),
            evidences=tuple(evidence_items),
            snapshots=tuple(snapshots),
            sources=tuple(source_items),
            resolution_decision=resolution_decision,
            resolution_claim_inputs=resolution_claim_inputs,
            resolution_evidence_inputs=resolution_evidence_inputs,
            confidence_assessment=confidence_assessment,
        )

    def get_processing_provenance(self, atom_id: str) -> ProcessingProvenance:
        """Return the persisted stage and pipeline for every processing output."""

        try:
            chain = self.get_provenance(atom_id)
        except (KeyError, ValueError) as exc:
            raise StorageIntegrityError(f"broken domain provenance for atom {atom_id}") from exc

        entities: list[tuple[str, str, str | None]] = [
            ("source_snapshot", snapshot.id, snapshot.created_by_stage_run_id)
            for snapshot in chain.snapshots
        ]
        entities.extend(
            ("evidence", item.id, item.created_by_stage_run_id) for item in chain.evidences
        )
        entities.extend(
            ("evidence_link", item.id, item.created_by_stage_run_id)
            for item in chain.evidence_links
        )
        entities.extend(("claim", item.id, item.created_by_stage_run_id) for item in chain.claims)
        entities.append(
            ("claim_group", chain.claim_group.id, chain.claim_group.created_by_stage_run_id)
        )
        if chain.resolution_decision is not None:
            entities.append(
                (
                    "resolution_decision",
                    chain.resolution_decision.id,
                    chain.resolution_decision.created_by_stage_run_id,
                )
            )
            entities.extend(
                ("resolution_claim_input", item.id, item.created_by_stage_run_id)
                for item in chain.resolution_claim_inputs
            )
            entities.extend(
                ("resolution_evidence_input", item.id, item.created_by_stage_run_id)
                for item in chain.resolution_evidence_inputs
            )
            if chain.confidence_assessment is not None:
                entities.append(
                    (
                        "confidence_assessment",
                        chain.confidence_assessment.id,
                        chain.confidence_assessment.created_by_stage_run_id,
                    )
                )
        entities.append(
            (
                "resolved_claim",
                chain.resolved_claim.id,
                chain.resolved_claim.created_by_stage_run_id,
            )
        )
        entities.append(("knowledge_atom", chain.atom.id, chain.atom.created_by_stage_run_id))

        steps: list[ProcessingStep] = []
        gaps: list[ProcessingGap] = []
        for entity_type, entity_id, stage_run_id in entities:
            if stage_run_id is None:
                gaps.append(
                    ProcessingGap(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        reason="not_recorded",
                    )
                )
                continue
            stage_run = self.get_stage_run(stage_run_id)
            if stage_run is None:
                raise StorageIntegrityError(
                    f"{entity_type} {entity_id} references missing stage run {stage_run_id}"
                )
            pipeline_run = self.get_pipeline_run(stage_run.pipeline_run_id)
            if pipeline_run is None:
                raise StorageIntegrityError(
                    f"stage run {stage_run.id} references missing pipeline run "
                    f"{stage_run.pipeline_run_id}"
                )
            steps.append(
                ProcessingStep(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    stage_run=stage_run,
                    pipeline_run=pipeline_run,
                )
            )
        return ProcessingProvenance(atom_id=atom_id, steps=tuple(steps), gaps=tuple(gaps))

    load_provenance = get_provenance
    trace_knowledge_atom = get_provenance

    def save_pipeline_run(self, item: PipelineRun) -> PipelineRun:
        values = {
            "id": item.id,
            "pipeline_version": item.pipeline_version,
            "status": item.status.value,
            "started_at": _iso(item.started_at),
            "finished_at": _iso(item.finished_at),
            "input_ref": item.input_ref,
            "output_ref": item.output_ref,
            "error": item.error,
            "metadata": item.metadata,
        }
        with self.engine.begin() as connection:
            existing_status = connection.execute(
                select(pipeline_runs.c.status).where(pipeline_runs.c.id == item.id)
            ).scalar_one_or_none()
            if existing_status is None and item.status is not PipelineRunStatus.STARTED:
                raise InvalidStateTransitionError(
                    f"new PipelineRun {item.id} must start in STARTED state"
                )
            if item.status.value in {
                PipelineRunStatus.SUCCEEDED.value,
                PipelineRunStatus.FAILED.value,
            } and existing_status == PipelineRunStatus.STARTED.value:
                child_statuses = tuple(
                    connection.execute(
                        select(stage_runs.c.status).where(stage_runs.c.pipeline_run_id == item.id)
                    ).scalars()
                )
                if item.status is PipelineRunStatus.SUCCEEDED:
                    if any(status != StageRunStatus.SUCCEEDED.value for status in child_statuses):
                        raise InvalidStateTransitionError(
                            f"PipelineRun {item.id} cannot succeed with non-succeeded stages"
                        )
                elif any(status == StageRunStatus.STARTED.value for status in child_statuses):
                    raise InvalidStateTransitionError(
                        f"PipelineRun {item.id} cannot fail with started stages"
                    )
            self._persist_lifecycle(
                connection,
                pipeline_runs,
                values,
                entity_type="PipelineRun",
                immutable_fields=("id", "pipeline_version", "started_at", "input_ref", "metadata"),
                mutable_fields=("status", "finished_at", "output_ref", "error"),
                status_field="status",
                terminal_statuses=(
                    PipelineRunStatus.SUCCEEDED.value,
                    PipelineRunStatus.FAILED.value,
                ),
            )
        persisted = self.get_pipeline_run(item.id)
        if persisted is None:
            raise StorageIntegrityError(f"pipeline run disappeared after save: {item.id}")
        return persisted

    def get_pipeline_run(self, run_id: str) -> PipelineRun | None:
        with self.engine.connect() as connection:
            row = self._row(connection, pipeline_runs, run_id)
        if not row:
            return None
        return PipelineRun(
            id=row["id"],
            pipeline_version=row["pipeline_version"],
            status=PipelineRunStatus(row["status"]),
            started_at=_dt(row["started_at"]),
            finished_at=_dt(row["finished_at"]),
            input_ref=row["input_ref"],
            output_ref=row["output_ref"],
            error=row["error"],
            metadata=_from_json(row["metadata"]),
        )

    def list_pipeline_runs(self) -> tuple[PipelineRun, ...]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(pipeline_runs.c.id).order_by(pipeline_runs.c.started_at)
            ).all()
        return tuple(item for row in rows if (item := self.get_pipeline_run(row[0])) is not None)

    def save_stage_run(self, item: StageRun) -> StageRun:
        values = {
            "id": item.id,
            "pipeline_run_id": item.pipeline_run_id,
            "stage_name": item.stage_name,
            "stage_version": item.stage_version,
            "status": item.status.value,
            "model": item.model,
            "provider": item.provider,
            "prompt_id": item.prompt_id,
            "prompt_version": item.prompt_version,
            "input_ref": item.input_ref,
            "output_ref": item.output_ref,
            "started_at": _iso(item.started_at),
            "finished_at": _iso(item.finished_at),
            "error_type": item.error_type,
            "error": item.error,
        }
        with self.engine.begin() as connection:
            existing_stage = connection.execute(
                select(stage_runs.c.id).where(stage_runs.c.id == item.id)
            ).scalar_one_or_none()
            if existing_stage is None:
                pipeline_status = connection.execute(
                    select(pipeline_runs.c.status).where(pipeline_runs.c.id == item.pipeline_run_id)
                ).scalar_one_or_none()
                if pipeline_status is None:
                    raise StorageIntegrityError(
                        f"pipeline run does not exist: {item.pipeline_run_id}"
                    )
                if pipeline_status != PipelineRunStatus.STARTED.value:
                    raise InvalidStateTransitionError(
                        f"cannot create StageRun {item.id} under terminal PipelineRun "
                        f"{item.pipeline_run_id}"
                    )
                if item.status is not StageRunStatus.STARTED:
                    raise InvalidStateTransitionError(
                        f"new StageRun {item.id} must start in STARTED state"
                    )
            self._persist_lifecycle(
                connection,
                stage_runs,
                values,
                entity_type="StageRun",
                immutable_fields=(
                    "id",
                    "pipeline_run_id",
                    "stage_name",
                    "stage_version",
                    "model",
                    "provider",
                    "prompt_id",
                    "prompt_version",
                    "input_ref",
                    "started_at",
                ),
                mutable_fields=("status", "finished_at", "output_ref", "error_type", "error"),
                status_field="status",
                terminal_statuses=(
                    StageRunStatus.SUCCEEDED.value,
                    StageRunStatus.FAILED.value,
                ),
            )
        persisted = self.get_stage_run(item.id)
        if persisted is None:
            raise StorageIntegrityError(f"stage run disappeared after save: {item.id}")
        return persisted

    def get_stage_run(self, stage_run_id: str) -> StageRun | None:
        with self.engine.connect() as connection:
            row = self._row(connection, stage_runs, stage_run_id)
        if not row:
            return None
        return StageRun(
            id=row["id"],
            pipeline_run_id=row["pipeline_run_id"],
            stage_name=row["stage_name"],
            stage_version=row["stage_version"],
            status=StageRunStatus(row["status"]),
            model=row["model"],
            provider=row["provider"],
            prompt_id=row["prompt_id"],
            prompt_version=row["prompt_version"],
            input_ref=row["input_ref"],
            output_ref=row["output_ref"],
            started_at=_dt(row["started_at"]),
            finished_at=_dt(row["finished_at"]),
            error_type=row["error_type"],
            error=row["error"],
        )

    def list_stage_runs(self, pipeline_run_id: str | None = None) -> tuple[StageRun, ...]:
        statement = select(stage_runs.c.id).order_by(stage_runs.c.started_at)
        if pipeline_run_id is not None:
            statement = statement.where(stage_runs.c.pipeline_run_id == pipeline_run_id)
        with self.engine.connect() as connection:
            rows = connection.execute(statement).all()
        return tuple(item for row in rows if (item := self.get_stage_run(row[0])) is not None)

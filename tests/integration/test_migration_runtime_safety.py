from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from tests.fixtures.legacy_phase0_schema import create_legacy_01e0ce8_schema

from research_library.storage import SQLiteRepository, StorageIntegrityError

TIMESTAMP = "2026-01-01T00:00:00+00:00"


def _migration_config(db_path: Path) -> Config:
    config = Config()
    config.set_main_option(
        "script_location",
        str(Path(__file__).parents[2] / "src" / "research_library" / "storage" / "migrations"),
    )
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite+pysqlite:///{db_path.resolve().as_posix()}".replace("%", "%%"),
    )
    return config


def _stamp_legacy(engine) -> object:
    legacy = create_legacy_01e0ce8_schema(engine)
    with engine.begin() as connection:
        config = Config()
        config.set_main_option(
            "script_location",
            str(Path(__file__).parents[2] / "src" / "research_library" / "storage" / "migrations"),
        )
        config.set_main_option("sqlalchemy.url", str(engine.url).replace("%", "%%"))
        config.attributes["connection"] = connection
        command.stamp(config, "0001_phase0")
    return legacy


def _populate_legacy(engine, *, invalid_stage: bool = False) -> None:
    legacy = _stamp_legacy(engine)
    pipeline_runs = legacy.tables["pipeline_runs"]
    stage_runs = legacy.tables["stage_runs"]
    sources = legacy.tables["sources"]
    snapshots = legacy.tables["source_snapshots"]
    evidence = legacy.tables["evidence"]
    claims = legacy.tables["claims"]
    groups = legacy.tables["claim_groups"]
    members = legacy.tables["claim_group_members"]
    links = legacy.tables["evidence_links"]
    resolved = legacy.tables["resolved_claims"]
    atoms = legacy.tables["knowledge_atoms"]
    stage_id = "missing-stage" if invalid_stage else "old-stage"
    with engine.begin() as connection:
        connection.execute(
            pipeline_runs.insert().values(
                id="old-run",
                pipeline_version="legacy-pipeline",
                status="started",
                started_at=TIMESTAMP,
                metadata={},
            )
        )
        connection.execute(
            stage_runs.insert().values(
                id="old-stage",
                pipeline_run_id="old-run",
                stage_name="legacy-stage",
                stage_version="legacy-v1",
                status="succeeded",
                started_at=TIMESTAMP,
                finished_at=TIMESTAMP,
            )
        )
        connection.execute(
            sources.insert().values(
                id="old-source",
                source_type="paper",
                canonical_uri="https://example.test/legacy",
                metadata={},
                created_at=TIMESTAMP,
            )
        )
        connection.execute(
            snapshots.insert().values(
                id="old-snapshot",
                source_id="old-source",
                retrieved_at=TIMESTAMP,
                content_hash="a" * 64,
                content_ref="old-source/old-snapshot/content",
                metadata={},
                created_by_stage_run_id=stage_id,
            )
        )
        connection.execute(
            evidence.insert().values(
                id="old-evidence",
                snapshot_id="old-snapshot",
                text="legacy quote",
                metadata={},
                created_at=TIMESTAMP,
                created_by_stage_run_id=stage_id,
            )
        )
        connection.execute(
            claims.insert().values(
                id="old-claim",
                statement="legacy fact",
                qualifiers={},
                extraction_confidence="0.75",
                created_at=TIMESTAMP,
                created_by_stage_run_id=stage_id,
            )
        )
        connection.execute(
            groups.insert().values(
                id="old-group",
                canonical_key="legacy-fact",
                created_at=TIMESTAMP,
            )
        )
        connection.execute(
            members.insert().values(claim_group_id="old-group", claim_id="old-claim")
        )
        connection.execute(
            links.insert().values(
                id="old-link",
                evidence_id="old-evidence",
                claim_id="old-claim",
                relation_type="supports",
                created_at=TIMESTAMP,
                created_by_stage_run_id=stage_id,
            )
        )
        connection.execute(
            resolved.insert().values(
                id="old-resolved",
                claim_group_id="old-group",
                canonical_statement="legacy fact",
                status="resolved",
                confidence="0.75",
                created_at=TIMESTAMP,
                created_by_stage_run_id=stage_id,
            )
        )
        connection.execute(
            atoms.insert().values(
                id="old-atom",
                resolved_claim_id="old-resolved",
                statement="legacy fact",
                confidence="0.75",
                qualifiers={},
                created_at=TIMESTAMP,
                created_by_stage_run_id=stage_id,
            )
        )


def _revision(engine) -> str:
    with engine.connect() as connection:
        return connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()


def _assert_legacy_revision_and_data_are_unchanged(engine) -> None:
    assert _revision(engine) == "0001_phase0"
    inspector = sa.inspect(engine)
    assert not any(
        foreign_key["referred_table"] == "stage_runs"
        for foreign_key in inspector.get_foreign_keys("claims")
    )
    with engine.connect() as connection:
        assert connection.execute(
            sa.text(
                "SELECT created_by_stage_run_id FROM claims WHERE id = 'old-claim'"
            )
        ).scalar_one() == "missing-stage"


def test_populated_legacy_database_upgrades_through_repository_path(tmp_path) -> None:
    db_path = tmp_path / "repository-populated-legacy.sqlite"
    engine = sa.create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    _populate_legacy(engine)
    engine.dispose()

    with SQLiteRepository(db_path, tmp_path / "snapshots") as repository:
        assert _revision(repository.engine) == "0003_phase1_refinery_domain"
        assert repository.get_knowledge_atom("old-atom") is not None
        provenance = repository.get_processing_provenance("old-atom")
        assert all(step.stage_run.id == "old-stage" for step in provenance.steps)
        with repository.engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []


def test_invalid_legacy_processing_reference_fails_repository_upgrade_without_repair(
    tmp_path,
) -> None:
    db_path = tmp_path / "repository-invalid-legacy.sqlite"
    engine = sa.create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    _populate_legacy(engine, invalid_stage=True)
    with pytest.raises(StorageIntegrityError, match="foreign key violation"):
        SQLiteRepository(db_path, tmp_path / "snapshots", engine=engine)

    _assert_legacy_revision_and_data_are_unchanged(engine)
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    engine.dispose()


def test_populated_legacy_database_upgrades_through_standalone_alembic_path(tmp_path) -> None:
    db_path = tmp_path / "cli-populated-legacy.sqlite"
    engine = sa.create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    _populate_legacy(engine)
    engine.dispose()

    command.upgrade(_migration_config(db_path), "head")
    check_engine = sa.create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    try:
        assert _revision(check_engine) == "0003_phase1_refinery_domain"
        with check_engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    finally:
        check_engine.dispose()


def test_invalid_legacy_processing_reference_fails_standalone_alembic_path(tmp_path) -> None:
    db_path = tmp_path / "cli-invalid-legacy.sqlite"
    engine = sa.create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    _populate_legacy(engine, invalid_stage=True)
    engine.dispose()

    with pytest.raises(StorageIntegrityError, match="foreign key violation"):
        command.upgrade(_migration_config(db_path), "head")

    check_engine = sa.create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    try:
        _assert_legacy_revision_and_data_are_unchanged(check_engine)
    finally:
        check_engine.dispose()

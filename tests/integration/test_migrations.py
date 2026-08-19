from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from tests.fixtures.legacy_phase0_schema import create_legacy_01e0ce8_schema

from research_library.storage import ProcessingGap, SQLiteRepository


def _migration_config(engine) -> Config:
    config = Config()
    config.set_main_option(
        "script_location",
        str(Path(__file__).parents[2] / "src" / "research_library" / "storage" / "migrations"),
    )
    config.set_main_option("sqlalchemy.url", str(engine.url).replace("%", "%%"))
    return config


def _migrate(engine, revision: str) -> None:
    with engine.begin() as connection:
        config = _migration_config(engine)
        config.attributes["connection"] = connection
        command.upgrade(config, revision)


def _stamp(engine, revision: str) -> None:
    with engine.begin() as connection:
        config = _migration_config(engine)
        config.attributes["connection"] = connection
        command.stamp(config, revision)


def _downgrade(engine, revision: str) -> None:
    with engine.begin() as connection:
        config = _migration_config(engine)
        config.attributes["connection"] = connection
        command.downgrade(config, revision)


def _schema_signature(engine) -> dict[str, object]:
    inspector = sa.inspect(engine)
    signature: dict[str, object] = {}
    for table in sorted(name for name in inspector.get_table_names() if name != "alembic_version"):
        columns = tuple(
            sorted(
                (
                    column["name"],
                    column["type"].__class__.__name__,
                    column["nullable"],
                )
                for column in inspector.get_columns(table)
            )
        )
        primary_key = tuple(inspector.get_pk_constraint(table).get("constrained_columns", ()))
        foreign_keys = tuple(
            sorted(
                (
                    tuple(foreign_key["constrained_columns"]),
                    foreign_key["referred_table"],
                    tuple(foreign_key["referred_columns"]),
                )
                for foreign_key in inspector.get_foreign_keys(table)
            )
        )
        unique_constraints = tuple(
            sorted(
                tuple(item.get("column_names", ()))
                for item in inspector.get_unique_constraints(table)
            )
        )
        indexes = tuple(
            sorted(
                (item["name"], tuple(item.get("column_names", ())))
                for item in inspector.get_indexes(table)
            )
        )
        signature[table] = (columns, primary_key, foreign_keys, unique_constraints, indexes)
    return signature


def test_fresh_database_is_at_phase1a_head(repository) -> None:
    version = repository.engine.connect().exec_driver_sql(
        "SELECT version_num FROM alembic_version"
    ).scalar_one()
    assert version == "0003_phase1_refinery_domain"


def test_historical_0001_does_not_follow_live_metadata() -> None:
    path = (
        Path(__file__).parents[2]
        / "src"
        / "research_library"
        / "storage"
        / "migrations"
        / "versions"
        / "0001_phase0.py"
    )
    source = path.read_text(encoding="utf-8")
    assert "create_all" not in source
    assert "drop_all" not in source
    assert "schema import metadata" not in source


def test_legacy_0001_data_upgrades_to_0002(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'legacy.sqlite').as_posix()}")
    _migrate(engine, "0001_phase0")
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO sources "
                "(id, source_type, canonical_uri, metadata, created_at) "
                "VALUES ('source-1', 'web', 'https://example.test', '{}', "
                "'2026-01-01T00:00:00+00:00')"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO claims "
                "(id, statement, qualifiers, extraction_confidence, created_at) "
                "VALUES ('claim-1', 'legacy claim', '{}', '0.75', '2026-01-01T00:00:00+00:00')"
            )
        )
    _migrate(engine, "head")
    inspector = sa.inspect(engine)
    columns = {item["name"]: item for item in inspector.get_columns("claims")}
    assert columns["extraction_confidence"]["type"].__class__.__name__ == "FLOAT"
    assert "created_by_stage_run_id" in columns
    with engine.connect() as connection:
        assert connection.execute(
            sa.text("SELECT extraction_confidence FROM claims WHERE id = 'claim-1'")
        ).scalar_one() == 0.75


def test_explicit_0001_matches_independent_01e0ce8_schema(tmp_path) -> None:
    migration_engine = sa.create_engine(
        f"sqlite+pysqlite:///{(tmp_path / 'migration.sqlite').as_posix()}"
    )
    legacy_engine = sa.create_engine(
        f"sqlite+pysqlite:///{(tmp_path / 'legacy-fixture.sqlite').as_posix()}"
    )
    _migrate(migration_engine, "0001_phase0")
    create_legacy_01e0ce8_schema(legacy_engine)
    assert _schema_signature(migration_engine) == _schema_signature(legacy_engine)


def test_real_legacy_fixture_stamp_upgrade_preserves_processing_lineage(tmp_path) -> None:
    db_path = tmp_path / "real-legacy.sqlite"
    engine = sa.create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    legacy = create_legacy_01e0ce8_schema(engine)
    _stamp(engine, "0001_phase0")
    timestamp = "2026-01-01T00:00:00+00:00"
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
    with engine.begin() as connection:
        connection.execute(
            pipeline_runs.insert().values(
                id="old-run",
                pipeline_version="legacy-pipeline",
                status="started",
                started_at=timestamp,
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
                started_at=timestamp,
                finished_at=timestamp,
            )
        )
        connection.execute(
            sources.insert().values(
                id="old-source",
                source_type="paper",
                canonical_uri="https://example.test/legacy",
                metadata={},
                created_at=timestamp,
            )
        )
        connection.execute(
            snapshots.insert().values(
                id="old-snapshot",
                source_id="old-source",
                retrieved_at=timestamp,
                content_hash="a" * 64,
                content_ref="old-source/old-snapshot/content",
                metadata={},
                created_by_stage_run_id="old-stage",
            )
        )
        connection.execute(
            evidence.insert().values(
                id="old-evidence",
                snapshot_id="old-snapshot",
                text="legacy quote",
                metadata={},
                created_at=timestamp,
                created_by_stage_run_id="old-stage",
            )
        )
        connection.execute(
            claims.insert().values(
                id="old-claim",
                statement="legacy fact",
                qualifiers={},
                extraction_confidence="0.75",
                created_at=timestamp,
                created_by_stage_run_id="old-stage",
            )
        )
        connection.execute(
            groups.insert().values(
                id="old-group",
                canonical_key="legacy-fact",
                created_at=timestamp,
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
                created_at=timestamp,
                created_by_stage_run_id="old-stage",
            )
        )
        connection.execute(
            resolved.insert().values(
                id="old-resolved",
                claim_group_id="old-group",
                canonical_statement="legacy fact",
                status="resolved",
                confidence="0.75",
                created_at=timestamp,
                created_by_stage_run_id="old-stage",
            )
        )
        connection.execute(
            atoms.insert().values(
                id="old-atom",
                resolved_claim_id="old-resolved",
                statement="legacy fact",
                confidence="0.75",
                qualifiers={},
                created_at=timestamp,
                created_by_stage_run_id="old-stage",
            )
        )
    _migrate(engine, "head")
    with SQLiteRepository(db_path, tmp_path / "snapshots", engine=engine) as repository:
        atom = repository.get_knowledge_atom("old-atom")
        assert atom.confidence == 0.75
        assert repository.get_claim("old-claim").extraction_confidence == 0.75
        processing = repository.get_processing_provenance("old-atom")
        assert not processing.is_complete
        assert processing.gaps == (
            ProcessingGap(entity_type="claim_group", entity_id="old-group", reason="not_recorded"),
        )
        assert all(step.stage_run.id == "old-stage" for step in processing.steps)
        assert all(step.pipeline_run.id == "old-run" for step in processing.steps)


def test_legacy_numeric_boundaries_convert_to_float(tmp_path) -> None:
    db_path = tmp_path / "numeric-legacy.sqlite"
    engine = sa.create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    legacy = create_legacy_01e0ce8_schema(engine)
    _stamp(engine, "0001_phase0")
    timestamp = "2026-01-01T00:00:00+00:00"
    claims = legacy.tables["claims"]
    with engine.begin() as connection:
        for claim_id, confidence in (
            ("numeric-zero", "0.0"),
            ("numeric-mid", "0.75"),
            ("numeric-one", "1.0"),
            ("numeric-null", None),
        ):
            connection.execute(
                claims.insert().values(
                    id=claim_id,
                    statement=claim_id,
                    qualifiers={},
                    extraction_confidence=confidence,
                    created_at=timestamp,
                )
            )
    _migrate(engine, "head")
    with engine.connect() as connection:
        values = connection.execute(
            sa.text(
                "SELECT id, extraction_confidence FROM claims "
                "WHERE id LIKE 'numeric-%' ORDER BY id"
            )
        ).all()
    assert values == [
        ("numeric-mid", 0.75),
        ("numeric-null", None),
        ("numeric-one", 1.0),
        ("numeric-zero", 0.0),
    ]


def test_phase1a_schema_round_trips_to_phase0_and_back(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'roundtrip.sqlite').as_posix()}")
    _migrate(engine, "head")
    _downgrade(engine, "0001_phase0")
    legacy_engine = sa.create_engine(
        f"sqlite+pysqlite:///{(tmp_path / 'roundtrip-legacy.sqlite').as_posix()}"
    )
    create_legacy_01e0ce8_schema(legacy_engine)
    assert _schema_signature(engine) == _schema_signature(legacy_engine)
    _migrate(engine, "head")
    with engine.connect() as connection:
        assert connection.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar_one() == "0003_phase1_refinery_domain"
        assert "created_by_stage_run_id" in {
            item["name"] for item in sa.inspect(engine).get_columns("knowledge_atoms")
        }


def test_ci_is_pr_main_push_dispatch_and_has_freeze_checks() -> None:
    workflow = (Path(__file__).parents[2] / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert "      - main" in workflow
    assert "workflow_dispatch:" in workflow
    assert "timeout-minutes: 10" in workflow
    assert "cache: \"pip\"" in workflow
    assert "python -m compileall -q src tests" in workflow
    assert "git diff --check" in workflow

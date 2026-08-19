from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from tests.fixtures.legacy_phase0_schema import create_legacy_01e0ce8_schema

from research_library.storage import SQLiteRepository
from research_library.storage.schema import metadata


def _config(engine) -> Config:
    config = Config()
    config.set_main_option(
        "script_location",
        str(Path(__file__).parents[2] / "src" / "research_library" / "storage" / "migrations"),
    )
    config.set_main_option("sqlalchemy.url", str(engine.url).replace("%", "%%"))
    return config


def _upgrade(engine, revision: str = "head") -> None:
    with engine.begin() as connection:
        config = _config(engine)
        config.attributes["connection"] = connection
        command.upgrade(config, revision)


def _downgrade(engine, revision: str) -> None:
    with engine.begin() as connection:
        config = _config(engine)
        config.attributes["connection"] = connection
        command.downgrade(config, revision)


def _stamp(engine, revision: str) -> None:
    with engine.begin() as connection:
        config = _config(engine)
        config.attributes["connection"] = connection
        command.stamp(config, revision)


def test_phase1_schema_metadata_matches_migrated_head(repository) -> None:
    inspector = sa.inspect(repository.engine)
    actual_tables = set(inspector.get_table_names()) - {"alembic_version"}
    expected_tables = set(metadata.tables)
    assert actual_tables == expected_tables
    for table_name, table in metadata.tables.items():
        assert {column.name for column in table.columns} == {
            column["name"] for column in inspector.get_columns(table_name)
        }
        expected_foreign_keys = {
            (foreign_key.parent.name, foreign_key.target_fullname)
            for foreign_key in table.foreign_keys
        }
        actual_foreign_keys = {
            (columns[0], f"{foreign_key['referred_table']}.{foreign_key['referred_columns'][0]}")
            for foreign_key in inspector.get_foreign_keys(table_name)
            for columns in [foreign_key["constrained_columns"]]
        }
        assert actual_foreign_keys == expected_foreign_keys
        expected_indexes = {
            (index.name, tuple(column.name for column in index.columns))
            for index in table.indexes
        }
        actual_indexes = {
            (index["name"], tuple(index.get("column_names", ())))
            for index in inspector.get_indexes(table_name)
        }
        assert actual_indexes == expected_indexes
    with repository.engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []


def test_0002_to_0003_backfills_phase0_data_without_promoting_atoms(tmp_path) -> None:
    db_path = tmp_path / "legacy-phase1.sqlite"
    engine = sa.create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    legacy = create_legacy_01e0ce8_schema(engine)
    _stamp(engine, "0001_phase0")
    timestamp = "2026-08-19T00:00:00+00:00"
    with engine.begin() as connection:
        connection.execute(
            legacy.tables["sources"].insert(),
            [
                {
                    "id": "legacy-source",
                    "source_type": "web",
                    "canonical_uri": "https://example.test/legacy",
                    "metadata": {},
                    "created_at": timestamp,
                },
                {
                    "id": "legacy-parent",
                    "source_type": "web",
                    "canonical_uri": "https://example.test/parent",
                    "metadata": {},
                    "created_at": timestamp,
                },
            ],
        )
        connection.execute(
            legacy.tables["claims"].insert().values(
                id="legacy-claim",
                statement="legacy statement",
                qualifiers={},
                created_at=timestamp,
            )
        )
        connection.execute(
            legacy.tables["claim_groups"].insert().values(
                id="legacy-group",
                canonical_key="legacy-key",
                name="Legacy Name",
                created_at=timestamp,
            )
        )
        connection.execute(
            legacy.tables["claim_group_members"].insert().values(
                claim_group_id="legacy-group", claim_id="legacy-claim"
            )
        )
        connection.execute(
            legacy.tables["resolved_claims"].insert().values(
                id="legacy-resolved",
                claim_group_id="legacy-group",
                canonical_statement="legacy statement",
                status="resolved",
                confidence="0.75",
                created_at=timestamp,
            )
        )
        connection.execute(
            legacy.tables["knowledge_atoms"].insert().values(
                id="legacy-atom",
                resolved_claim_id="legacy-resolved",
                statement="legacy statement",
                confidence="0.75",
                qualifiers={},
                created_at=timestamp,
            )
        )
        connection.execute(
            legacy.tables["source_dependencies"].insert().values(
                id="legacy-dependency",
                source_id="legacy-source",
                parent_source_id="legacy-parent",
                independence_score="0.2",
            )
        )
    _upgrade(engine)

    with SQLiteRepository(db_path, tmp_path / "snapshots", engine=engine) as repository:
        group = repository.get_claim_group("legacy-group")
        atom = repository.get_knowledge_atom("legacy-atom")
        resolved = repository.get_resolved_claim("legacy-resolved")
        dependency = repository.get_source_dependency("legacy-dependency")
        membership = repository.get_claim_group_membership("legacy-group", "legacy-claim")
        assert group.canonical_statement == "Legacy Name"
        assert group.qualifiers == {}
        assert membership is not None
        assert membership.created_at is None
        assert membership.created_by_stage_run_id is None
        assert atom.status.value == "withheld"
        assert atom.subject is None and atom.predicate is None and atom.object is None
        assert resolved.resolution_decision_id is None
        assert resolved.confidence_assessment_id is None
        assert dependency.relation_type.value == "possibly_dependent"
        assert dependency.signals == {}
        with repository.engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []


def test_phase1_migration_downgrade_and_reupgrade_are_reversible(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'roundtrip.sqlite').as_posix()}")
    _upgrade(engine)
    _downgrade(engine, "0002_phase0_hardening")
    inspector = sa.inspect(engine)
    assert "resolution_decisions" not in inspector.get_table_names()
    assert "canonical_statement" not in {
        column["name"] for column in inspector.get_columns("claim_groups")
    }
    _upgrade(engine)
    assert "resolution_decisions" in sa.inspect(engine).get_table_names()
    with engine.connect() as connection:
        version = connection.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        assert version == "0004_phase1_llm_audit"

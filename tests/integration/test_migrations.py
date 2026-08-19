from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config


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
        command.upgrade(config, revision) if revision != "0001_phase0" else command.upgrade(
            config, revision
        )


def test_fresh_database_is_at_hardened_head(repository) -> None:
    version = repository.engine.connect().exec_driver_sql(
        "SELECT version_num FROM alembic_version"
    ).scalar_one()
    assert version == "0002_phase0_hardening"


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


def test_hardened_schema_round_trips_0002_to_0001_to_0002(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'roundtrip.sqlite').as_posix()}")
    _migrate(engine, "head")
    _migrate(engine, "0001_phase0")
    _migrate(engine, "head")
    with engine.connect() as connection:
        assert connection.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar_one() == "0002_phase0_hardening"
        assert "created_by_stage_run_id" in {
            item["name"] for item in sa.inspect(engine).get_columns("knowledge_atoms")
        }

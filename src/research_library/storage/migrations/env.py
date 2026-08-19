"""Alembic environment supporting both CLI and repository-managed upgrades."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from research_library.storage.migration_safety import run_migrations_with_safety
from research_library.storage.schema import metadata

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is None:
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
        with connectable.connect() as generated_connection:
            def migrate() -> None:
                context.configure(connection=generated_connection, target_metadata=target_metadata)
                with context.begin_transaction():
                    context.run_migrations()

            run_migrations_with_safety(generated_connection, migrate)
        connectable.dispose()
        return
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

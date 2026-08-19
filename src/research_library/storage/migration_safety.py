"""Small SQLite guards for schema rebuild migrations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .errors import StorageIntegrityError


def is_sqlite(connection: Any) -> bool:
    return connection.dialect.name == "sqlite"


def set_sqlite_foreign_keys(connection: Any, enabled: bool) -> None:
    """Toggle SQLite FK enforcement only when the connection is outside a transaction."""

    if not is_sqlite(connection):
        return
    if connection.in_transaction():
        raise StorageIntegrityError("SQLite foreign_keys PRAGMA requires an inactive transaction")
    value = "ON" if enabled else "OFF"
    connection.exec_driver_sql(f"PRAGMA foreign_keys={value}")
    actual = int(connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one())
    if connection.in_transaction():
        connection.commit()
    expected = 1 if enabled else 0
    if actual != expected:
        raise StorageIntegrityError(
            f"SQLite foreign_keys could not be set to {expected}; observed {actual}"
        )


def sqlite_foreign_key_violations(connection: Any) -> tuple[tuple[Any, ...], ...]:
    if not is_sqlite(connection):
        return ()
    return tuple(tuple(row) for row in connection.exec_driver_sql("PRAGMA foreign_key_check").all())


def _raise_on_foreign_key_violations(connection: Any) -> None:
    violations = sqlite_foreign_key_violations(connection)
    if not violations:
        return
    samples = "; ".join(
        f"table={row[0]!r}, rowid={row[1]!r}, parent={row[2]!r}, fkid={row[3]!r}"
        for row in violations[:5]
    )
    raise StorageIntegrityError(f"foreign key violation(s): {samples}")


def run_migrations_with_safety(connection: Any, migrate: Callable[[], None]) -> None:
    """Run migrations in a controlled transaction and restore SQLite FK enforcement."""

    if not is_sqlite(connection):
        transaction = connection.begin()
        try:
            migrate()
            transaction.commit()
        except Exception:
            if transaction.is_active:
                transaction.rollback()
            raise
        return

    set_sqlite_foreign_keys(connection, False)
    transaction = connection.begin()
    try:
        migrate()
        _raise_on_foreign_key_violations(connection)
        transaction.commit()
    except Exception:
        if transaction.is_active:
            transaction.rollback()
        raise
    finally:
        if transaction.is_active:
            transaction.rollback()
        set_sqlite_foreign_keys(connection, True)

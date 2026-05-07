from __future__ import annotations

import sqlite3
from pathlib import Path

from src.db.migrate import SCHEMA_PATH, migrate

_EXPECTED_TABLES = {"raw_content", "canonical_records", "change_history", "validation_failed"}


def _table_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as con:
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row[0] for row in rows}


def test_migrate_creates_all_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    assert _EXPECTED_TABLES.issubset(_table_names(db_path))


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    migrate(db_path)  # second call must not raise or corrupt
    assert _EXPECTED_TABLES.issubset(_table_names(db_path))


def test_migrate_creates_parent_dir(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "dir" / "test.db"
    migrate(db_path)
    assert db_path.exists()


def test_schema_file_exists() -> None:
    assert SCHEMA_PATH.exists(), f"schema.sql not found at {SCHEMA_PATH}"

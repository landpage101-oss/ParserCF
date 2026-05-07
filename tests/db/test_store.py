from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

from src.db.migrate import SCHEMA_PATH
from src.db.store import append_validation_failure, record_attempt, upsert_canonical


@pytest.fixture
def con() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return c


# ---------------------------------------------------------------------------
# record_attempt
# ---------------------------------------------------------------------------


def test_record_attempt_returns_row_id(con: sqlite3.Connection) -> None:
    raw_id = record_attempt(con, "test_src", "id-1", "https://example.com", {"k": "v"}, "trace-1")
    assert isinstance(raw_id, int)
    assert raw_id >= 1


def test_record_attempt_stores_correct_content_hash(con: sqlite3.Connection) -> None:
    payload = {"title": "Hello", "body": "World"}
    raw_id = record_attempt(con, "test_src", "id-2", "https://example.com/2", payload, "t2")
    row = con.execute(
        "SELECT content_hash, raw_payload FROM raw_content WHERE id = ?", (raw_id,)
    ).fetchone()
    expected_hash = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    assert row[0] == expected_hash


def test_record_attempt_raw_payload_differs_from_validated(con: sqlite3.Connection) -> None:
    # Raw payload may have extra fields that Pydantic would strip
    raw = {"title": "Doc", "body": "content", "_firecrawl_meta": "extra"}
    raw_id = record_attempt(con, "src", "id-3", "https://x.com/3", raw, "t3")
    stored = json.loads(
        con.execute("SELECT raw_payload FROM raw_content WHERE id = ?", (raw_id,)).fetchone()[0]
    )
    assert stored["_firecrawl_meta"] == "extra"


# ---------------------------------------------------------------------------
# upsert_canonical
# ---------------------------------------------------------------------------


def test_upsert_canonical_creates_record(con: sqlite3.Connection) -> None:
    raw_id = record_attempt(con, "src", "id-10", "https://x.com/10", {"a": 1}, "t10")
    upsert_canonical(con, "src", "id-10", "https://x.com/10", {"a": 1}, raw_id)
    row = con.execute(
        "SELECT source_id, payload FROM canonical_records WHERE source = ? AND source_id = ?",
        ("src", "id-10"),
    ).fetchone()
    assert row is not None
    assert json.loads(row[1]) == {"a": 1}


def test_upsert_canonical_updates_existing_record(con: sqlite3.Connection) -> None:
    raw_id1 = record_attempt(con, "src", "id-20", "https://x.com/20", {"a": 1}, "t20a")
    upsert_canonical(con, "src", "id-20", "https://x.com/20", {"a": 1}, raw_id1)

    raw_id2 = record_attempt(con, "src", "id-20", "https://x.com/20", {"a": 2}, "t20b")
    upsert_canonical(con, "src", "id-20", "https://x.com/20", {"a": 2}, raw_id2)

    row = con.execute(
        "SELECT payload FROM canonical_records WHERE source = ? AND source_id = ?",
        ("src", "id-20"),
    ).fetchone()
    assert json.loads(row[0]) == {"a": 2}


def test_change_history_written_on_field_change(con: sqlite3.Connection) -> None:
    raw_id1 = record_attempt(con, "src", "id-30", "https://x.com/30", {"title": "old"}, "t30a")
    upsert_canonical(con, "src", "id-30", "https://x.com/30", {"title": "old"}, raw_id1)

    raw_id2 = record_attempt(con, "src", "id-30", "https://x.com/30", {"title": "new"}, "t30b")
    upsert_canonical(con, "src", "id-30", "https://x.com/30", {"title": "new"}, raw_id2)

    rows = con.execute(
        "SELECT field, old_value, new_value FROM change_history WHERE source = ? AND source_id = ?",
        ("src", "id-30"),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "title"
    assert json.loads(rows[0][1]) == "old"
    assert json.loads(rows[0][2]) == "new"


def test_change_history_not_written_when_no_change(con: sqlite3.Connection) -> None:
    payload = {"title": "same"}
    raw_id1 = record_attempt(con, "src", "id-40", "https://x.com/40", payload, "t40a")
    upsert_canonical(con, "src", "id-40", "https://x.com/40", payload, raw_id1)

    raw_id2 = record_attempt(con, "src", "id-40", "https://x.com/40", payload, "t40b")
    upsert_canonical(con, "src", "id-40", "https://x.com/40", payload, raw_id2)

    count = con.execute(
        "SELECT COUNT(*) FROM change_history WHERE source = ? AND source_id = ?",
        ("src", "id-40"),
    ).fetchone()[0]
    assert count == 0


# ---------------------------------------------------------------------------
# append_validation_failure
# ---------------------------------------------------------------------------


def test_append_validation_failure_writes_record(con: sqlite3.Connection) -> None:
    raw_id = record_attempt(con, "src", "id-50", "https://x.com/50", {"x": 1}, "t50")
    append_validation_failure(
        con, "src", "https://x.com/50", raw_id, "ValidationError: missing title"
    )
    row = con.execute(
        "SELECT source, url, raw_id, error FROM validation_failed WHERE raw_id = ?",
        (raw_id,),
    ).fetchone()
    assert row is not None
    assert row[0] == "src"
    assert row[2] == raw_id
    assert "ValidationError" in row[3]

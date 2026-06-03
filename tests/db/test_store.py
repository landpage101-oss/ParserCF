from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

import src.safety.trace as trace_module
from src.db.migrate import SCHEMA_PATH
from src.db.store import (
    append_validation_failure,
    get_last_scraped_at,
    record_attempt,
    resolve_validation_failure,
    upsert_canonical,
)


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


# ---------------------------------------------------------------------------
# resolve_validation_failure
# ---------------------------------------------------------------------------


def _make_vf(con: sqlite3.Connection) -> int:
    """Helper: insert one raw + one vf record, return vf id."""
    raw_id = record_attempt(con, "src", "id-vf", "https://x.com/vf", {"x": 1}, "t-vf")
    append_validation_failure(con, "src", "https://x.com/vf", raw_id, "ValidationError: missing")
    return con.execute("SELECT id FROM validation_failed WHERE raw_id = ?", (raw_id,)).fetchone()[0]


def test_resolve_sets_resolved_at_and_resolution(
    con: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(trace_module, "TRACE_DIR", tmp_path)
    vf_id = _make_vf(con)

    resolve_validation_failure(con, vf_id, resolution="fixed", reason="schema normaliser added")

    row = con.execute(
        "SELECT resolved_at, resolution FROM validation_failed WHERE id = ?", (vf_id,)
    ).fetchone()
    assert row[0] is not None  # resolved_at set
    assert row[1] == "fixed"


def test_resolve_writes_trace_span(
    con: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(trace_module, "TRACE_DIR", tmp_path)
    vf_id = _make_vf(con)

    resolve_validation_failure(con, vf_id, resolution="discarded", reason="anti-bot page")

    records = [
        json.loads(line)
        for f in tmp_path.glob("*.jsonl")
        for line in f.read_text().splitlines()
        if line.strip()
    ]
    resolve_spans = [r for r in records if r.get("name") == "resolve_vf"]
    assert len(resolve_spans) == 1
    attrs = resolve_spans[0]["attrs"]
    assert attrs["vf_id"] == vf_id
    assert attrs["resolution"] == "discarded"
    assert attrs["reason"] == "anti-bot page"


def test_resolve_raises_on_unknown_id(
    con: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(trace_module, "TRACE_DIR", tmp_path)
    with pytest.raises(ValueError, match="not found"):
        resolve_validation_failure(con, 9999, resolution="fixed", reason="test")


def test_resolve_raises_if_already_resolved(
    con: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(trace_module, "TRACE_DIR", tmp_path)
    vf_id = _make_vf(con)
    resolve_validation_failure(con, vf_id, resolution="fixed", reason="first")

    with pytest.raises(ValueError, match="already resolved"):
        resolve_validation_failure(con, vf_id, resolution="fixed", reason="duplicate")


def test_resolve_raises_on_invalid_resolution(
    con: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(trace_module, "TRACE_DIR", tmp_path)
    vf_id = _make_vf(con)
    with pytest.raises(ValueError, match="resolution must be one of"):
        resolve_validation_failure(con, vf_id, resolution="typo", reason="test")


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


# ---------------------------------------------------------------------------
# get_last_scraped_at
# ---------------------------------------------------------------------------


def test_get_last_scraped_at_returns_none_for_unknown(con: sqlite3.Connection) -> None:
    result = get_last_scraped_at(con, "src", "id-missing")
    assert result is None


def test_get_last_scraped_at_returns_tz_aware_datetime(con: sqlite3.Connection) -> None:
    raw_id = record_attempt(con, "src", "id-fresh", "https://x.com/fresh", {"a": 1}, "t-fresh")
    upsert_canonical(con, "src", "id-fresh", "https://x.com/fresh", {"a": 1}, raw_id)

    result = get_last_scraped_at(con, "src", "id-fresh")

    assert result is not None
    assert result.tzinfo is not None
    expected_iso = con.execute(
        "SELECT scraped_at FROM raw_content WHERE id = ?", (raw_id,)
    ).fetchone()[0]
    assert result == datetime.fromisoformat(expected_iso)


def test_get_last_scraped_at_reflects_re_scrape(con: sqlite3.Connection) -> None:
    raw_id1 = record_attempt(con, "src", "id-rescr", "https://x.com/rescr", {"a": 1}, "t-rescr-a")
    upsert_canonical(con, "src", "id-rescr", "https://x.com/rescr", {"a": 1}, raw_id1)

    raw_id2 = record_attempt(con, "src", "id-rescr", "https://x.com/rescr", {"a": 2}, "t-rescr-b")
    upsert_canonical(con, "src", "id-rescr", "https://x.com/rescr", {"a": 2}, raw_id2)

    result = get_last_scraped_at(con, "src", "id-rescr")

    expected_iso = con.execute(
        "SELECT scraped_at FROM raw_content WHERE id = ?", (raw_id2,)
    ).fetchone()[0]
    assert result == datetime.fromisoformat(expected_iso)

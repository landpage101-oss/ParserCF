"""Smoke tests for src/run.py batch entry point."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from src.db.migrate import migrate
from src.run import run


class _StubConfig:
    adapter = "src/sources/docs_python_org.py"
    rate_limit_rps = 1.0  # NEW — required by run() since PR-A


class _StubAdapter:
    page_type = "docs"
    domain = "example.invalid"
    name = "stub"

    def __init__(self, urls: list[str] | None = None) -> None:
        self._urls = urls or ["https://docs.python.org/3/library/json.html"]

    def list_urls(self, since: str | None = None) -> list[str]:  # noqa: ARG002
        return list(self._urls)

    def parse_id(self, url: str) -> str:
        return url.rsplit("/", maxsplit=1)[-1].removesuffix(".html")


_STUB_URL = "https://docs.python.org/3/library/json.html"

_VALID_RAW: dict[str, Any] = {
    "source": "docs.python.org",
    "source_url": "https://docs.python.org/3/library/json.html",
    "source_id": "json",
    "title": "json -- JSON encoder and decoder",
    "section_path": [],
    "body_md": "A standard library module for encoding and decoding JSON data.",
    "code_block_count": 0,
    "last_updated": None,
}

_INVALID_RAW: dict[str, Any] = {
    "source": "docs.python.org",
    "source_url": "https://docs.python.org/3/library/json.html",
    "source_id": "json",
    "title": "Error",
    "section_path": [],
    "body_md": "404 not found -- the page you requested does not exist",
    "code_block_count": 0,
    "last_updated": None,
}


def _seed_canonical(db: Path, source: str, source_id: str, url: str, age_days: float) -> None:
    """Insert a canonical record whose backing raw_content.scraped_at is N days ago."""
    ts = (datetime.now(UTC) - timedelta(days=age_days)).isoformat()
    con = sqlite3.connect(db)
    try:
        con.execute(
            "INSERT INTO raw_content (source, source_id, url, content_hash, "
            "raw_payload, scraped_at, trace_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (source, source_id, url, "fake-hash", "{}", ts, "seed-trace"),
        )
        raw_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.execute(
            "INSERT INTO canonical_records (source, source_id, url, payload, "
            "valid_from, raw_id) VALUES (?, ?, ?, ?, ?, ?)",
            (source, source_id, url, "{}", ts, raw_id),
        )
        con.commit()
    finally:
        con.close()


def _setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "test.db"
    migrate(db)
    monkeypatch.setattr("src.run.load_sources", lambda: [_StubConfig()])
    monkeypatch.setattr("src.run._load_adapter", lambda _name: _StubAdapter())
    monkeypatch.setattr("src.run.is_allowed", lambda _url: (True, None))
    return db


def test_run_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr("src.run.fetch_via_firecrawl", lambda _url, _pt: _VALID_RAW)

    counts = run("docs_python_org", db_path=db)

    assert counts["canonical"] == 1
    assert counts["validation_failed"] == 0
    con = sqlite3.connect(db)
    try:
        (n,) = con.execute("SELECT COUNT(*) FROM canonical_records").fetchone()
        assert n == 1
        (n,) = con.execute("SELECT COUNT(*) FROM validation_failed").fetchone()
        assert n == 0
    finally:
        con.close()


def test_run_validation_error_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr("src.run.fetch_via_firecrawl", lambda _url, _pt: _INVALID_RAW)

    counts = run("docs_python_org", db_path=db)

    assert counts["validation_failed"] == 1
    assert counts["canonical"] == 0
    con = sqlite3.connect(db)
    try:
        (raw_n,) = con.execute("SELECT COUNT(*) FROM raw_content").fetchone()
        assert raw_n == 1
        (canon_n,) = con.execute("SELECT COUNT(*) FROM canonical_records").fetchone()
        assert canon_n == 0
        (vf_n,) = con.execute("SELECT COUNT(*) FROM validation_failed").fetchone()
        assert vf_n == 1
        raw_id = con.execute("SELECT id FROM raw_content").fetchone()[0]
        vf_raw_id = con.execute("SELECT raw_id FROM validation_failed").fetchone()[0]
        assert vf_raw_id == raw_id
    finally:
        con.close()


def test_run_circuit_breaker_stops(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "src.run._load_adapter",
        lambda _name: _StubAdapter(urls=[f"https://example.invalid/{i}" for i in range(5)]),
    )

    def _failing_fetch(_url: str, _pt: str) -> dict[str, Any]:
        raise RuntimeError("transport failed")

    monkeypatch.setattr("src.run.fetch_via_firecrawl", _failing_fetch)

    with pytest.raises(RuntimeError, match="circuit breaker"):
        run("docs_python_org", db_path=db)


def test_run_propagates_config_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """KeyError (e.g. missing env var) should NOT be swallowed as transport error."""
    db = _setup(tmp_path, monkeypatch)

    def _config_error_fetch(_url: str, _pt: str) -> dict[str, Any]:
        raise KeyError("FIRECRAWL_API_KEY")

    monkeypatch.setattr("src.run.fetch_via_firecrawl", _config_error_fetch)
    with pytest.raises(KeyError, match="FIRECRAWL_API_KEY"):
        run("docs_python_org", db_path=db)


def test_run_transport_error_is_logged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Transport errors must be logged with traceback, not silently swallowed."""
    db = _setup(tmp_path, monkeypatch)

    def _transport_error(_url: str, _pt: str) -> dict[str, Any]:
        raise ConnectionError("timeout after 30s")

    monkeypatch.setattr("src.run.fetch_via_firecrawl", _transport_error)

    with caplog.at_level(logging.ERROR, logger="src.run"):
        counts = run("docs_python_org", db_path=db)

    assert counts["errors"] == 1
    assert counts["canonical"] == 0
    assert "timeout after 30s" in caplog.text


def test_run_overrides_source_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Adapter-provided source/source_id/source_url override Firecrawl-extracted values."""
    db = _setup(tmp_path, monkeypatch)
    polluted_raw: dict[str, Any] = {
        "source": "WRONG_SOURCE_FROM_LLM_GUESS",
        "source_url": "https://wrong.invalid/llm-guessed-url",
        "source_id": "wrong_source_id",
        "title": "json -- JSON encoder and decoder",
        "section_path": [],
        "body_md": "A standard library module for encoding and decoding JSON data.",
        "code_block_count": 0,
        "last_updated": None,
    }
    monkeypatch.setattr("src.run.fetch_via_firecrawl", lambda _url, _pt: dict(polluted_raw))

    counts = run("docs_python_org", db_path=db)
    assert counts["canonical"] == 1

    con = sqlite3.connect(db)
    try:
        row = con.execute("SELECT source, source_id, url FROM canonical_records").fetchone()
        assert row[0] == "docs_python_org"
        assert row[1] == "json"
        assert row[2] == "https://docs.python.org/3/library/json.html"

        payload_row = con.execute("SELECT payload FROM canonical_records").fetchone()
        payload = json.loads(payload_row[0])
        assert payload["source"] == "docs_python_org"
        assert payload["source_id"] == "json"
        assert payload["source_url"] == "https://docs.python.org/3/library/json.html"

        raw_row = con.execute("SELECT raw_payload FROM raw_content").fetchone()
        raw_persisted = json.loads(raw_row[0])
        assert raw_persisted["source"] == "docs_python_org"
        assert raw_persisted["source_id"] == "json"
        assert raw_persisted["source_url"] == "https://docs.python.org/3/library/json.html"
    finally:
        con.close()


# ---------------------------------------------------------------------------
# skip-if-fresh
# ---------------------------------------------------------------------------


def test_run_skips_fresh_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _setup(tmp_path, monkeypatch)
    _seed_canonical(db, "docs_python_org", "json", _STUB_URL, age_days=1.0)
    fetch_called: list[str] = []
    monkeypatch.setattr(
        "src.run.fetch_via_firecrawl",
        lambda url, _pt: (fetch_called.append(url), _VALID_RAW)[1],
    )

    counts = run("docs_python_org", db_path=db, max_age_days=7)

    assert counts["skipped_fresh"] == 1
    assert counts["canonical"] == 0
    assert fetch_called == []


def test_run_processes_stale_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _setup(tmp_path, monkeypatch)
    _seed_canonical(db, "docs_python_org", "json", _STUB_URL, age_days=30.0)
    monkeypatch.setattr("src.run.fetch_via_firecrawl", lambda _u, _p: _VALID_RAW)

    counts = run("docs_python_org", db_path=db, max_age_days=7)

    assert counts["skipped_fresh"] == 0
    assert counts["canonical"] == 1


def test_run_processes_when_no_canonical(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr("src.run.fetch_via_firecrawl", lambda _u, _p: _VALID_RAW)

    counts = run("docs_python_org", db_path=db, max_age_days=7)

    assert counts["skipped_fresh"] == 0
    assert counts["canonical"] == 1


def test_run_force_flag_bypasses_skip_fresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _setup(tmp_path, monkeypatch)
    _seed_canonical(db, "docs_python_org", "json", _STUB_URL, age_days=1.0)
    monkeypatch.setattr("src.run.fetch_via_firecrawl", lambda _u, _p: _VALID_RAW)

    counts = run("docs_python_org", db_path=db, max_age_days=7, force=True)

    assert counts["skipped_fresh"] == 0
    assert counts["canonical"] == 1


def test_run_invariant_holds_across_buckets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """sum(counts.values()) == iterated_urls — sanity that classification is exhaustive."""
    db = _setup(tmp_path, monkeypatch)
    urls = [
        "https://docs.python.org/3/library/json.html",  # fresh → skipped
        "https://docs.python.org/3/library/os.html",  # stale → canonical
    ]
    monkeypatch.setattr("src.run._load_adapter", lambda _name: _StubAdapter(urls=urls))
    _seed_canonical(db, "docs_python_org", "json", urls[0], age_days=1.0)
    monkeypatch.setattr("src.run.fetch_via_firecrawl", lambda _u, _p: _VALID_RAW)

    counts = run("docs_python_org", db_path=db, max_age_days=7)

    assert sum(counts.values()) == 2
    assert counts["skipped_fresh"] == 1
    assert counts["canonical"] == 1

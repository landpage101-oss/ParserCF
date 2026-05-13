"""Smoke tests for src/run.py batch entry point."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from src.db.migrate import migrate
from src.run import run


class _StubConfig:
    adapter = "src/sources/docs_python_org.py"


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


_VALID_RAW: dict[str, Any] = {
    "source": "docs.python.org",
    "source_url": "https://docs.python.org/3/library/json.html",
    "source_id": "json",
    "title": "json — JSON encoder and decoder",
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
    "body_md": "404 not found — the page you requested does not exist",
    "code_block_count": 0,
    "last_updated": None,
}


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
        assert raw_n == 1  # raw persisted before validation (append-only invariant)
        (canon_n,) = con.execute("SELECT COUNT(*) FROM canonical_records").fetchone()
        assert canon_n == 0
        (vf_n,) = con.execute("SELECT COUNT(*) FROM validation_failed").fetchone()
        assert vf_n == 1
        raw_id = con.execute("SELECT id FROM raw_content").fetchone()[0]
        vf_raw_id = con.execute("SELECT raw_id FROM validation_failed").fetchone()[0]
        assert vf_raw_id == raw_id  # FK links failure to its raw record
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


def test_run_overrides_source_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Adapter-provided source/source_id/source_url override Firecrawl-extracted values.

    TODO #8: Firecrawl JSON-mode treats these fields as content; LLM fills them
    with metadata guesses. They must be overridden with adapter-provided truth.
    """
    db = _setup(tmp_path, monkeypatch)
    # raw with WRONG values for the three identifier fields (as if Firecrawl LLM guessed)
    polluted_raw: dict[str, Any] = {
        "source": "WRONG_SOURCE_FROM_LLM_GUESS",
        "source_url": "https://wrong.invalid/llm-guessed-url",
        "source_id": "wrong_source_id",
        "title": "json — JSON encoder and decoder",
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
        # Table columns: adapter-provided
        row = con.execute("SELECT source, source_id, url FROM canonical_records").fetchone()
        assert row[0] == "docs_python_org"
        assert row[1] == "json"  # _StubAdapter.parse_id returns URL leaf
        assert row[2] == "https://docs.python.org/3/library/json.html"

        # Payload fields: must also be adapter-provided after the fix
        payload_row = con.execute("SELECT payload FROM canonical_records").fetchone()
        payload = json.loads(payload_row[0])
        assert payload["source"] == "docs_python_org"
        assert payload["source_id"] == "json"
        assert payload["source_url"] == "https://docs.python.org/3/library/json.html"

        # raw_content persists the normalized (overridden) raw, not the polluted Firecrawl output
        raw_row = con.execute("SELECT raw_payload FROM raw_content").fetchone()
        raw_persisted = json.loads(raw_row[0])
        assert raw_persisted["source"] == "docs_python_org"
        assert raw_persisted["source_id"] == "json"
        assert raw_persisted["source_url"] == "https://docs.python.org/3/library/json.html"
    finally:
        con.close()

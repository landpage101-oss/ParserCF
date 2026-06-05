"""Dispatch tests: run.py routes to Firecrawl or HTTP based on adapter.kind."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pytest

from src.db.migrate import migrate
from src.run import run
from src.sources._http_base import KIND_HTTP


class _StubConfig:
    adapter = "src/sources/docs_python_org.py"


class _StubFirecrawlAdapter:
    """Adapter without 'kind' attribute — dispatches to Firecrawl by default."""

    page_type = "docs"
    domain = "example.invalid"
    name = "docs_python_org"

    def list_urls(self, since: str | None = None) -> list[str]:  # noqa: ARG002
        return ["https://example.test/x"]

    def parse_id(self, url: str) -> str:
        return url.rsplit("/", maxsplit=1)[-1]


class _StubHttpAdapter:
    """Adapter with kind=KIND_HTTP — dispatches to HTTP path."""

    kind = KIND_HTTP
    page_type = "docs"
    domain = "example.invalid"
    name = "docs_python_org"

    def list_urls(self, since: str | None = None) -> list[str]:  # noqa: ARG002
        return ["https://example.test/x"]

    def parse_id(self, url: str) -> str:
        return url.rsplit("/", maxsplit=1)[-1]

    def parse_response(self, response_json: dict[str, Any], url: str) -> dict[str, Any]:  # noqa: ARG002
        return {}


_VALID_DOCS_RAW: dict[str, Any] = {
    "source": "docs_python_org",
    "source_url": "https://example.test/x",
    "source_id": "x",
    "title": "Dispatch test",
    "section_path": [],
    "body_md": "Dispatch test content.",
    "code_block_count": 0,
    "last_updated": None,
}


def _setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, adapter: Any) -> Path:
    db = tmp_path / "test.db"
    migrate(db)
    monkeypatch.setattr("src.run.load_sources", lambda: [_StubConfig()])
    monkeypatch.setattr("src.run._load_adapter", lambda _name: adapter)
    monkeypatch.setattr("src.run.is_allowed", lambda _url: (True, None))
    return db


def test_run_dispatches_firecrawl_for_default_adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    firecrawl_calls: list[str] = []
    http_calls: list[str] = []

    monkeypatch.setattr(
        "src.run.fetch_via_firecrawl",
        lambda url, _pt: (firecrawl_calls.append(url), dict(_VALID_DOCS_RAW))[1],
    )
    monkeypatch.setattr(
        "src.run.fetch_via_http",
        lambda _a, url: (http_calls.append(url), {})[1],
    )
    db = _setup(tmp_path, monkeypatch, _StubFirecrawlAdapter())

    counts = run("docs_python_org", db_path=db)

    assert firecrawl_calls == ["https://example.test/x"]
    assert http_calls == []
    assert counts["canonical"] == 1


def test_run_dispatches_http_for_kind_http_adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    firecrawl_calls: list[str] = []
    http_calls: list[str] = []

    monkeypatch.setattr(
        "src.run.fetch_via_firecrawl",
        lambda url, _pt: (firecrawl_calls.append(url), {})[1],
    )
    monkeypatch.setattr(
        "src.run.fetch_via_http",
        lambda _a, url: (http_calls.append(url), dict(_VALID_DOCS_RAW))[1],
    )
    db = _setup(tmp_path, monkeypatch, _StubHttpAdapter())

    counts = run("docs_python_org", db_path=db)

    assert http_calls == ["https://example.test/x"]
    assert firecrawl_calls == []
    assert counts["canonical"] == 1

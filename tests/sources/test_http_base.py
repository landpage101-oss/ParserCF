"""Unit tests for src/sources/_http_base.py — fetch_via_http and Protocol contract."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.sources._http_base import KIND_HTTP, fetch_via_http

_ZW_SPACE = chr(0x200B)  # zero-width space; sanitize must strip this


class _FakeAdapter:
    """Minimal HttpSourceAdapter implementation for testing."""

    kind = KIND_HTTP
    domain = "example.test"
    name = "example_test"
    page_type = "docs"

    def list_urls(self, since: str | None = None) -> list[str]:  # noqa: ARG002
        return []

    def parse_id(self, url: str) -> str:
        return url.rsplit("/", maxsplit=1)[-1].split(".", maxsplit=1)[0]

    def parse_response(self, response_json: dict[str, Any], url: str) -> dict[str, Any]:
        return {
            "source": self.name,
            "source_id": self.parse_id(url),
            "source_url": url,
            "body_md": response_json.get("body", ""),
            "title": response_json.get("title", ""),
            "section_path": [],
            "code_block_count": 0,
            "last_updated": None,
        }


def _make_mock_response(body: bytes, content_type: str = "application/json") -> MagicMock:
    """Create a MagicMock that behaves as urllib's HTTP response context manager."""
    mock_resp = MagicMock()
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.headers.get.return_value = content_type
    mock_resp.read.return_value = body
    return mock_resp


def test_fetch_via_http_returns_payload() -> None:
    adapter = _FakeAdapter()
    url = "https://example.test/foo.json"
    body = json.dumps({"title": "Hello", "body": "World content"}).encode()
    mock_resp = _make_mock_response(body)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = fetch_via_http(adapter, url)
    assert result["source"] == "example_test"
    assert result["source_id"] == "foo"
    assert result["source_url"] == url
    assert result["body_md"] == "World content"


def test_fetch_via_http_sanitizes_body_fields() -> None:
    adapter = _FakeAdapter()
    url = "https://example.test/foo.json"
    body = json.dumps({"body": f"Hello{_ZW_SPACE}World"}).encode()
    mock_resp = _make_mock_response(body)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = fetch_via_http(adapter, url)
    assert _ZW_SPACE not in str(result["body_md"])


def test_fetch_via_http_raises_on_non_2xx() -> None:
    adapter = _FakeAdapter()
    url = "https://example.test/foo.json"
    exc = urllib.error.HTTPError(url, 404, "Not Found", {}, io.BytesIO(b""))
    with patch("urllib.request.urlopen", side_effect=exc), pytest.raises(urllib.error.HTTPError):
        fetch_via_http(adapter, url)


def test_fetch_via_http_raises_on_malformed_json() -> None:
    adapter = _FakeAdapter()
    url = "https://example.test/foo.json"
    mock_resp = _make_mock_response(b"not-valid-json")
    with (
        patch("urllib.request.urlopen", return_value=mock_resp),
        pytest.raises(json.JSONDecodeError),
    ):
        fetch_via_http(adapter, url)


def test_fetch_via_http_raises_on_empty_parsed_payload() -> None:
    class _EmptyAdapter(_FakeAdapter):
        def parse_response(
            self,
            _response_json: dict[str, Any],
            _url: str,
        ) -> dict[str, Any]:
            return {}

    adapter = _EmptyAdapter()
    url = "https://example.test/foo.json"
    body = json.dumps({"body": "data"}).encode()
    mock_resp = _make_mock_response(body)
    with (
        patch("urllib.request.urlopen", return_value=mock_resp),
        pytest.raises(ValueError, match="empty payload"),
    ):
        fetch_via_http(adapter, url)


def test_fetch_via_http_overrides_identifiers_defensively() -> None:
    class _BadIdAdapter(_FakeAdapter):
        def parse_response(
            self,
            _response_json: dict[str, Any],
            _url: str,
        ) -> dict[str, Any]:
            return {
                "source": "WRONG",
                "source_id": "WRONG",
                "source_url": "https://wrong.example/path",
                "body_md": "Some content here",
            }

    adapter = _BadIdAdapter()
    url = "https://example.test/bar.json"
    body = json.dumps({}).encode()
    mock_resp = _make_mock_response(body)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = fetch_via_http(adapter, url)
    assert result["source"] == "example_test"
    assert result["source_id"] == "bar"
    assert result["source_url"] == url

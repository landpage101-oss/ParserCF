"""Unit tests for src/sources/_http_base.py — fetch_via_http and Protocol contract."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.sources._http_base import KIND_HTTP, fetch_via_http

_ZW_SPACE = chr(0x200B)  # zero-width space; sanitize must strip this


@pytest.fixture(autouse=True)
def _reset_rate_limit_state() -> Iterator[None]:
    # Intentional private-symbol import: test fixture owns module-level state
    # reset for _http_base.py. This is the agreed test-only contract for
    # rate-limit isolation (see spec PR-A). Not for production-code use.
    from src.sources._http_base import _LAST_HTTP_CALL_TS  # noqa: PLC0415

    _LAST_HTTP_CALL_TS.clear()
    yield
    _LAST_HTTP_CALL_TS.clear()


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
        result = fetch_via_http(adapter, url, rate_limit_rps=1.0)
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
        result = fetch_via_http(adapter, url, rate_limit_rps=1.0)
    assert _ZW_SPACE not in str(result["body_md"])


def test_fetch_via_http_raises_on_non_2xx() -> None:
    adapter = _FakeAdapter()
    url = "https://example.test/foo.json"
    exc = urllib.error.HTTPError(url, 404, "Not Found", {}, io.BytesIO(b""))
    with patch("urllib.request.urlopen", side_effect=exc), pytest.raises(urllib.error.HTTPError):
        fetch_via_http(adapter, url, rate_limit_rps=1.0)


def test_fetch_via_http_raises_on_malformed_json() -> None:
    adapter = _FakeAdapter()
    url = "https://example.test/foo.json"
    mock_resp = _make_mock_response(b"not-valid-json")
    with (
        patch("urllib.request.urlopen", return_value=mock_resp),
        pytest.raises(json.JSONDecodeError),
    ):
        fetch_via_http(adapter, url, rate_limit_rps=1.0)


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
        fetch_via_http(adapter, url, rate_limit_rps=1.0)


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
        result = fetch_via_http(adapter, url, rate_limit_rps=1.0)
    assert result["source"] == "example_test"
    assert result["source_id"] == "bar"
    assert result["source_url"] == url


# --- Rate-limit behaviour tests ---


def test_fetch_via_http_sleeps_when_called_within_rate_limit_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _FakeAdapter()
    url = "https://example.test/foo.json"
    body = json.dumps({"title": "T", "body": "B"}).encode()
    mock_resp = _make_mock_response(body)

    # side_effect sequence: first call records 0.0, second call reads 0.3
    # (elapsed=0.3 < 1.0 → sleep), then records 1.0 after sleep.
    monotonic_calls = iter([0.0, 0.3, 1.0])
    monkeypatch.setattr("src.sources._http_base.time.monotonic", lambda: next(monotonic_calls))

    sleep_calls: list[float] = []
    monkeypatch.setattr("src.sources._http_base.time.sleep", sleep_calls.append)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        fetch_via_http(adapter, url, rate_limit_rps=1.0)
        fetch_via_http(adapter, url, rate_limit_rps=1.0)

    assert len(sleep_calls) == 1
    assert sleep_calls[0] == pytest.approx(0.7, abs=1e-9)


def test_fetch_via_http_does_not_sleep_on_first_call_for_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _FakeAdapter()
    url = "https://example.test/foo.json"
    body = json.dumps({"title": "T", "body": "B"}).encode()
    mock_resp = _make_mock_response(body)

    sleep_calls: list[float] = []
    monkeypatch.setattr("src.sources._http_base.time.sleep", sleep_calls.append)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        fetch_via_http(adapter, url, rate_limit_rps=1.0)

    assert sleep_calls == []


def test_fetch_via_http_does_not_sleep_when_interval_already_elapsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.sources._http_base import _LAST_HTTP_CALL_TS  # noqa: PLC0415

    adapter = _FakeAdapter()
    url = "https://example.test/foo.json"
    body = json.dumps({"title": "T", "body": "B"}).encode()
    mock_resp = _make_mock_response(body)

    # Simulate that the last call happened at t=0.0 and now it's t=5.0 (elapsed > 1/rps)
    _LAST_HTTP_CALL_TS["example_test"] = 0.0
    monkeypatch.setattr("src.sources._http_base.time.monotonic", lambda: 5.0)

    sleep_calls: list[float] = []
    monkeypatch.setattr("src.sources._http_base.time.sleep", sleep_calls.append)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        fetch_via_http(adapter, url, rate_limit_rps=1.0)

    assert sleep_calls == []


def test_fetch_via_http_rate_limit_state_isolated_per_source_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _AdapterB(_FakeAdapter):
        name = "adapter_b"

    adapter_a = _FakeAdapter()
    adapter_b = _AdapterB()
    url = "https://example.test/foo.json"
    body = json.dumps({"title": "T", "body": "B"}).encode()

    # Both adapters return the same timestamp (t=0.0) — each is first for its key
    monkeypatch.setattr("src.sources._http_base.time.monotonic", lambda: 0.0)

    sleep_calls: list[float] = []
    monkeypatch.setattr("src.sources._http_base.time.sleep", sleep_calls.append)

    mock_resp_a = _make_mock_response(body)
    mock_resp_b = _make_mock_response(body)
    with patch("urllib.request.urlopen", side_effect=[mock_resp_a, mock_resp_b]):
        fetch_via_http(adapter_a, url, rate_limit_rps=1.0)
        fetch_via_http(adapter_b, url, rate_limit_rps=1.0)

    assert sleep_calls == []

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

from src.safety.cost import CostGate
from src.sources._http_base import (
    KIND_HTTP,
    _http_get_json,
    fetch_via_http,
    paginate_limit_skip,
)

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


# --- _http_get_json tests ---


def test_http_get_json_returns_decoded_json() -> None:
    url = "https://example.test/data.json"
    body = json.dumps({"key": "value", "count": 42}).encode()
    mock_resp = _make_mock_response(body)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = _http_get_json(url, "example_test", rate_limit_rps=1.0)
    assert result == {"key": "value", "count": 42}
    assert isinstance(result, dict)


def test_http_get_json_raises_value_error_on_non_object_json() -> None:
    for non_obj_body in [b"[1, 2, 3]", b'"string"', b"42", b"null"]:
        mock_resp = _make_mock_response(non_obj_body)
        with (
            patch("urllib.request.urlopen", return_value=mock_resp),
            pytest.raises(ValueError, match="expected JSON object"),
        ):
            _http_get_json("https://example.test/x.json", "example_test", rate_limit_rps=1.0)


# --- paginate_limit_skip tests ---


def _make_page(items: list[dict[str, object]], total: int) -> dict[str, object]:
    return {"products": items, "total": total}


def _id_item(item: dict[str, object]) -> str:
    return f"https://example.test/products/{item['id']}"


def test_paginate_limit_skip_yields_all_items_across_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page_items_1 = [{"id": i} for i in range(1, 31)]
    page_items_2 = [{"id": i} for i in range(31, 61)]
    page_items_3 = [{"id": i} for i in range(61, 71)]
    total = 70

    pages: dict[str, dict[str, object]] = {
        "https://example.test/products?limit=30&skip=0": _make_page(page_items_1, total),
        "https://example.test/products?limit=30&skip=30": _make_page(page_items_2, total),
        "https://example.test/products?limit=30&skip=60": _make_page(page_items_3, total),
    }
    monkeypatch.setattr(
        "src.sources._http_base._http_get_json",
        lambda url, _src, _rps: pages[url],
    )

    urls = list(
        paginate_limit_skip(
            "https://example.test/products?limit={limit}&skip={skip}",
            _id_item,
            source_name="example_test",
            rate_limit_rps=1.0,
            limit=30,
        )
    )

    assert len(urls) == 70
    assert urls[0] == "https://example.test/products/1"
    assert urls[-1] == "https://example.test/products/70"


def test_paginate_limit_skip_stops_when_total_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page_items = [{"id": i} for i in range(1, 11)]
    call_count = 0

    def mock_get_json(_url: str, _src: str, _rps: float) -> dict[str, object]:
        nonlocal call_count
        call_count += 1
        return _make_page(page_items, 10)

    monkeypatch.setattr("src.sources._http_base._http_get_json", mock_get_json)

    urls = list(
        paginate_limit_skip(
            "https://example.test/products?limit={limit}&skip={skip}",
            _id_item,
            source_name="example_test",
            rate_limit_rps=1.0,
            limit=30,
        )
    )

    assert len(urls) == 10
    assert call_count == 1


def test_paginate_limit_skip_stops_on_empty_items_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.sources._http_base._http_get_json",
        lambda _url, _src, _rps: {"products": [], "total": 100},
    )

    urls = list(
        paginate_limit_skip(
            "https://example.test/products?limit={limit}&skip={skip}",
            _id_item,
            source_name="example_test",
            rate_limit_rps=1.0,
            limit=30,
        )
    )

    assert urls == []


def test_paginate_limit_skip_respects_max_pages_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.sources._http_base._http_get_json",
        lambda _url, _src, _rps: {"products": [{"id": i} for i in range(30)], "total": 10000},
    )

    urls = list(
        paginate_limit_skip(
            "https://example.test/products?limit={limit}&skip={skip}",
            _id_item,
            source_name="example_test",
            rate_limit_rps=1.0,
            limit=30,
            max_pages=2,
        )
    )

    assert len(urls) == 60  # 2 pages x 30 items


def test_paginate_limit_skip_calls_gate_before_and_after_each_listing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import MagicMock  # noqa: PLC0415

    monkeypatch.setattr(
        "src.sources._http_base._http_get_json",
        lambda _url, _src, _rps: _make_page([{"id": i} for i in range(1, 11)], 10),
    )

    gate = MagicMock(spec=CostGate)

    list(
        paginate_limit_skip(
            "https://example.test/products?limit={limit}&skip={skip}",
            _id_item,
            source_name="example_test",
            rate_limit_rps=1.0,
            limit=30,
            gate=gate,
        )
    )

    gate.before_http_call.assert_called_once()
    gate.after_http_success.assert_called_once()
    gate.after_error.assert_not_called()


def test_paginate_limit_skip_calls_gate_after_error_on_listing_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import io  # noqa: PLC0415
    import urllib.error as _ue  # noqa: PLC0415
    from unittest.mock import MagicMock  # noqa: PLC0415

    exc = _ue.HTTPError(
        "https://example.test/products?limit=30&skip=0",
        503,
        "Service Unavailable",
        {},  # type: ignore[arg-type]
        io.BytesIO(b""),
    )

    def raise_exc(_url: str, _src: str, _rps: float) -> dict[str, object]:
        raise exc

    monkeypatch.setattr("src.sources._http_base._http_get_json", raise_exc)

    gate = MagicMock(spec=CostGate)

    with pytest.raises(_ue.HTTPError):
        list(
            paginate_limit_skip(
                "https://example.test/products?limit={limit}&skip={skip}",
                _id_item,
                source_name="example_test",
                rate_limit_rps=1.0,
                limit=30,
                gate=gate,
            )
        )

    gate.before_http_call.assert_called_once()
    gate.after_error.assert_called_once()
    gate.after_http_success.assert_not_called()

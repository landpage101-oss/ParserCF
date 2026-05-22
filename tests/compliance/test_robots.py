"""Unit tests for robots.txt compliance (RFC 9309)."""

import logging
import urllib.error
from unittest.mock import patch

import pytest

from src.compliance import robots
from src.compliance.robots import is_allowed


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    """Reset is_allowed cache between tests."""
    robots._cache.clear()


def _http_error(code: int, reason: str = "") -> urllib.error.HTTPError:
    """Build an HTTPError with given status code for mocking _fetch_robots."""
    return urllib.error.HTTPError(
        url="https://example.com/robots.txt",
        code=code,
        msg=reason,
        hdrs={},  # type: ignore[arg-type]
        fp=None,
    )


def test_allowed_returns_true_when_rp_allows() -> None:
    """200 OK with Allow: / → (True, None)."""
    body = "User-agent: *\nAllow: /\n"
    with patch.object(robots, "_fetch_robots", return_value=body):
        allowed, delay = is_allowed("https://example.com/page")
    assert allowed is True
    assert delay is None


def test_disallowed_returns_false() -> None:
    """200 OK with Disallow: / → (False, ...)."""
    body = "User-agent: *\nDisallow: /\n"
    with patch.object(robots, "_fetch_robots", return_value=body):
        allowed, _ = is_allowed("https://example.com/page")
    assert allowed is False


def test_crawl_delay_fallback_to_wildcard() -> None:
    """Crawl-delay under wildcard agent is returned when no agent-specific delay."""
    body = "User-agent: *\nCrawl-delay: 2\nAllow: /\n"
    with patch.object(robots, "_fetch_robots", return_value=body):
        allowed, delay = is_allowed("https://example.com/page")
    assert allowed is True
    assert delay == 2.0


def test_403_returns_allow_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    """RFC 9309 §2.3.1.4: 403 on robots.txt → allow-all + WARNING. anthropic.com regression."""
    with (
        patch.object(robots, "_fetch_robots", side_effect=_http_error(403, "Forbidden")),
        caplog.at_level(logging.WARNING, logger="src.compliance.robots"),
    ):
        allowed, delay = is_allowed("https://www.anthropic.com/news/")
    assert allowed is True
    assert delay is None
    assert any("403" in r.message and "allow-all" in r.message for r in caplog.records)


def test_404_returns_allow() -> None:
    """404 on robots.txt → allow-all per RFC 9309."""
    with patch.object(robots, "_fetch_robots", side_effect=_http_error(404, "Not Found")):
        allowed, _ = is_allowed("https://example.com/page")
    assert allowed is True


def test_429_returns_deny() -> None:
    """429 Too Many Requests → deny."""
    with patch.object(robots, "_fetch_robots", side_effect=_http_error(429, "Too Many Requests")):
        allowed, _ = is_allowed("https://example.com/page")
    assert allowed is False


def test_451_returns_deny() -> None:
    """451 Unavailable For Legal Reasons → deny."""
    with patch.object(robots, "_fetch_robots", side_effect=_http_error(451, "Legal")):
        allowed, _ = is_allowed("https://example.com/page")
    assert allowed is False


def test_500_returns_deny() -> None:
    """5xx → fail-closed (RFC 9309 §2.3.1.5)."""
    with patch.object(robots, "_fetch_robots", side_effect=_http_error(500, "Server Error")):
        allowed, _ = is_allowed("https://example.com/page")
    assert allowed is False


def test_network_error_returns_deny() -> None:
    """Network unreachable → fail-closed."""
    with patch.object(robots, "_fetch_robots", side_effect=urllib.error.URLError("refused")):
        allowed, _ = is_allowed("https://example.com/page")
    assert allowed is False


def test_cache_hit_skips_second_read() -> None:
    """Two calls to same host → _fetch_robots called once."""
    body = "User-agent: *\nAllow: /\n"
    with patch.object(robots, "_fetch_robots", return_value=body) as mock_fetch:
        is_allowed("https://example.com/page1")
        is_allowed("https://example.com/page2")
    assert mock_fetch.call_count == 1


def test_cache_expires_and_re_fetches() -> None:
    """After TTL expiry, _fetch_robots is called again."""
    body = "User-agent: *\nAllow: /\n"
    with patch.object(robots, "_fetch_robots", return_value=body) as mock_fetch:
        is_allowed("https://example.com/page")
        key = next(iter(robots._cache))
        cached_at, *rest = robots._cache[key]
        robots._cache[key] = (cached_at - robots._CACHE_TTL - 1, *rest)
        is_allowed("https://example.com/page")
    assert mock_fetch.call_count == 2

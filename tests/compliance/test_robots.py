from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from src.compliance import robots as robots_mod
from src.compliance.robots import is_allowed


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    robots_mod._cache.clear()  # noqa: SLF001


def _make_rp(can_fetch: bool = True, delay: float | None = None) -> MagicMock:
    rp = MagicMock()
    rp.can_fetch.return_value = can_fetch
    rp.crawl_delay.return_value = delay
    return rp


def test_allowed_returns_true_when_rp_allows() -> None:
    rp = _make_rp(can_fetch=True, delay=1.0)
    with patch("src.compliance.robots.RobotFileParser", return_value=rp):
        allowed, delay = is_allowed("https://example.com/page")
    assert allowed is True
    assert delay == 1.0


def test_disallowed_returns_false() -> None:
    rp = _make_rp(can_fetch=False, delay=None)
    with patch("src.compliance.robots.RobotFileParser", return_value=rp):
        allowed, _delay = is_allowed("https://example.com/private")
    assert allowed is False


def test_fail_closed_on_read_exception() -> None:
    rp = MagicMock()
    rp.read.side_effect = OSError("timeout")
    with patch("src.compliance.robots.RobotFileParser", return_value=rp):
        allowed, delay = is_allowed("https://unreachable.example.com/page")
    assert allowed is False
    assert delay is None


def test_cache_hit_skips_second_read() -> None:
    rp = _make_rp(can_fetch=True, delay=0.5)
    with patch("src.compliance.robots.RobotFileParser", return_value=rp):
        is_allowed("https://cached.example.com/a")
        is_allowed("https://cached.example.com/b")
    # RobotFileParser was constructed once; read() called once
    assert rp.read.call_count == 1


def test_cache_expires_and_re_fetches() -> None:
    rp = _make_rp(can_fetch=True)
    with patch("src.compliance.robots.RobotFileParser", return_value=rp):
        is_allowed("https://expire.example.com/page")
        # Manually expire the cache entry
        host = "https://expire.example.com"
        robots_mod._cache[host] = (rp, time.time() - robots_mod._CACHE_TTL - 1)  # noqa: SLF001
        is_allowed("https://expire.example.com/page")
    assert rp.read.call_count == 2


def test_crawl_delay_fallback_to_wildcard() -> None:
    rp = MagicMock()
    rp.can_fetch.return_value = True
    # agent-specific delay returns None, wildcard returns 2.0
    rp.crawl_delay.side_effect = lambda agent: None if agent != "*" else 2.0
    with patch("src.compliance.robots.RobotFileParser", return_value=rp):
        _, delay = is_allowed("https://wildcard.example.com/page")
    assert delay == 2.0

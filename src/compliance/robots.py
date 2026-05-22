"""Compliance: robots.txt checks. RFC 9309 reference implementation."""

from __future__ import annotations

import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from http import HTTPStatus

logger = logging.getLogger(__name__)

USER_AGENT = "agent-parser/1.0 (+contact@example.com)"
_CACHE_TTL = 3600

# Cache shape: host -> (fetched_at, allowed, crawl_delay_or_None). Resolved at fetch time.
_cache: dict[str, tuple[float, bool, float | None]] = {}


def _fetch_robots(robots_url: str) -> str:
    """Fetch robots.txt content. Raises urllib.error.HTTPError or URLError on failure."""
    req = urllib.request.Request(robots_url, headers={"User-Agent": USER_AGENT})  # noqa: S310
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
        content: str = resp.read().decode("utf-8", errors="replace")
        return content


def is_allowed(url: str) -> tuple[bool, float | None]:
    """Check robots.txt per RFC 9309. Returns (allowed, crawl_delay_seconds_or_None).

    Status-code handling:
    - 200: parse robots.txt, use rp.can_fetch().
    - 3xx: urllib follows by default; content of redirect target is what we parse.
    - 401, 403, 404, other 4xx (NOT 429/451): per RFC 9309 §2.3.1.4, treat as
      allow-all and log a WARNING for audit trail. This is the Googlebot
      precedent and the RFC's permissive interpretation.
    - 429 (Too Many Requests), 451 (Unavailable For Legal Reasons): deny.
    - 5xx: per RFC 9309 §2.3.1.5, treat as temporary unavailability — fail-closed.
    - Network error: fail-closed (more conservative than RFC, deliberate project choice).
    """
    parsed = urllib.parse.urlparse(url)
    host = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = f"{host}/robots.txt"

    # Cache lookup
    now = time.time()
    if host in _cache:
        cached_at, allowed, delay = _cache[host]
        if now - cached_at < _CACHE_TTL:
            return allowed, delay

    try:
        content = _fetch_robots(robots_url)
    except urllib.error.HTTPError as e:
        if e.code in (HTTPStatus.TOO_MANY_REQUESTS, HTTPStatus.UNAVAILABLE_FOR_LEGAL_REASONS):
            logger.info(
                "robots.txt at %s returned %d %s; denying per RFC 9309",
                robots_url,
                e.code,
                e.reason,
            )
            _cache[host] = (now, False, None)
            return False, None
        if HTTPStatus.BAD_REQUEST <= e.code < HTTPStatus.INTERNAL_SERVER_ERROR:
            logger.warning(
                "robots.txt at %s returned %d %s; treating as allow-all per RFC 9309 §2.3.1.4",
                robots_url,
                e.code,
                e.reason,
            )
            _cache[host] = (now, True, None)
            return True, None
        # 5xx
        logger.info(
            "robots.txt at %s returned %d %s; denying per RFC 9309 §2.3.1.5",
            robots_url,
            e.code,
            e.reason,
        )
        # Don't cache 5xx — transient, retry next call.
        return False, None
    except (urllib.error.URLError, OSError):
        # Network error — fail-closed, more conservative than RFC.
        return False, None

    # 200 OK path
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(content.splitlines())
    allowed = rp.can_fetch(USER_AGENT, url)
    delay_raw = rp.crawl_delay(USER_AGENT) or rp.crawl_delay("*")
    delay = float(delay_raw) if delay_raw is not None else None
    _cache[host] = (now, allowed, delay)
    return allowed, delay

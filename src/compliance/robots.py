from __future__ import annotations

import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

USER_AGENT = "agent-parser/1.0 (+contact@example.com)"
_CACHE_TTL = 3600
_cache: dict[str, tuple[RobotFileParser, float]] = {}


def is_allowed(url: str) -> tuple[bool, float | None]:
    """Return (allowed, crawl_delay_seconds). Fail-closed on any robots.txt error."""
    parsed = urlparse(url)
    host = f"{parsed.scheme}://{parsed.netloc}"
    now = time.time()
    cached = _cache.get(host)
    if cached and now - cached[1] < _CACHE_TTL:
        rp = cached[0]
    else:
        rp = RobotFileParser()
        rp.set_url(f"{host}/robots.txt")
        try:
            rp.read()
        except Exception:  # noqa: BLE001
            return False, None  # fail-closed: нет доступа к robots.txt → запрет
        _cache[host] = (rp, now)
    allowed = rp.can_fetch(USER_AGENT, url)
    delay_raw = rp.crawl_delay(USER_AGENT) or rp.crawl_delay("*")
    delay: float | None = float(delay_raw) if delay_raw is not None else None
    return allowed, delay

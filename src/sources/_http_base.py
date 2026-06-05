"""HTTP adapter protocol and fetch utility for sources with public JSON APIs."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from collections.abc import Iterable
from typing import ClassVar, Final, Protocol

from src.compliance.robots import USER_AGENT
from src.safety.sanitize import sanitize

logger = logging.getLogger(__name__)

KIND_FIRECRAWL: Final[str] = "firecrawl"
KIND_HTTP: Final[str] = "http"

# Mirrors extract.py::_SANITIZE_FIELDS. Duplication is intentional:
# extract.py is Firecrawl-specific; _http_base.py is self-contained.
_SANITIZE_FIELDS: Final[tuple[str, ...]] = ("body_md", "definition", "description")
_HTTP_TIMEOUT_SECONDS: Final[float] = 30.0


class HttpSourceAdapter(Protocol):
    """Adapter for sources with public JSON API. Not Firecrawl.

    One URL → one HTTP GET → one parsed payload → one canonical record.
    Pagination / handle-discovery happens inside list_urls, not in fetch.
    """

    kind: ClassVar[str]  # MUST be KIND_HTTP — used for run.py dispatch
    domain: str
    name: str
    page_type: str  # one of 'article'|'docs'|'product'|'reference'

    def list_urls(self, since: str | None = None) -> Iterable[str]: ...

    def parse_id(self, url: str) -> str: ...

    def parse_response(
        self,
        response_json: dict[str, object],
        url: str,
    ) -> dict[str, object]:
        """Map JSON API response to dict matching PAGE_TYPE_TO_SCHEMA[page_type].

        MUST populate at minimum: source, source_id, source_url (caller will
        override these defensively but adapter should still produce them).
        Pure function — no I/O, no sanitize. Sanitize happens in fetch_via_http.
        """
        ...


def fetch_via_http(
    adapter: HttpSourceAdapter,
    url: str,
) -> dict[str, object]:
    """Fetch JSON from a public API, parse via adapter, sanitize unsafe fields.

    Returns dict suitable for record_attempt + validate_extracted.

    Raises:
      urllib.error.HTTPError on non-2xx HTTP status.
      ValueError on malformed JSON or empty/incomplete parsed payload.
      urllib.error.URLError on transport failure.

    NOT responsible for: robots.txt (caller checks via is_allowed), CostGate
    bookkeeping (caller wraps in before_http_call / after_*), DB writes.
    """
    req = urllib.request.Request(  # noqa: S310
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_SECONDS) as resp:  # noqa: S310
        content_type: str = resp.headers.get("Content-Type", "")
        if not content_type.startswith("application/json"):
            logger.warning(
                "unexpected Content-Type %r from %s; attempting JSON parse anyway",
                content_type,
                url,
            )
        body: bytes = resp.read()

    response_json: dict[str, object] = json.loads(body.decode("utf-8"))
    payload = adapter.parse_response(response_json, url)

    if not payload or not {"source", "source_id", "source_url"}.issubset(payload):
        raise ValueError(f"empty payload from {url}")

    for field in _SANITIZE_FIELDS:
        val = payload.get(field)
        if isinstance(val, str):
            payload[field], _ = sanitize(val)

    # Defensive overrides — mirrors run.py post-fetch pattern (idempotent for HTTP).
    payload["source"] = adapter.name
    payload["source_id"] = adapter.parse_id(url)
    payload["source_url"] = url

    return payload

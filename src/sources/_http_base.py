"""HTTP adapter protocol and fetch utility for sources with public JSON APIs."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Iterator
from typing import TYPE_CHECKING, ClassVar, Final, Protocol, cast

from src.compliance.robots import USER_AGENT
from src.safety.sanitize import sanitize

if TYPE_CHECKING:
    from src.safety.cost import CostGate

logger = logging.getLogger(__name__)

KIND_FIRECRAWL: Final[str] = "firecrawl"
KIND_HTTP: Final[str] = "http"

# Mirrors extract.py::_SANITIZE_FIELDS. Duplication is intentional:
# extract.py is Firecrawl-specific; _http_base.py is self-contained.
_SANITIZE_FIELDS: Final[tuple[str, ...]] = ("body_md", "definition", "description")
_HTTP_TIMEOUT_SECONDS: Final[float] = 30.0
_DEFAULT_PAGE_LIMIT: Final[int] = 30
_DEFAULT_MAX_PAGES: Final[int] = 100

# Per-source last-call timestamp (monotonic seconds). Module-level state;
# acceptable for batch runner (single process per run). Tests must reset via
# autouse fixture — see tests/sources/test_http_base.py.
_LAST_HTTP_CALL_TS: dict[str, float] = {}


def _apply_rate_limit(source_name: str, rate_limit_rps: float) -> None:
    """Sleep if necessary to maintain rate_limit_rps for source_name.

    Spacing is measured from start-of-call to start-of-call (timestamp is
    recorded after the optional sleep, before the HTTP fetch). This makes the
    effective RPS match the configured value regardless of per-fetch latency.

    Timestamp is recorded BEFORE the HTTP request, so transport failures
    (5xx, timeouts, URLError) still update the timestamp. This is intentional:
    on server-side failure we want to keep spacing the retries, not burst the
    server during a degraded state. The cost — one extra spacing interval per
    failed attempt — is the right trade-off.

    First call for a source records the timestamp and returns immediately.
    """
    min_interval = 1.0 / rate_limit_rps
    last = _LAST_HTTP_CALL_TS.get(source_name)
    if last is not None:
        elapsed = time.monotonic() - last
        if elapsed < min_interval:
            sleep_for = min_interval - elapsed
            logger.debug(
                "rate-limit sleep %.3fs for source %s (rate=%.2f rps)",
                sleep_for,
                source_name,
                rate_limit_rps,
            )
            time.sleep(sleep_for)
    # Recorded BEFORE fetch — see docstring on intentional transport-fail behavior.
    _LAST_HTTP_CALL_TS[source_name] = time.monotonic()


class HttpSourceAdapter(Protocol):
    """Adapter for sources with public JSON API. Not Firecrawl.

    One URL → one HTTP GET → one parsed payload → one canonical record.
    Pagination / handle-discovery happens inside list_urls, not in fetch.
    """

    kind: ClassVar[str]  # MUST be KIND_HTTP — used for run.py dispatch
    domain: str
    name: str
    page_type: str  # one of 'article'|'docs'|'product'|'reference'

    def list_urls(
        self,
        since: str | None = None,
        *,
        gate: CostGate | None = None,
        rate_limit_rps: float | None = None,
    ) -> Iterable[str]: ...

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


def _http_get_json(
    url: str,
    source_name: str,
    rate_limit_rps: float,
) -> dict[str, object]:
    """Rate-limited HTTP GET returning decoded JSON. Pure transport — no adapter, no sanitize.

    Used by both fetch_via_http (single-record fetch) and paginate_limit_skip
    (listing pages). Applies _apply_rate_limit before urlopen.

    Raises:
      urllib.error.HTTPError on non-2xx HTTP status.
      json.JSONDecodeError on malformed JSON body.
      urllib.error.URLError on transport failure.
      ValueError if top-level JSON value is not an object (array, scalar, null).
    """
    _apply_rate_limit(source_name, rate_limit_rps)

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

    result = json.loads(body.decode("utf-8"))
    if not isinstance(result, dict):
        # Top-level JSON arrays / scalars are not what any of our adapters
        # consume — fail-loud rather than mask with cast / ignore. Some public
        # APIs return arrays on error paths; this catches that case explicitly.
        raise ValueError(  # noqa: TRY004
            f"expected JSON object from {url}, got {type(result).__name__}"
        )
    return cast("dict[str, object]", result)


def fetch_via_http(
    adapter: HttpSourceAdapter,
    url: str,
    rate_limit_rps: float,
) -> dict[str, object]:
    """Fetch JSON from a public API, parse via adapter, sanitize unsafe fields.

    Composes _http_get_json (rate-limited transport) + adapter.parse_response
    (shape adaptation) + sanitize + defensive identifier overrides.

    Returns dict suitable for record_attempt + validate_extracted.

    Raises:
      urllib.error.HTTPError on non-2xx HTTP status.
      ValueError on malformed JSON or empty/incomplete parsed payload.
      urllib.error.URLError on transport failure.

    NOT responsible for: robots.txt, CostGate bookkeeping, DB writes.
    """
    response_json = _http_get_json(url, adapter.name, rate_limit_rps)
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


def _should_stop_pagination(
    n_items: int,
    limit: int,
    total: int | None,
    seen: int,
) -> bool:
    """Return True when any pagination termination signal fires (greedy check)."""
    if n_items == 0:
        return True
    if n_items < limit:
        return True
    return total is not None and seen >= total


def paginate_limit_skip(  # noqa: C901
    listing_url_template: str,
    item_to_detail_url: Callable[[dict[str, object]], str],
    *,
    source_name: str,
    rate_limit_rps: float,
    items_key: str = "products",
    total_key: str = "total",
    limit: int = _DEFAULT_PAGE_LIMIT,
    gate: CostGate | None = None,
    max_pages: int = _DEFAULT_MAX_PAGES,
) -> Iterator[str]:
    """Paginate a JSON API with limit+skip semantics; yield detail URLs.

    Listing-page requests go through _http_get_json (same rate-limit budget,
    HTTP-bucket via gate.before_http_call() / after_http_success()) so they
    count identically to single-record fetches.

    Stops at the FIRST of:
      - seen >= total (normal termination from API metadata)
      - items in page == 0 (empty page)
      - items in page < limit (short page = last page)
      - pages_seen >= max_pages (safety cap; logs warning if not exhausted)

    Generator is lazy — listing pages are fetched only when the consumer asks
    for the next URL. If run.py breaks the outer loop early (max_iterations,
    circuit breaker, KeyboardInterrupt), remaining pages are never fetched.

    Gate accounting on failure: if _http_get_json raises, gate.after_error() is
    called before the exception propagates — symmetric with _fetch_for_adapter
    in run.py. This feeds the circuit breaker so cascading listing failures stop
    the batch correctly.

    Args:
      listing_url_template: format-string with {limit} and {skip} placeholders.
      item_to_detail_url: callback that builds a detail URL from a listing-item dict.
      source_name: passed to _apply_rate_limit; must match adapter.name.
      rate_limit_rps: spacing between listing-page fetches.
      items_key: JSON key containing the list of items (default "products").
      total_key: JSON key containing total item count (default "total").
      limit: page size (default 30).
      gate: optional CostGate; listing calls count against HTTP-bucket.
      max_pages: safety cap on listing-page requests (default 100). Override for
        catalogs >3000 items (with default limit=30).

    Yields:
      Detail URLs for downstream fetch_via_http calls.

    Raises:
      RuntimeError if gate.before_http_call() trips a cap or breaker.
      urllib.error.HTTPError / URLError / json.JSONDecodeError from _http_get_json.
      ValueError from _http_get_json (non-object JSON) or item_to_detail_url.
    """
    skip = 0
    seen = 0
    pages_seen = 0
    total: int | None = None

    while pages_seen < max_pages:
        url = listing_url_template.format(limit=limit, skip=skip)

        if gate is not None:
            gate.before_http_call()  # may raise RuntimeError on cap / breaker
        try:
            page = _http_get_json(url, source_name, rate_limit_rps)
        except Exception:
            # Symmetric with _fetch_for_adapter: feed the circuit breaker so
            # cascading listing failures stop the batch correctly.
            if gate is not None:
                gate.after_error()
            raise
        if gate is not None:
            gate.after_http_success()

        pages_seen += 1

        items_raw = page.get(items_key, [])
        if not isinstance(items_raw, list):
            logger.warning(
                "paginate_limit_skip: %s returned non-list for key %r; stopping",
                url,
                items_key,
            )
            return
        items: list[dict[str, object]] = [
            cast("dict[str, object]", it) for it in items_raw if isinstance(it, dict)
        ]
        dropped = len(items_raw) - len(items)
        if dropped:
            logger.warning(
                "paginate_limit_skip: %s dropped %d non-dict items from key %r",
                url,
                dropped,
                items_key,
            )

        if total is None:
            total_raw = page.get(total_key)
            if isinstance(total_raw, int):
                total = total_raw

        for item in items:
            yield item_to_detail_url(item)
            seen += 1

        if _should_stop_pagination(len(items), limit, total, seen):
            return

        skip += limit

    # max_pages cap hit without exhaustion — log for debug
    logger.warning(
        "paginate_limit_skip: hit max_pages cap %d for %s "
        "(seen=%d, total=%s); pagination truncated",
        max_pages,
        listing_url_template,
        seen,
        total,
    )

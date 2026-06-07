"""Adapter for dummyjson.com — public testing sandbox REST API.

robots.txt: wildcard Allow / for our User-Agent (not among named-disallow
AI bots); only Disallow /auth/.
Content-Signal: search=yes, ai-train=no — analytical catalog use respects both.
Legal basis: free public sandbox API, fake/placeholder data, open-source
community project (github.com/Ovi/DummyJSON).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import ClassVar

from src.sources._http_base import KIND_HTTP

_BASE = "https://dummyjson.com/products/"

_SEEDS: tuple[str, ...] = tuple(f"{_BASE}{i}" for i in range(1, 11))

# dummyjson does not return currency in responses. The sandbox uses USD by
# convention (prices in US dollar amounts, no currency symbol). Hardcoded
# default — if dummyjson ever starts returning a currency field, prefer it.
_DEFAULT_CURRENCY = "USD"


class DummyjsonComAdapter:
    kind: ClassVar[str] = KIND_HTTP
    domain = "dummyjson.com"
    name = "dummyjson_com"
    page_type = "product"

    def list_urls(self, since: str | None = None) -> Iterable[str]:  # noqa: ARG002
        return list(_SEEDS)

    def parse_id(self, url: str) -> str:
        # /products/5 -> "5"; trailing-slash and query-string tolerant
        return url.removeprefix(_BASE).split("/", maxsplit=1)[0].split("?", maxsplit=1)[0]

    def parse_response(
        self,
        response_json: dict[str, object],
        url: str,
    ) -> dict[str, object]:
        # Defensive: dummyjson always returns full object, but adapter does not
        # rely on field presence — schema validator + run.py defensive overrides
        # close the gaps.
        price_raw = response_json.get("price")
        # Keep JSON-primitive: record_attempt audits raw_payload via json.dumps before
        # Pydantic validation. Decimal would break that. Product schema validator
        # converts float→Decimal cleanly (Pydantic v2 uses Decimal(str(value)) under
        # the hood, preserving precision).
        price: float | None = float(price_raw) if isinstance(price_raw, (int, float)) else None

        stock_raw = response_json.get("stock")
        in_stock = bool(isinstance(stock_raw, int) and stock_raw > 0)

        return {
            "source": self.name,
            "source_url": url,
            "source_id": self.parse_id(url),
            "name": response_json.get("title", ""),
            "sku": response_json.get("sku"),
            "price": price,
            "currency": _DEFAULT_CURRENCY,
            "in_stock": in_stock,
            "description": response_json.get("description"),
        }

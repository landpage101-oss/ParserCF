"""Adapter for dummyjson.com — public testing sandbox REST API.

robots.txt: wildcard Allow / for our User-Agent (not among named-disallow
AI bots); only Disallow /auth/.
Content-Signal: search=yes, ai-train=no — analytical catalog use respects both.
Legal basis: free public sandbox API, fake/placeholder data, open-source
community project (github.com/Ovi/DummyJSON).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, ClassVar

from src.sources._http_base import KIND_HTTP, paginate_limit_skip

if TYPE_CHECKING:
    from src.safety.cost import CostGate

_BASE = "https://dummyjson.com/products/"
_LISTING_URL_TEMPLATE = "https://dummyjson.com/products?limit={limit}&skip={skip}"
_PAGE_LIMIT = 30  # dummyjson default; max 100 but 30 is a balanced page size

# dummyjson does not return currency in responses. The sandbox uses USD by
# convention (prices in US dollar amounts, no currency symbol). Hardcoded
# default — if dummyjson ever starts returning a currency field, prefer it.
_DEFAULT_CURRENCY = "USD"


def _item_to_detail_url(item: dict[str, object]) -> str:
    item_id = item.get("id")
    if not isinstance(item_id, int):
        raise ValueError(f"dummyjson item missing integer 'id': {item!r}")  # noqa: TRY004
    return f"{_BASE}{item_id}"


class DummyjsonComAdapter:
    kind: ClassVar[str] = KIND_HTTP
    domain = "dummyjson.com"
    name = "dummyjson_com"
    page_type = "product"

    def list_urls(
        self,
        since: str | None = None,  # noqa: ARG002
        *,
        gate: CostGate | None = None,
        rate_limit_rps: float | None = None,
    ) -> Iterable[str]:
        if rate_limit_rps is None:
            raise ValueError(
                "dummyjson_com.list_urls requires rate_limit_rps; "
                "production callers must pass config.rate_limit_rps from sources.yaml"
            )
        yield from paginate_limit_skip(
            listing_url_template=_LISTING_URL_TEMPLATE,
            item_to_detail_url=_item_to_detail_url,
            source_name=self.name,
            rate_limit_rps=rate_limit_rps,
            items_key="products",
            total_key="total",
            limit=_PAGE_LIMIT,
            gate=gate,
        )

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

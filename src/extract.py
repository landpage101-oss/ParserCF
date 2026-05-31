import functools
import hashlib
import os
import re
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import Literal
from urllib.parse import urlparse

import markdownify as _md_lib
from bs4 import BeautifulSoup, Tag
from firecrawl import Firecrawl
from pydantic import BaseModel

from src.safety.sanitize import sanitize
from src.schemas import PAGE_TYPE_TO_SCHEMA

PageType = Literal["article", "docs", "product", "reference"]

_SANITIZE_FIELDS = ("body_md", "definition", "description")
_MD_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "code", "pre", "ul", "ol", "li", "a"]
_CURRENCY_MAP: dict[str, str] = {"€": "EUR", "$": "USD", "£": "GBP", "₽": "RUB"}
_ISO_CODE_LEN = 3

_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_LANG_RE = re.compile(r'<html[^>]+lang=["\']([a-z]{2})["\']', re.IGNORECASE)
_AUTHOR_RE = re.compile(r"\bBy\s+([A-Z][a-zA-Z .\'-]{2,60})")
_CODE_FENCE_RE = re.compile(r"^```", re.MULTILINE)
_PRICE_RE = re.compile(r"([€$£₽])\s*([\d,.\s]+)|([\d,.\s]+)\s*([€$£₽]|USD|EUR|RUB|GBP)")
_IN_STOCK_RE = re.compile(r'data-in-stock=["\']?(\w+)["\']?', re.IGNORECASE)
_TERM_PREFIX_RE = re.compile(r"^(?:Glossary|Reference|Term|Definition|FAQ):\s+", re.IGNORECASE)

# ── production path ───────────────────────────────────────────────────────────


@functools.lru_cache(maxsize=1)
def _client() -> Firecrawl:
    return Firecrawl(api_key=os.environ["FIRECRAWL_API_KEY"])


def fetch_via_firecrawl(url: str, page_type: str) -> dict[str, object]:
    """Fetch raw JSON from Firecrawl. NO validation — caller persists raw first.

    Returns the raw dict as received from Firecrawl (after sanitize).
    Caller MUST call record_attempt(raw) before validate_extracted(raw, ...).
    """
    schema_cls = PAGE_TYPE_TO_SCHEMA[page_type]
    result = _client().scrape(
        url,
        formats=[{"type": "json", "schema": schema_cls.model_json_schema()}],
        only_main_content=True,
        wait_for=1500,  # wait for JS hydration; prevents truncated body/title (#A)
        timeout=30000,  # 30 s per attempt; fail fast so our backoff handles retries (#A)
    )
    raw_json: dict[str, object] = getattr(result, "json", None) or {}
    if not raw_json:
        raise ValueError(f"empty extraction for {url}")
    for field in _SANITIZE_FIELDS:
        val = raw_json.get(field)
        if isinstance(val, str):
            raw_json[field], _ = sanitize(val)
    return raw_json


def validate_extracted(raw: dict[str, object], page_type: str) -> BaseModel:
    """Validate raw payload against the schema for page_type.

    Raises pydantic.ValidationError on failure. Caller is expected to have
    already persisted raw via record_attempt — this function does not touch the DB.
    """
    schema_cls = PAGE_TYPE_TO_SCHEMA[page_type]
    return schema_cls.model_validate(raw)


def extract_via_firecrawl(url: str, page_type: str) -> tuple[dict[str, object], BaseModel]:
    """Convenience wrapper: fetch + validate in one call.

    Kept for backward compatibility. New code (run.py) should call
    fetch_via_firecrawl and validate_extracted separately to preserve raw
    on ValidationError (append-only invariant, ERRATA E-4).
    """
    raw = fetch_via_firecrawl(url, page_type)
    return raw, validate_extracted(raw, page_type)


# ── local test-double path ────────────────────────────────────────────────────


def _html_to_md(html: str) -> str:
    return str(_md_lib.markdownify(html, convert=_MD_TAGS, heading_style="ATX"))


def _extract_section_path(html: str) -> list[str]:
    """Parse breadcrumb nav from HTML to derive section_path for docs pages."""
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    nav = soup.find("nav", attrs={"class": re.compile(r"breadcrumb", re.IGNORECASE)})
    if not isinstance(nav, Tag):
        return []
    return [li.get_text(strip=True) for li in nav.find_all("li") if li.get_text(strip=True)]


def _derive_source(url: str) -> tuple[str, str]:
    netloc = urlparse(url).netloc or "synthetic"
    source = netloc.removeprefix("www.")
    source_id = hashlib.sha256(url.encode()).hexdigest()[:16]
    return source, source_id


def _apply_sanitize(data: dict[str, object]) -> dict[str, object]:
    for field in _SANITIZE_FIELDS:
        val = data.get(field)
        if isinstance(val, str):
            data[field], _ = sanitize(val)
    return data


def _parse_article(md: str, html: str, url: str) -> dict[str, object]:
    source, source_id = _derive_source(url)
    h1 = _H1_RE.search(md)
    lang_m = _LANG_RE.search(html)
    author_m = _AUTHOR_RE.search(md)
    published_at: str | None = None
    if html:
        soup = BeautifulSoup(html, "html.parser")
        pub_meta = soup.find("meta", property="article:published_time")
        if isinstance(pub_meta, Tag):
            published_at = str(pub_meta.get("content", "")) or None
    return {
        "source": source,
        "source_url": url,
        "source_id": source_id,
        "title": h1.group(1).strip() if h1 else "Untitled",
        "author": author_m.group(1).strip() if author_m else None,
        "published_at": published_at,
        "body_md": md,
        "language": lang_m.group(1) if lang_m else "en",
    }


def _parse_docs(md: str, html: str, url: str) -> dict[str, object]:
    source, source_id = _derive_source(url)
    h1 = _H1_RE.search(md)
    code_block_count = len(_CODE_FENCE_RE.findall(md)) // 2
    return {
        "source": source,
        "source_url": url,
        "source_id": source_id,
        "title": h1.group(1).strip() if h1 else "Untitled",
        "section_path": _extract_section_path(html),
        "body_md": md,
        "code_block_count": code_block_count,
        "last_updated": None,
    }


def _parse_product(md: str, html: str, url: str) -> dict[str, object]:
    source, source_id = _derive_source(url)
    h1 = _H1_RE.search(md)
    price: Decimal | None = None
    currency: str | None = None
    pm = _PRICE_RE.search(md)
    if pm:
        sym = (pm.group(1) or pm.group(4) or "").strip()
        num_raw = (pm.group(2) or pm.group(3) or "").strip()
        num_str = re.sub(r"[^\d.]", "", num_raw.replace(",", "."))
        try:
            price = Decimal(num_str) if num_str else None
            currency = _CURRENCY_MAP.get(sym, sym if len(sym) == _ISO_CODE_LEN else None)
        except InvalidOperation:
            pass
    in_stock_m = _IN_STOCK_RE.search(html)
    in_stock = in_stock_m.group(1).lower() not in ("false", "0", "no") if in_stock_m else True
    return {
        "source": source,
        "source_url": url,
        "source_id": source_id,
        "name": h1.group(1).strip() if h1 else None,
        "price": price,
        "currency": currency,
        "in_stock": in_stock,
        "description": md,
    }


def _parse_reference(md: str, _html: str, url: str) -> dict[str, object]:
    source, source_id = _derive_source(url)
    h1 = _H1_RE.search(md)
    term = _TERM_PREFIX_RE.sub("", h1.group(1).strip()) if h1 else "Unknown"
    return {
        "source": source,
        "source_url": url,
        "source_id": source_id,
        "term": term,
        "definition": md,
        "examples": [],
        "last_updated": None,
    }


_ParseFn = Callable[[str, str, str], dict[str, object]]

_PARSERS: dict[str, _ParseFn] = {
    "article": _parse_article,
    "docs": _parse_docs,
    "product": _parse_product,
    "reference": _parse_reference,
}


def extract_from_local(
    raw: str,
    page_type: PageType,
    *,
    source: str = "synthetic",
    source_id: str = "test-id",
    language: str = "en",
    section_path: list[str] | None = None,
    fallback_url: str = "https://example.invalid/synthetic",
) -> dict[str, object]:
    """Local extraction test double. Accepts HTML or markdown; never makes network calls."""
    if raw.lstrip().startswith("<"):
        html = raw
        md = _html_to_md(html)
    else:
        html = ""
        md = raw
    data = _PARSERS[page_type](md, html, fallback_url)
    data["source"] = source
    data["source_id"] = source_id
    data["source_url"] = fallback_url
    if page_type == "article":
        data["language"] = language
    if page_type == "docs" and section_path is not None:
        data["section_path"] = section_path
    return _apply_sanitize(data)

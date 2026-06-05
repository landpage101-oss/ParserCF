"""Adapter for Scrape This Site sandbox pages (https://www.scrapethissite.com/pages/).

Public scraping sandbox explicitly designed for web scraping practice.
robots.txt: Disallow /lessons/, /faq/ — /pages/** fully allowed.
Legal basis: non-commercial educational use of a purpose-built public scraping sandbox.
"""

from collections.abc import Iterable

_BASE = "https://www.scrapethissite.com/pages/"

_SEEDS: tuple[str, ...] = (
    # sandbox index — overview of all practice pages
    "https://www.scrapethissite.com/pages/",
    # individual sandbox pages (all within robots.txt-allowed /pages/ path)
    "https://www.scrapethissite.com/pages/simple/",  # Countries of the World
    "https://www.scrapethissite.com/pages/forms/",  # Hockey Teams (pagination)
    "https://www.scrapethissite.com/pages/ajax-javascript/",  # Oscar Films (JS/AJAX)
    "https://www.scrapethissite.com/pages/frames/",  # Frames & iFrames
    "https://www.scrapethissite.com/pages/advanced/",  # Advanced Topics
)


class ScrapethissiteComAdapter:
    page_type = "reference"
    domain = "www.scrapethissite.com"
    name = "scrapethissite_com"

    def list_urls(self, since: str | None = None) -> Iterable[str]:  # noqa: ARG002
        return list(_SEEDS)

    def parse_id(self, url: str) -> str:
        # Strip base prefix and trailing slash → e.g. "simple", "forms", "" (index)
        slug = url.removeprefix(_BASE).rstrip("/")
        return slug or "index"

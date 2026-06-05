"""Tests for ScrapethissiteComAdapter."""

from src.sources.scrapethissite_com import ScrapethissiteComAdapter


class TestScrapethissiteComAdapter:
    def setup_method(self) -> None:
        self.adapter = ScrapethissiteComAdapter()

    def test_list_urls_returns_seeds(self) -> None:
        urls = list(self.adapter.list_urls())
        assert len(urls) == 6
        assert "https://www.scrapethissite.com/pages/" in urls
        assert "https://www.scrapethissite.com/pages/simple/" in urls
        assert "https://www.scrapethissite.com/pages/forms/" in urls

    def test_list_urls_since_ignored(self) -> None:
        """since parameter is accepted but not used (static seed list)."""
        assert list(self.adapter.list_urls(since="2026-01-01")) == list(self.adapter.list_urls())

    def test_parse_id_strips_base_and_trailing_slash(self) -> None:
        assert self.adapter.parse_id("https://www.scrapethissite.com/pages/simple/") == "simple"
        assert self.adapter.parse_id("https://www.scrapethissite.com/pages/forms/") == "forms"
        assert (
            self.adapter.parse_id("https://www.scrapethissite.com/pages/ajax-javascript/")
            == "ajax-javascript"
        )
        assert self.adapter.parse_id("https://www.scrapethissite.com/pages/frames/") == "frames"
        assert self.adapter.parse_id("https://www.scrapethissite.com/pages/advanced/") == "advanced"

    def test_parse_id_index_page(self) -> None:
        assert self.adapter.parse_id("https://www.scrapethissite.com/pages/") == "index"

    def test_page_type_is_reference(self) -> None:
        assert self.adapter.page_type == "reference"

    def test_domain(self) -> None:
        assert self.adapter.domain == "www.scrapethissite.com"

    def test_name(self) -> None:
        assert self.adapter.name == "scrapethissite_com"

    def test_no_disallowed_paths(self) -> None:
        """Ensure no seed URL falls under robots.txt Disallow: /lessons/ or /faq/."""
        urls = list(self.adapter.list_urls())
        for url in urls:
            assert "/lessons/" not in url, f"Disallowed path in seed: {url}"
            assert "/faq/" not in url, f"Disallowed path in seed: {url}"

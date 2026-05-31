"""Unit tests for AnthropicNewsAdapter."""

from src.sources.anthropic_news import AnthropicNewsAdapter

_URL_PREFIX = "https://www.anthropic.com/news/"
_EXPECTED_COUNT = 19


def test_list_urls_returns_seeds() -> None:
    """list_urls() must yield exactly the hardcoded seeds, all in the news namespace."""
    adapter = AnthropicNewsAdapter()
    urls = list(adapter.list_urls())
    assert len(urls) == _EXPECTED_COUNT
    assert all(url.startswith(_URL_PREFIX) for url in urls)


def test_parse_id_strips_prefix() -> None:
    """parse_id() must strip the news-URL prefix and return the slug verbatim."""
    adapter = AnthropicNewsAdapter()
    url = "https://www.anthropic.com/news/claude-sonnet-4-6"
    assert adapter.parse_id(url) == "claude-sonnet-4-6"


def test_page_type_is_article() -> None:
    """page_type must be 'article' — binding for run.py extraction dispatch."""
    assert AnthropicNewsAdapter.page_type == "article"


def test_list_urls_ignores_since() -> None:
    """`since` parameter is accepted for Protocol compat but ignored in this iteration.

    Future incremental-refresh PR will implement filtering; this guard ensures
    semantics don't drift silently.
    """
    adapter = AnthropicNewsAdapter()
    assert list(adapter.list_urls()) == list(adapter.list_urls("2026-01-01"))

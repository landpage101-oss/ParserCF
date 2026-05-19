"""Adapter for Anthropic news articles (https://www.anthropic.com/news/)."""

from collections.abc import Iterable

_URL_PREFIX = "https://www.anthropic.com/news/"

_SEEDS: tuple[str, ...] = (
    "https://www.anthropic.com/news/claude-sonnet-4-6",
    "https://www.anthropic.com/news/claude-opus-4-7",
    "https://www.anthropic.com/news/core-views-on-ai-safety",
    "https://www.anthropic.com/news/the-case-for-targeted-regulation",
    "https://www.anthropic.com/news/clio",
    "https://www.anthropic.com/news/anthropic-acquires-stainless",
    "https://www.anthropic.com/news/claude-is-a-space-to-think",
    "https://www.anthropic.com/news/automated-alignment-researchers",
)


class AnthropicNewsAdapter:
    page_type = "article"
    domain = "www.anthropic.com"
    name = "anthropic_news"

    def list_urls(self, since: str | None = None) -> Iterable[str]:  # noqa: ARG002
        return list(_SEEDS)

    def parse_id(self, url: str) -> str:
        return url.removeprefix(_URL_PREFIX)

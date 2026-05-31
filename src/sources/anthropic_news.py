"""Adapter for Anthropic news articles (https://www.anthropic.com/news/)."""

from collections.abc import Iterable

_URL_PREFIX = "https://www.anthropic.com/news/"

_SEEDS: tuple[str, ...] = (
    # model releases
    "https://www.anthropic.com/news/claude-sonnet-4-6",
    "https://www.anthropic.com/news/claude-opus-4-7",
    "https://www.anthropic.com/news/claude-opus-4-8",
    "https://www.anthropic.com/news/claude-4",
    "https://www.anthropic.com/news/claude-3-family",
    "https://www.anthropic.com/news/3-5-models-and-computer-use",
    # safety policy & alignment
    "https://www.anthropic.com/news/core-views-on-ai-safety",
    "https://www.anthropic.com/news/the-case-for-targeted-regulation",
    "https://www.anthropic.com/news/anthropics-responsible-scaling-policy",
    "https://www.anthropic.com/news/claudes-constitution",
    "https://www.anthropic.com/news/measuring-agent-autonomy",
    "https://www.anthropic.com/news/automated-alignment-researchers",
    # technical research
    "https://www.anthropic.com/news/clio",
    "https://www.anthropic.com/news/contextual-retrieval",
    "https://www.anthropic.com/news/the-anthropic-economic-index",
    # product & ecosystem
    "https://www.anthropic.com/news/claude-is-a-space-to-think",
    "https://www.anthropic.com/news/donating-the-model-context-protocol-and-establishing-of-the-agentic-ai-foundation",
    # acquisition & usage research
    "https://www.anthropic.com/news/anthropic-acquires-stainless",
    "https://www.anthropic.com/news/how-people-use-claude-for-support-advice-and-companionship",
)


class AnthropicNewsAdapter:
    page_type = "article"
    domain = "www.anthropic.com"
    name = "anthropic_news"

    def list_urls(self, since: str | None = None) -> Iterable[str]:  # noqa: ARG002
        return list(_SEEDS)

    def parse_id(self, url: str) -> str:
        return url.removeprefix(_URL_PREFIX)

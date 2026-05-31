"""
#E (Variant A): discover new seed URLs for the anthropic_news adapter.

Run once to find articles not yet in _SEEDS, review output, then
manually add URLs to src/sources/anthropic_news.py.

Usage:
    python scripts/discover_anthropic_seeds.py [--limit 100]

Cost cap: 5 Firecrawl credits (one map call).
Output:  scripts/discovered_anthropic_seeds.txt  (new URLs only)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

_KNOWN_SEEDS: frozenset[str] = frozenset(
    {
        "https://www.anthropic.com/news/claude-sonnet-4-6",
        "https://www.anthropic.com/news/claude-opus-4-7",
        "https://www.anthropic.com/news/core-views-on-ai-safety",
        "https://www.anthropic.com/news/the-case-for-targeted-regulation",
        "https://www.anthropic.com/news/clio",
        "https://www.anthropic.com/news/anthropic-acquires-stainless",
        "https://www.anthropic.com/news/claude-is-a-space-to-think",
        "https://www.anthropic.com/news/automated-alignment-researchers",
    }
)

_NEWS_PREFIX = "https://www.anthropic.com/news/"


def _is_article_url(url: str) -> bool:
    """True for /news/<slug> — excludes the index page and non-article paths."""
    if not url.startswith(_NEWS_PREFIX):
        return False
    slug = url.removeprefix(_NEWS_PREFIX).strip("/")
    return bool(slug) and "/" not in slug and "#" not in slug and "?" not in slug


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Discover anthropic.com/news seed URLs")
    parser.add_argument("--limit", type=int, default=100, help="Max URLs to map (default 100)")
    args = parser.parse_args(argv)

    from firecrawl import Firecrawl  # type: ignore[import-untyped]

    client = Firecrawl(api_key=os.environ["FIRECRAWL_API_KEY"])

    print(f"Mapping https://www.anthropic.com/news/ (limit={args.limit})...")
    result = client.map(
        "https://www.anthropic.com/news/",
        search="/news/",
        limit=args.limit,
    )

    all_urls: list[str] = [lnk.url for lnk in (result.links or [])]
    print(f"Firecrawl returned {len(all_urls)} URLs total")

    article_urls = [u for u in all_urls if _is_article_url(u)]
    new_urls = [u for u in article_urls if u not in _KNOWN_SEEDS]

    print(f"Article URLs: {len(article_urls)}")
    print(f"Already in _SEEDS: {len(article_urls) - len(new_urls)}")
    print(f"New URLs to review: {len(new_urls)}")

    if not new_urls:
        print("\nNothing new — _SEEDS already covers all discovered articles.")
        return

    print("\n--- NEW URLs (review before adding to src/sources/anthropic_news.py) ---")
    for url in sorted(new_urls):
        print(f"  {url}")

    out = Path("scripts/discovered_anthropic_seeds.txt")
    out.write_text("\n".join(sorted(new_urls)) + "\n", encoding="utf-8")
    print(f"\nSaved to {out}")
    print(
        "\nNext step: review the list, add chosen URLs to _SEEDS in src/sources/anthropic_news.py"
    )


if __name__ == "__main__":
    main()

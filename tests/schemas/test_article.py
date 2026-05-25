import pytest
from pydantic import ValidationError

from src.schemas.article import Article


def test_happy_path() -> None:
    article = Article.model_validate(
        {
            "source": "test_adapter",
            "source_url": "https://example.com/article/test",
            "source_id": "article/test",
            "title": "Test Article Title",
            "author": "Jane Doe",
            "body_md": "This is a sufficiently long body for testing the article schema.",
            "language": "en",
        }
    )
    assert article.title == "Test Article Title"
    assert article.author == "Jane Doe"
    assert article.language == "en"
    assert article.published_at is None


def test_missing_required_field() -> None:
    with pytest.raises(ValidationError):
        Article.model_validate(
            {
                "source_url": "https://example.com/article/test",
                "source_id": "article/test",
                "title": "Test Article Title",
                "body_md": "This is a sufficiently long body for testing the article schema.",
                "language": "en",
            }
        )


def test_placeholder_rejected() -> None:
    with pytest.raises(ValidationError, match="placeholder/error"):
        Article.model_validate(
            {
                "source": "test_adapter",
                "source_url": "https://example.com/article/test",
                "source_id": "article/test",
                "title": "Test Article Title",
                "body_md": "Access denied. Please verify you are human.",
                "language": "en",
            }
        )


def test_legitimate_404_mention_accepted() -> None:
    Article.model_validate(
        {
            "source": "test_adapter",
            "source_url": "https://example.com/article/test",
            "source_id": "article/test",
            "title": "Test Article Title",
            "body_md": (
                "The upstream service returned error 404 in processing;"
                " our handler caught it and retried successfully."
            ),
            "language": "en",
        }
    )


def test_404_not_found_still_rejected() -> None:
    with pytest.raises(ValidationError, match="placeholder/error"):
        Article.model_validate(
            {
                "source": "test_adapter",
                "source_url": "https://example.com/article/test",
                "source_id": "article/test",
                "title": "Test Article Title",
                "body_md": "404 Not Found — the page you requested does not exist on this server.",
                "language": "en",
            }
        )


# ── published_at normalisation ────────────────────────────────────────────────

_BASE = {
    "source": "anthropic_news",
    "source_url": "https://www.anthropic.com/news/x",
    "source_id": "x",
    "title": "T",
    "body_md": "This is a sufficiently long body for testing the schema.",
    "language": "en",
}


def _article(**overrides: object) -> Article:
    return Article.model_validate({**_BASE, **overrides})


def test_published_at_human_abbreviated_month() -> None:
    a = _article(published_at="Feb 17, 2026")
    assert a.published_at is not None
    assert (a.published_at.year, a.published_at.month, a.published_at.day) == (2026, 2, 17)


def test_published_at_human_full_month() -> None:
    a = _article(published_at="January 5, 2025")
    assert a.published_at is not None
    assert (a.published_at.year, a.published_at.month, a.published_at.day) == (2025, 1, 5)


def test_published_at_iso_datetime_passthrough() -> None:
    # regression guard for eval fixture 01 — must stay exact
    a = _article(published_at="2026-03-15T00:00:00Z")
    assert a.published_at is not None
    assert a.published_at.isoformat().startswith("2026-03-15T00:00:00")


def test_published_at_iso_date_only_passthrough() -> None:
    a = _article(published_at="2023-03-08")
    assert a.published_at is not None
    assert (a.published_at.year, a.published_at.month, a.published_at.day) == (2023, 3, 8)


def test_published_at_blank_becomes_none() -> None:
    assert _article(published_at="   ").published_at is None


def test_published_at_none_passthrough() -> None:
    assert _article(published_at=None).published_at is None


def test_published_at_unparseable_rejected() -> None:
    with pytest.raises(ValidationError):
        _article(published_at="sometime last spring")

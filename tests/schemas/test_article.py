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

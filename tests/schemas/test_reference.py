import pytest
from pydantic import ValidationError

from src.schemas.reference import ReferenceEntry


def test_happy_path() -> None:
    entry = ReferenceEntry.model_validate(
        {
            "source": "glossary_adapter",
            "source_url": "https://glossary.example.com/terms/idempotency",
            "source_id": "terms/idempotency",
            "term": "Idempotency",
            "definition": (
                "A property of operations where applying the same operation multiple "
                "times produces the same result as applying it once."
            ),
            "examples": ["PUT /resource/123 is idempotent; POST /resource is not."],
        }
    )
    assert entry.term == "Idempotency"
    assert entry.examples == ["PUT /resource/123 is idempotent; POST /resource is not."]
    assert entry.last_updated is None


def test_missing_required_field() -> None:
    with pytest.raises(ValidationError):
        ReferenceEntry.model_validate(
            {
                "source_url": "https://glossary.example.com/terms/idempotency",
                "source_id": "terms/idempotency",
                "term": "Idempotency",
                "definition": (
                    "A property of operations where applying the same operation multiple "
                    "times produces the same result as applying it once."
                ),
            }
        )


def test_placeholder_rejected() -> None:
    with pytest.raises(ValidationError, match="placeholder/error"):
        ReferenceEntry.model_validate(
            {
                "source": "glossary_adapter",
                "source_url": "https://glossary.example.com/terms/idempotency",
                "source_id": "terms/idempotency",
                "term": "Idempotency",
                "definition": "Access denied. Please verify you are human.",
            }
        )


def test_legitimate_404_mention_accepted() -> None:
    ReferenceEntry.model_validate(
        {
            "source": "glossary_adapter",
            "source_url": "https://glossary.example.com/terms/idempotency",
            "source_id": "terms/idempotency",
            "term": "Idempotency",
            "definition": (
                "The upstream service returned error 404 in processing;"
                " our handler caught it and retried successfully."
            ),
        }
    )


def test_404_not_found_still_rejected() -> None:
    with pytest.raises(ValidationError, match="placeholder/error"):
        ReferenceEntry.model_validate(
            {
                "source": "glossary_adapter",
                "source_url": "https://glossary.example.com/terms/idempotency",
                "source_id": "terms/idempotency",
                "term": "Idempotency",
                "definition": "404 Not Found — the page you requested does not exist.",
            }
        )


def test_legitimate_long_content_with_marker_accepted() -> None:
    """Regression: long definition mentioning error-state phrases is not a placeholder."""
    long_definition = (
        "The HTTP 404 Not Found client error response status code indicates "
        "that the server cannot find the requested resource. A 404 status only "
        "indicates that the resource is missing. " * 10
    )
    assert len(long_definition) >= 500
    ReferenceEntry.model_validate(
        {
            "source": "glossary_adapter",
            "source_url": "https://glossary.example.com/terms/http-404",
            "source_id": "terms/http-404",
            "term": "HTTP 404",
            "definition": long_definition,
        }
    )

import pytest
from pydantic import ValidationError

from src.schemas.docs import DocsPage


def test_happy_path() -> None:
    page = DocsPage.model_validate(
        {
            "source": "docs_python_org",
            "source_url": "https://docs.python.org/3/library/json.html",
            "source_id": "library/json",
            "title": "json — JSON encoder and decoder",
            "section_path": ["Library Reference", "Data Formats"],
            "body_md": "The json module exposes an API familiar to users of the standard library.",
            "code_block_count": 3,
        }
    )
    assert page.title == "json — JSON encoder and decoder"
    assert page.code_block_count == 3
    assert page.section_path == ["Library Reference", "Data Formats"]
    assert page.last_updated is None


def test_missing_required_field() -> None:
    with pytest.raises(ValidationError):
        DocsPage.model_validate(
            {
                "source_url": "https://docs.python.org/3/library/json.html",
                "source_id": "library/json",
                "title": "json — JSON encoder and decoder",
                "body_md": "The json module exposes an API. " * 2,
                "code_block_count": 0,
            }
        )


def test_placeholder_rejected() -> None:
    with pytest.raises(ValidationError, match="placeholder/error"):
        DocsPage.model_validate(
            {
                "source": "docs_python_org",
                "source_url": "https://docs.python.org/3/library/json.html",
                "source_id": "library/json",
                "title": "Access Denied",
                "body_md": "Access denied. Please verify you are human.",
                "code_block_count": 0,
            }
        )

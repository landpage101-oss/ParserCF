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


def test_legitimate_404_mention_accepted() -> None:
    DocsPage.model_validate(
        {
            "source": "docs_python_org",
            "source_url": "https://docs.python.org/3/library/json.html",
            "source_id": "library/json",
            "title": "Error Handling",
            "body_md": (
                "The upstream service returned error 404 in processing;"
                " our handler caught it and retried successfully."
            ),
            "code_block_count": 0,
        }
    )


def test_404_not_found_still_rejected() -> None:
    with pytest.raises(ValidationError, match="placeholder/error"):
        DocsPage.model_validate(
            {
                "source": "docs_python_org",
                "source_url": "https://docs.python.org/3/library/json.html",
                "source_id": "library/json",
                "title": "Error Handling",
                "body_md": "404 Not Found — the page you requested does not exist on this server.",
                "code_block_count": 0,
            }
        )


def test_legitimate_long_content_with_marker_accepted() -> None:
    """Regression: vf #4 (MDN HTTP 404 docs page) was wrongly rejected by old validator.

    Long content discussing 'page not found' / '404 not found' as a topic is
    legitimate documentation, not a placeholder.
    """
    long_body = (
        "The HTTP 404 Not Found client error response status code indicates "
        "that the server cannot find the requested resource. A 404 status only "
        "indicates that the resource is missing. " * 10
    )
    assert len(long_body) >= 500
    DocsPage.model_validate(
        {
            "source": "developer_mozilla_org",
            "source_url": "https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/404",
            "source_id": "Web/HTTP/Status/404",
            "title": "404 Not Found",
            "section_path": ["Web", "HTTP", "Status", "404"],
            "body_md": long_body,
            "code_block_count": 0,
        }
    )

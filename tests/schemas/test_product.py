import pytest
from pydantic import ValidationError

from src.schemas.product import Product


def test_happy_path() -> None:
    product = Product.model_validate(
        {
            "source": "shop_adapter",
            "source_url": "https://shop.example.com/products/widget-x",
            "source_id": "products/widget-x",
            "name": "Widget X",
            "sku": "WX-001",
            "price": "99.99",
            "currency": "USD",
            "in_stock": True,
            "description": "A high-quality widget for all your needs.",
        }
    )
    assert product.name == "Widget X"
    assert product.in_stock is True
    assert str(product.price) == "99.99"
    assert product.currency == "USD"


def test_missing_required_field() -> None:
    with pytest.raises(ValidationError):
        Product.model_validate(
            {
                "source_url": "https://shop.example.com/products/widget-x",
                "source_id": "products/widget-x",
                "name": "Widget X",
                "in_stock": True,
            }
        )


def test_placeholder_rejected() -> None:
    with pytest.raises(ValidationError, match="placeholder/error"):
        Product.model_validate(
            {
                "source": "shop_adapter",
                "source_url": "https://shop.example.com/products/widget-x",
                "source_id": "products/widget-x",
                "name": "Widget X",
                "in_stock": True,
                "description": "Access denied. Please verify you are human.",
            }
        )


def test_legitimate_404_mention_accepted() -> None:
    Product.model_validate(
        {
            "source": "shop_adapter",
            "source_url": "https://shop.example.com/products/widget-x",
            "source_id": "products/widget-x",
            "name": "Widget X",
            "in_stock": True,
            "description": (
                "The upstream service returned error 404 in processing;"
                " our handler caught it and retried successfully."
            ),
        }
    )


def test_404_not_found_still_rejected() -> None:
    with pytest.raises(ValidationError, match="placeholder/error"):
        Product.model_validate(
            {
                "source": "shop_adapter",
                "source_url": "https://shop.example.com/products/widget-x",
                "source_id": "products/widget-x",
                "name": "Widget X",
                "in_stock": True,
                "description": "404 Not Found — the page you requested does not exist.",
            }
        )


def test_legitimate_long_content_with_marker_accepted() -> None:
    """Regression: long description mentioning error-state phrases is not a placeholder."""
    long_description = (
        "The HTTP 404 Not Found client error response status code indicates "
        "that the server cannot find the requested resource. A 404 status only "
        "indicates that the resource is missing. " * 10
    )
    assert len(long_description) >= 500
    Product.model_validate(
        {
            "source": "shop_adapter",
            "source_url": "https://shop.example.com/products/http-guide",
            "source_id": "products/http-guide",
            "name": "HTTP Error Guide",
            "in_stock": True,
            "description": long_description,
        }
    )


def test_zero_or_negative_price_rejected() -> None:
    with pytest.raises(ValidationError, match="price must be > 0"):
        Product.model_validate(
            {
                "source": "shop_adapter",
                "source_url": "https://shop.example.com/products/widget-x",
                "source_id": "products/widget-x",
                "name": "Widget X",
                "price": "0",
                "currency": "USD",
                "in_stock": True,
            }
        )

"""Tests for DummyjsonComAdapter."""

from __future__ import annotations

from decimal import Decimal

from src.schemas.product import Product
from src.sources._http_base import KIND_HTTP
from src.sources.dummyjson_com import DummyjsonComAdapter


class TestDummyjsonComAdapter:
    def setup_method(self) -> None:
        self.adapter = DummyjsonComAdapter()

    def test_list_urls_returns_10_product_seeds(self) -> None:
        urls = list(self.adapter.list_urls())
        assert len(urls) == 10
        assert all(url.startswith("https://dummyjson.com/products/") for url in urls)

    def test_parse_id_extracts_numeric_id(self) -> None:
        assert self.adapter.parse_id("https://dummyjson.com/products/5") == "5"
        assert self.adapter.parse_id("https://dummyjson.com/products/5/") == "5"
        assert self.adapter.parse_id("https://dummyjson.com/products/10?foo=bar") == "10"

    def test_page_type_is_product(self) -> None:
        assert self.adapter.page_type == "product"

    def test_kind_is_http(self) -> None:
        assert self.adapter.kind == KIND_HTTP

    def test_parse_response_maps_minimum_product_fields(self) -> None:
        url = "https://dummyjson.com/products/1"
        response: dict[str, object] = {
            "id": 1,
            "title": "Essence Mascara",
            "description": "An excellent product.",
            "sku": "RCH45Q1A",
            "price": 9.99,
            "stock": 5,
        }
        result = self.adapter.parse_response(response, url)
        assert result["source"] == "dummyjson_com"
        assert result["source_id"] == "1"
        assert result["source_url"] == url
        assert result["name"] == "Essence Mascara"
        assert result["sku"] == "RCH45Q1A"
        assert result["currency"] == "USD"
        assert result["in_stock"] is True
        assert result["description"] == "An excellent product."

    def test_parse_response_price_is_float_passthrough(self) -> None:
        """Adapter returns JSON-primitive; Pydantic Product converts to Decimal at validate."""
        url = "https://dummyjson.com/products/1"
        response: dict[str, object] = {"title": "X", "price": 9.99, "stock": 1}
        result = self.adapter.parse_response(response, url)
        assert result["price"] == 9.99
        assert isinstance(result["price"], float)
        assert not isinstance(result["price"], Decimal)

    def test_parse_response_output_validates_as_product_with_decimal_price(self) -> None:
        """Lock-in: adapter output passes Product.model_validate with clean Decimal."""
        url = "https://dummyjson.com/products/1"
        response: dict[str, object] = {
            "title": "Test Product",
            "description": "A real description longer than placeholder threshold.",
            "price": 9.99,
            "stock": 5,
        }
        result = self.adapter.parse_response(response, url)
        product = Product.model_validate(result)
        assert product.price == Decimal("9.99")  # Pydantic str-coerces float, no precision loss
        assert product.name == "Test Product"
        assert product.in_stock is True

    def test_parse_response_in_stock_from_stock_count(self) -> None:
        url = "https://dummyjson.com/products/1"
        base: dict[str, object] = {"title": "X", "price": 1.0}

        result_zero = self.adapter.parse_response({**base, "stock": 0}, url)
        assert result_zero["in_stock"] is False

        result_positive = self.adapter.parse_response({**base, "stock": 99}, url)
        assert result_positive["in_stock"] is True

        result_missing = self.adapter.parse_response(base, url)
        assert result_missing["in_stock"] is False

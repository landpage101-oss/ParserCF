from decimal import Decimal

from pydantic import BaseModel, Field, HttpUrl, field_validator


class Product(BaseModel):
    source: str = Field(min_length=1, max_length=64)
    source_url: HttpUrl
    source_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=300)
    sku: str | None = None
    price: Decimal | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    in_stock: bool
    description: str | None = None

    @field_validator("price")
    @classmethod
    def positive(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v <= 0:
            raise ValueError("price must be > 0 if present")
        return v

    @field_validator("description")
    @classmethod
    def reject_placeholder(cls, v: str | None) -> str | None:
        if v is None:
            return v
        markers = {
            "lorem ipsum",
            "page not found",
            "access denied",
            "404 not found",
            "403 forbidden",
            "are you a robot",
        }
        low = v.lower()
        for m in markers:
            if m in low:
                raise ValueError(f"description looks like placeholder/error: '{m}'")
        return v

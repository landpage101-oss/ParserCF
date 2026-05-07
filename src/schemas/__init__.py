from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel

from src.schemas.article import Article
from src.schemas.docs import DocsPage
from src.schemas.product import Product
from src.schemas.reference import ReferenceEntry

PAGE_TYPE_TO_SCHEMA: dict[str, type[BaseModel]] = {
    "article": Article,
    "docs": DocsPage,
    "product": Product,
    "reference": ReferenceEntry,
}

__all__ = [
    "PAGE_TYPE_TO_SCHEMA",
    "Article",
    "DocsPage",
    "Product",
    "ReferenceEntry",
]

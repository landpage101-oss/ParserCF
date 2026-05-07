from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator


class Article(BaseModel):
    source: str = Field(min_length=1, max_length=64)
    source_url: HttpUrl
    source_id: str = Field(min_length=1, max_length=256)
    title: str = Field(min_length=1, max_length=500)
    author: str | None = None
    published_at: datetime | None = None
    body_md: str = Field(min_length=10)
    language: str = Field(pattern=r"^[a-z]{2}$")

    @field_validator("body_md")
    @classmethod
    def reject_placeholder(cls, v: str) -> str:
        markers = {
            "lorem ipsum",
            "page not found",
            "access denied",
            "404",
            "403 forbidden",
            "are you a robot",
        }
        low = v.lower()
        for m in markers:
            if m in low:
                raise ValueError(f"body looks like placeholder/error: '{m}'")
        return v

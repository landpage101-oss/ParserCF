from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator


class DocsPage(BaseModel):
    source: str = Field(min_length=1, max_length=64)
    source_url: HttpUrl
    source_id: str = Field(min_length=1, max_length=256)
    title: str = Field(min_length=1)
    section_path: list[str] = Field(default_factory=list)
    body_md: str = Field(min_length=10)
    code_block_count: int = Field(ge=0)
    last_updated: datetime | None = None

    @field_validator("body_md")
    @classmethod
    def reject_placeholder(cls, v: str) -> str:
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
                raise ValueError(f"body looks like placeholder/error: '{m}'")
        return v

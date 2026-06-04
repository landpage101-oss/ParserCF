from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator

from src.schemas._validators import detect_placeholder_marker


class ReferenceEntry(BaseModel):
    source: str = Field(min_length=1, max_length=64)
    source_url: HttpUrl
    source_id: str = Field(min_length=1, max_length=256)
    term: str = Field(min_length=1, max_length=300)
    definition: str = Field(min_length=10)
    examples: list[str] = Field(default_factory=list)
    last_updated: datetime | None = None

    @field_validator("definition")
    @classmethod
    def reject_placeholder(cls, v: str) -> str:
        marker = detect_placeholder_marker(v)
        if marker is not None:
            raise ValueError(f"definition looks like placeholder/error: '{marker}'")
        return v

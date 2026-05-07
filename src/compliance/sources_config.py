from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class SourceConfig(BaseModel):
    domain: str = Field(min_length=1)
    added_by: str = Field(min_length=1)
    reviewed_at: date
    legal_basis: str = Field(min_length=10)
    rate_limit_rps: float = Field(gt=0, le=10)
    adapter: str = Field(pattern=r"^src/sources/[a-z][a-z0-9_]*\.py$")
    api_available: bool
    api_check_notes: str | None = None


def load_sources(config_path: Path | None = None) -> list[SourceConfig]:
    path = config_path or Path("config/sources.yaml")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [SourceConfig.model_validate(item) for item in raw]

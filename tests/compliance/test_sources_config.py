from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.compliance.sources_config import SourceConfig, load_sources

_VALID_ENTRY = {
    "domain": "docs.python.org",
    "added_by": "landpage101-oss",
    "reviewed_at": "2026-05-04",
    "legal_basis": "Public documentation, robots.txt allow, no auth required",
    "rate_limit_rps": 1.0,
    "adapter": "src/sources/docs_python_org.py",
    "api_available": False,
}


def test_valid_entry_parses() -> None:
    cfg = SourceConfig.model_validate(_VALID_ENTRY)
    assert cfg.domain == "docs.python.org"
    assert cfg.api_check_notes is None


def test_negative_rate_limit_rejected() -> None:
    bad = {**_VALID_ENTRY, "rate_limit_rps": -1.0}
    with pytest.raises(ValidationError):
        SourceConfig.model_validate(bad)


def test_zero_rate_limit_rejected() -> None:
    bad = {**_VALID_ENTRY, "rate_limit_rps": 0}
    with pytest.raises(ValidationError):
        SourceConfig.model_validate(bad)


def test_rate_limit_above_cap_rejected() -> None:
    bad = {**_VALID_ENTRY, "rate_limit_rps": 11.0}
    with pytest.raises(ValidationError):
        SourceConfig.model_validate(bad)


def test_invalid_adapter_pattern_rejected() -> None:
    # uppercase in adapter path
    bad = {**_VALID_ENTRY, "adapter": "src/sources/Foo.py"}
    with pytest.raises(ValidationError):
        SourceConfig.model_validate(bad)


def test_adapter_wrong_prefix_rejected() -> None:
    bad = {**_VALID_ENTRY, "adapter": "adapters/docs_python_org.py"}
    with pytest.raises(ValidationError):
        SourceConfig.model_validate(bad)


def test_load_sources_empty_yaml(tmp_path: Path) -> None:
    yaml_file = tmp_path / "sources.yaml"
    yaml_file.write_text("[]", encoding="utf-8")
    result = load_sources(yaml_file)
    assert result == []


def test_load_sources_valid_entry(tmp_path: Path) -> None:
    content = textwrap.dedent("""\
        - domain: docs.python.org
          added_by: landpage101-oss
          reviewed_at: "2026-05-04"
          legal_basis: "Public documentation, robots.txt allow, no auth required"
          rate_limit_rps: 1.0
          adapter: src/sources/docs_python_org.py
          api_available: false
    """)
    yaml_file = tmp_path / "sources.yaml"
    yaml_file.write_text(content, encoding="utf-8")
    sources = load_sources(yaml_file)
    assert len(sources) == 1
    assert sources[0].domain == "docs.python.org"


def test_load_sources_invalid_entry_raises(tmp_path: Path) -> None:
    content = textwrap.dedent("""\
        - domain: docs.python.org
          added_by: landpage101-oss
          reviewed_at: "2026-05-04"
          legal_basis: "Short"
          rate_limit_rps: -5
          adapter: src/sources/docs_python_org.py
          api_available: false
    """)
    yaml_file = tmp_path / "sources.yaml"
    yaml_file.write_text(content, encoding="utf-8")
    with pytest.raises(ValidationError):
        load_sources(yaml_file)

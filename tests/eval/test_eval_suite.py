import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.extract import extract_from_local
from src.safety.sanitize import sanitize
from src.schemas import PAGE_TYPE_TO_SCHEMA


def _resolve_base_field(rule_key: str) -> str:
    for suffix in ("_min_length", "_must_contain", "_min"):
        if rule_key.endswith(suffix):
            return rule_key.removesuffix(suffix)
    raise ValueError(f"unknown soft-rule suffix: {rule_key}")


def _check_soft(value: object, rule_key: str, rule_value: object) -> None:
    """Soft checks: *_min_length, *_must_contain, *_min."""
    if rule_key.endswith("_min_length"):
        assert len(str(value)) >= int(rule_value), f"len({value!r}) < {rule_value}"  # type: ignore[arg-type]
    elif rule_key.endswith("_must_contain"):
        for needle in rule_value:  # type: ignore[union-attr]
            assert needle.lower() in str(value).lower(), f"missing '{needle}' in field"
    elif rule_key.endswith("_min"):
        assert int(value or 0) >= int(rule_value), f"{value} < {rule_value}"  # type: ignore[arg-type,call-overload]
    else:
        raise AssertionError(f"unknown soft rule: {rule_key}")


def _build_local_kwargs(
    expected_pydantic: dict[str, object],
    input_path: Path,
) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "source": expected_pydantic.get("source", "synthetic"),
        "source_id": expected_pydantic.get("source_id", input_path.stem),
        "language": expected_pydantic.get("language", "en"),
        "section_path": (
            expected_pydantic["section_path"]
            if isinstance(expected_pydantic.get("section_path"), list)
            else None
        ),
    }
    if "source_url" in expected_pydantic:
        kwargs["fallback_url"] = expected_pydantic["source_url"]
    return kwargs


def test_fixture(fixture_pair: tuple[str, Path, Path]) -> None:
    _name, input_path, expected_path = fixture_pair
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    raw = input_path.read_text(encoding="utf-8")

    # 1. Sanitize layer
    cleaned, warnings = sanitize(raw)
    expected_warns = expected.get("expected_sanitize_warnings", [])
    if expected_warns:
        assert set(expected_warns).issubset(set(warnings)), (
            f"sanitize warnings mismatch: got {warnings}, expected >=  {expected_warns}"
        )

    # 2. Extraction and validation
    schema_cls = PAGE_TYPE_TO_SCHEMA[expected["page_type"]]
    expected_status = expected["expected_validation_status"]
    expected_pydantic = expected.get("expected_pydantic", {})
    kwargs = _build_local_kwargs(expected_pydantic, input_path)

    if expected_status == "rejected":
        obj = extract_from_local(cleaned, expected["page_type"], **kwargs)  # type: ignore[arg-type]
        with pytest.raises(ValidationError) as exc:
            schema_cls.model_validate(obj)
        marker = expected.get("expected_validation_error_contains")
        if marker:
            assert marker.lower() in str(exc.value).lower()
        return

    obj = extract_from_local(cleaned, expected["page_type"], **kwargs)  # type: ignore[arg-type]
    instance = schema_cls.model_validate(obj)

    # 3. Compare with expected_pydantic (hard + soft checks)
    expected_fields = expected.get("expected_pydantic", {})
    dump = instance.model_dump(mode="json")

    for k, v in expected_fields.items():
        if any(k.endswith(suf) for suf in ("_min_length", "_must_contain", "_min")):
            base_field = _resolve_base_field(k)
            _check_soft(dump.get(base_field), k, v)
        else:
            assert str(dump.get(k)) == str(v), f"field {k}: got {dump.get(k)!r}, expected {v!r}"

    # 4. Negative checks (must_not_contain_in_body)
    for needle in expected.get("must_not_contain_in_body", []):
        body = dump.get("body_md") or dump.get("definition") or ""
        assert needle.lower() not in body.lower(), f"forbidden token '{needle}' leaked into output"


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("body_md_min_length", "body_md"),
        ("definition_must_contain", "definition"),
        ("code_block_count_min", "code_block_count"),
        ("title_must_contain", "title"),
    ],
)
def test_resolve_base_field(key: str, expected: str) -> None:
    assert _resolve_base_field(key) == expected


def test_resolve_base_field_rejects_unknown_suffix() -> None:
    with pytest.raises(ValueError, match="unknown soft-rule suffix"):
        _resolve_base_field("plain_field")

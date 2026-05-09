from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _discover() -> list[tuple[str, Path, Path]]:
    """Собирает пары (input_path, expected_path) по всем категориям."""
    pairs: list[tuple[str, Path, Path]] = []
    for category in ("article", "docs", "product", "reference"):
        cat_dir = FIXTURES_DIR / category
        if not cat_dir.exists():
            continue
        for expected in sorted(cat_dir.glob("*.expected.json")):
            base = expected.name.replace(".expected.json", "")
            for ext in (".html", ".md", ".captured.md"):
                inp = cat_dir / f"{base}{ext}"
                if inp.exists():
                    pairs.append((f"{category}/{base}", inp, expected))
                    break
    return pairs


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "fixture_pair" in metafunc.fixturenames:
        pairs = _discover()
        ids = [p[0] for p in pairs]
        metafunc.parametrize("fixture_pair", pairs, ids=ids)

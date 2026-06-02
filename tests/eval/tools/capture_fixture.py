"""Capture fixtures via Firecrawl from allow-listed URLs.
Run: `python -m tests.eval.tools.capture_fixture`.
One-shot operator tool — NOT executed in CI.
"""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from firecrawl import Firecrawl

FIXTURES_DIR = Path("tests/eval/fixtures")

CAPTURED = [
    {
        "id": "08_python_json",
        "category": "docs",
        "url": "https://docs.python.org/3/library/json.html",
        "page_type": "docs",
    },
    {
        "id": "09_mdn_get",
        "category": "docs",
        "url": "https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/GET",
        "page_type": "docs",
    },
    {
        "id": "17_arxiv_abstract",
        "category": "reference",
        "url": "https://arxiv.org/abs/2210.03629",
        "page_type": "reference",
    },
]


def _normalise_body(body: str) -> str:
    """Ensure body ends with exactly one trailing newline for clean git diffs."""
    if not body:
        return ""
    return body.rstrip("\n") + "\n"


def _hash(body: str) -> str:
    return "sha256:" + hashlib.sha256(body.encode()).hexdigest()


def _write_json(path: Path, data: dict) -> None:
    """Write JSON with stable formatting and a trailing newline."""
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    fc = Firecrawl(api_key=os.environ["FIRECRAWL_API_KEY"])
    for spec in CAPTURED:
        out_dir = FIXTURES_DIR / spec["category"]
        out_dir.mkdir(parents=True, exist_ok=True)
        md_path = out_dir / f"{spec['id']}.captured.md"
        meta_path = out_dir / f"{spec['id']}.expected.json"

        print(f"[capture] {spec['url']}")
        doc = fc.scrape(spec["url"], formats=["markdown"], only_main_content=True)
        body = _normalise_body(getattr(doc, "markdown", "") or "")
        new_hash = _hash(body)

        # 1. Markdown body: write only if content differs (or file is new).
        #    Skipping no-op writes keeps `git diff` clean across cron runs.
        old_body = md_path.read_text(encoding="utf-8") if md_path.exists() else None
        if old_body != body:
            md_path.write_text(body, encoding="utf-8")
            print(f"[md]     {md_path} updated")
        else:
            print(f"[md]     {md_path} unchanged")

        # 2. Metadata JSON.
        if not meta_path.exists():
            # New fixture: full skeleton, reviewer fills in expected_pydantic manually.
            meta = {
                "page_type": spec["page_type"],
                "captured_at": datetime.now(UTC).isoformat(),
                "captured_from": spec["url"],
                "captured_via": "firecrawl_scrape",
                "captured_content_hash": new_hash,
                "edge_case": "TODO: describe",
                "expected_pydantic": {
                    "title_must_contain": "TODO",
                    "body_md_min_length": max(500, len(body) // 2),
                },
                "expected_validation_status": "ok",
            }
            _write_json(meta_path, meta)
            print(f"[stub]   {meta_path} — fill in 'expected_pydantic' manually")
            continue

        # Existing fixture: only touch captured_at + captured_content_hash when
        # the underlying content actually changed. Otherwise leave file intact
        # so cron-driven runs do not produce spurious diffs.
        existing = json.loads(meta_path.read_text(encoding="utf-8"))
        if existing.get("captured_content_hash") == new_hash:
            print(f"[meta]   {meta_path} unchanged (hash match)")
            continue

        existing["captured_content_hash"] = new_hash
        existing["captured_at"] = datetime.now(UTC).isoformat()
        _write_json(meta_path, existing)
        print(f"[meta]   {meta_path} refreshed (new hash)")


if __name__ == "__main__":
    main()

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


def main() -> None:
    fc = Firecrawl(api_key=os.environ["FIRECRAWL_API_KEY"])
    for spec in CAPTURED:
        out_dir = FIXTURES_DIR / spec["category"]
        out_dir.mkdir(parents=True, exist_ok=True)
        md_path = out_dir / f"{spec['id']}.captured.md"
        meta_path = out_dir / f"{spec['id']}.expected.json"

        print(f"[capture] {spec['url']}")  # noqa: T201
        doc = fc.scrape(spec["url"], formats=["markdown"], only_main_content=True)
        body = getattr(doc, "markdown", "") or ""
        md_path.write_text(body, encoding="utf-8")

        # generate expected.json skeleton — reviewer fills in expected_pydantic manually
        if not meta_path.exists():
            meta = {
                "page_type": spec["page_type"],
                "captured_at": datetime.now(UTC).isoformat(),
                "captured_from": spec["url"],
                "captured_via": "firecrawl_scrape",
                "captured_content_hash": "sha256:" + hashlib.sha256(body.encode()).hexdigest(),
                "edge_case": "TODO: describe",
                "expected_pydantic": {
                    "title_must_contain": "TODO",
                    "body_md_min_length": max(500, len(body) // 2),
                },
                "expected_validation_status": "ok",
            }
            meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[stub]   {meta_path} — fill in 'expected_pydantic' manually")  # noqa: T201
        else:
            # update content_hash only; leave everything else intact
            existing = json.loads(meta_path.read_text(encoding="utf-8"))
            existing["captured_content_hash"] = (
                "sha256:" + hashlib.sha256(body.encode()).hexdigest()
            )
            existing["captured_at"] = datetime.now(UTC).isoformat()
            meta_path.write_text(
                json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8"
            )


if __name__ == "__main__":
    main()

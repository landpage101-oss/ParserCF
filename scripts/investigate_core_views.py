"""
#A investigation: core-views-on-ai-safety batch-context flake.

Phase 1 — 5x isolated fetch, no batch context.
Run: python scripts/investigate_core_views.py

Hypothesis: fetch fails in batch (position 3, after 2 successful fetches)
but succeeds in isolation — pointing to rate-limit or SDK connection-pool issue.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

# make src importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
# surface SDK-level retries and HTTP details
logging.getLogger("firecrawl").setLevel(logging.DEBUG)
logging.getLogger("httpx").setLevel(logging.DEBUG)
logging.getLogger("httpcore").setLevel(logging.DEBUG)

from src.extract import fetch_via_firecrawl  # noqa: E402

TARGET = "https://www.anthropic.com/news/core-views-on-ai-safety"
RUNS = 5
DELAY_BETWEEN = 5  # seconds — avoid back-to-back hammering


def main() -> None:
    results: list[dict] = []

    for i in range(1, RUNS + 1):
        print(f"\n{'=' * 60}")
        print(f"Run {i}/{RUNS}  url={TARGET}")
        t0 = time.monotonic()
        try:
            raw = fetch_via_firecrawl(TARGET, "article")
            elapsed = time.monotonic() - t0
            keys = list(raw.keys())
            title = raw.get("title", "<no title>")
            body_len = len(str(raw.get("body_md", "")))
            print(
                f"  OK  elapsed={elapsed:.1f}s  title={title!r}  body_len={body_len}  keys={keys}"
            )
            results.append({"run": i, "status": "ok", "elapsed": elapsed, "title": title})
        except Exception as exc:  # noqa: BLE001
            elapsed = time.monotonic() - t0
            print(f"  FAIL  elapsed={elapsed:.1f}s  {type(exc).__name__}: {exc}")
            results.append(
                {
                    "run": i,
                    "status": "fail",
                    "elapsed": elapsed,
                    "exc": f"{type(exc).__name__}: {exc}",
                }
            )

        if i < RUNS:
            print(f"  sleeping {DELAY_BETWEEN}s before next run...")
            time.sleep(DELAY_BETWEEN)

    print(f"\n{'=' * 60}")
    print("SUMMARY")
    ok = sum(1 for r in results if r["status"] == "ok")
    fail = len(results) - ok
    print(f"  {ok}/{RUNS} OK,  {fail}/{RUNS} FAIL")
    for r in results:
        if r["status"] == "ok":
            print(f"  run {r['run']}: OK  {r['elapsed']:.1f}s  title={r.get('title', '')!r}")
        else:
            print(f"  run {r['run']}: FAIL  {r['elapsed']:.1f}s  {r['exc']}")

    if ok == RUNS:
        print("\nCONCLUSION: succeeds in isolation every time → batch-context issue")
        print(
            "  Next step: Phase 2 — instrumented batch, "
            "watch for rate-limit or SDK state after N requests"
        )
    elif ok == 0:
        print(
            "\nCONCLUSION: fails consistently in isolation"
            " → URL-level issue (CDN block, page structure, etc.)"
        )
        print("  Next step: retry with proxy:stealth or exclude seed from adapter")
    else:
        print("\nCONCLUSION: intermittent — flaky CDN or SDK timeout on long page")
        print("  Next step: check elapsed on failures — if ~30s or ~120s, confirm SDK retry count")


if __name__ == "__main__":
    main()

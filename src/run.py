"""Batch entry point: iterate adapter URLs, scrape, persist to SQLite (append-only)."""

from __future__ import annotations

import argparse
import importlib
import logging
import sqlite3
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError

from src.compliance.robots import is_allowed
from src.compliance.sources_config import SourceConfig, load_sources
from src.db.store import (
    append_validation_failure,
    get_last_scraped_at,
    record_attempt,
    upsert_canonical,
)
from src.extract import fetch_via_firecrawl, validate_extracted
from src.safety.cost import CostBudget, CostGate
from src.safety.trace import span
from src.sources._http_base import KIND_FIRECRAWL, KIND_HTTP, fetch_via_http

if TYPE_CHECKING:
    from src.sources._base import SourceAdapter

logger = logging.getLogger(__name__)

DB_PATH = Path("data/scraped.db")


def _config_name(cfg: SourceConfig) -> str:
    """Derive source name: 'src/sources/docs_python_org.py' → 'docs_python_org'."""
    return Path(cfg.adapter).stem


def _load_adapter(source_name: str) -> SourceAdapter:
    module = importlib.import_module(f"src.sources.{source_name}")
    class_name = "".join(part.capitalize() for part in source_name.split("_")) + "Adapter"
    adapter_cls = getattr(module, class_name)
    return adapter_cls()  # type: ignore[no-any-return]


def _is_fresh(
    con: sqlite3.Connection,
    source: str,
    source_id: str,
    url: str,
    max_age_days: int,
    *,
    force: bool,
) -> bool:
    """Return True when the canonical record is younger than max_age_days and force is off."""
    if force:
        return False
    last_scraped = get_last_scraped_at(con, source, source_id)
    if last_scraped is None:
        return False
    age = datetime.now(UTC) - last_scraped
    if age > timedelta(days=max_age_days):
        return False
    logger.info(
        "skip-fresh: %s (source_id=%s, last_scraped=%s, age_days=%.2f, threshold_days=%d)",
        url,
        source_id,
        last_scraped.isoformat(),
        age.total_seconds() / 86400,
        max_age_days,
    )
    return True


def _fetch_for_adapter(
    adapter: SourceAdapter,
    url: str,
    adapter_kind: str,
    gate: CostGate,
    counts: dict[str, int],
    rate_limit_rps: float,  # NEW — applied only on HTTP path
) -> dict[str, object] | None:
    """Fetch raw payload dispatched by adapter kind; return None on handled error."""
    if adapter_kind == KIND_FIRECRAWL:
        gate.before_call(cost=5)  # may raise RuntimeError on circuit breaker
        try:
            return fetch_via_firecrawl(url, adapter.page_type)
        except (KeyError, ImportError, AttributeError, ModuleNotFoundError):
            # Config errors are NOT transient — fail loud, not circuit breaker quota.
            raise
        except Exception:  # actual transport/transient errors feed circuit breaker
            logger.exception("fetch failed for %s", url)
            gate.after_error()
            counts["errors"] += 1
            return None
    elif adapter_kind == KIND_HTTP:
        gate.before_http_call()  # may raise RuntimeError on cap / breaker
        try:
            return fetch_via_http(adapter, url, rate_limit_rps)  # type: ignore[arg-type]  # runtime dispatch via adapter_kind
        except (KeyError, ImportError, AttributeError, ModuleNotFoundError):
            # Config errors are NOT transient — fail loud, not circuit breaker quota.
            raise
        except Exception:  # transport / transient errors feed circuit breaker
            logger.exception("http fetch failed for %s", url)
            gate.after_error()
            counts["errors"] += 1
            return None
    else:
        raise ValueError(f"unknown adapter kind: {adapter_kind!r}")


def run(
    source: str,
    *,
    since: str | None = None,
    max_credits: int = 100,
    max_iterations: int = 200,
    max_http_calls: int = 200,
    max_age_days: int = 7,
    force: bool = False,
    db_path: Path = DB_PATH,
) -> dict[str, int]:
    """Run a batch. Returns summary counts."""
    configs = load_sources()
    config = next((c for c in configs if _config_name(c) == source), None)
    if config is None:
        raise ValueError(f"source {source!r} not found in sources.yaml")

    rate_limit_rps = config.rate_limit_rps  # NEW

    adapter = _load_adapter(source)
    gate = CostGate(
        CostBudget(
            max_credits_per_run=max_credits,
            max_iterations=max_iterations,
            max_http_calls_per_run=max_http_calls,
        )
    )
    counts = {
        "canonical": 0,
        "validation_failed": 0,
        "skipped_robots": 0,
        "errors": 0,
        "skipped_fresh": 0,
    }

    con = sqlite3.connect(db_path)
    root_span_id: str | None = None
    iterated_count = 0
    try:
        with span("batch", source=source) as root:
            root_span_id = root["span_id"]
            for i, url in enumerate(adapter.list_urls(since)):
                if i >= max_iterations:
                    break
                iterated_count += 1
                allowed, delay = is_allowed(url)
                if not allowed:
                    counts["skipped_robots"] += 1
                    continue

                source_id_for_check = adapter.parse_id(url)
                if _is_fresh(con, source, source_id_for_check, url, max_age_days, force=force):
                    counts["skipped_fresh"] += 1
                    continue

                if delay is not None:
                    # robots.txt crawl-delay (per-fetch, declared by source).
                    # This composes with the per-source rate-limit applied inside
                    # fetch_via_http (inter-fetch spacing from sources.yaml::rate_limit_rps):
                    # robots-delay → rate-limit → urlopen. Both layers may fire; the effective
                    # wait is the stricter of the two for any given pair of consecutive calls.
                    time.sleep(delay)
                adapter_kind = getattr(adapter, "kind", KIND_FIRECRAWL)
                with span("scrape", parent_id=root["span_id"], url=url, kind=adapter_kind) as s:
                    raw = _fetch_for_adapter(
                        adapter, url, adapter_kind, gate, counts, rate_limit_rps
                    )
                    if raw is None:
                        continue
                    source_id = adapter.parse_id(url)

                    # TODO #8 / ERRATA E-2: identifiers we own; Firecrawl LLM guesses them wrong.
                    raw["source"] = source
                    raw["source_id"] = source_id
                    raw["source_url"] = url

                    raw_id = record_attempt(con, source, source_id, url, raw, s["span_id"])
                    try:
                        instance = validate_extracted(raw, adapter.page_type)
                    except ValidationError as exc:
                        append_validation_failure(con, source, url, raw_id, str(exc))
                        gate.after_error()
                        counts["validation_failed"] += 1
                        con.commit()
                        continue
                    upsert_canonical(
                        con,
                        source,
                        source_id,
                        url,
                        instance.model_dump(mode="json"),
                        raw_id,
                    )
                    if adapter_kind == KIND_FIRECRAWL:
                        gate.after_success(cost=5)
                    else:
                        gate.after_http_success()
                    counts["canonical"] += 1
                    con.commit()
    finally:
        con.close()

    total = sum(counts.values())
    assert total == iterated_count, (
        f"counts mismatch: sum(counts)={total}, iterated_urls={iterated_count}, counts={counts}"
    )
    print(  # noqa: T201
        f"batch done: {counts}, credits_used={gate.credits_used}, root_span_id={root_span_id}"
    )
    return counts


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="src.run", description="Scraper batch entry point")
    parser.add_argument("--source", required=True)
    parser.add_argument("--since", default=None)
    parser.add_argument("--max-credits", type=int, default=100)
    parser.add_argument("--max-iterations", type=int, default=200)
    parser.add_argument(
        "--max-http-calls",
        type=int,
        default=200,
        help="Cap on HTTP fetches per run (parallel to --max-credits for HTTP-source adapters)",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=7,
        help="Skip URLs with canonical record younger than N days (default 7)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Disable skip-if-fresh; re-scrape all URLs regardless of age",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass  # python-dotenv is dev-only; env vars expected to be set in prod/CI
    args = _parse_args(argv)
    counts = run(
        args.source,
        since=args.since,
        max_credits=args.max_credits,
        max_iterations=args.max_iterations,
        max_http_calls=args.max_http_calls,
        max_age_days=args.max_age_days,
        force=args.force,
    )
    return 0 if counts["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

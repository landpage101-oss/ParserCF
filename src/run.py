"""Batch entry point: iterate adapter URLs, scrape, persist to SQLite (append-only)."""

from __future__ import annotations

import argparse
import importlib
import sqlite3
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError

from src.compliance.robots import is_allowed
from src.compliance.sources_config import SourceConfig, load_sources
from src.db.store import append_validation_failure, record_attempt, upsert_canonical
from src.extract import fetch_via_firecrawl, validate_extracted
from src.safety.cost import CostBudget, CostGate
from src.safety.trace import span

if TYPE_CHECKING:
    from src.sources._base import SourceAdapter

DB_PATH = Path("data/scraped.db")


def _config_name(cfg: SourceConfig) -> str:
    """Derive source name: 'src/sources/docs_python_org.py' → 'docs_python_org'."""
    return Path(cfg.adapter).stem


def _load_adapter(source_name: str) -> SourceAdapter:
    module = importlib.import_module(f"src.sources.{source_name}")
    class_name = "".join(part.capitalize() for part in source_name.split("_")) + "Adapter"
    adapter_cls = getattr(module, class_name)
    return adapter_cls()  # type: ignore[no-any-return]


def run(
    source: str,
    *,
    since: str | None = None,
    max_credits: int = 100,
    max_iterations: int = 200,
    db_path: Path = DB_PATH,
) -> dict[str, int]:
    """Run a batch. Returns summary counts."""
    configs = load_sources()
    config = next((c for c in configs if _config_name(c) == source), None)
    if config is None:
        raise ValueError(f"source {source!r} not found in sources.yaml")

    adapter = _load_adapter(source)
    gate = CostGate(CostBudget(max_credits_per_run=max_credits))
    counts = {"canonical": 0, "validation_failed": 0, "skipped_robots": 0, "errors": 0}

    con = sqlite3.connect(db_path)
    root_span_id: str | None = None
    try:
        with span("batch", source=source) as root:
            root_span_id = root["span_id"]
            for i, url in enumerate(adapter.list_urls(since)):
                if i >= max_iterations:
                    break
                allowed, delay = is_allowed(url)
                if not allowed:
                    counts["skipped_robots"] += 1
                    continue
                if delay is not None:
                    time.sleep(delay)
                with span("scrape", parent_id=root["span_id"], url=url) as s:
                    gate.before_call(cost=5)  # may raise RuntimeError on circuit breaker
                    try:
                        raw = fetch_via_firecrawl(url, adapter.page_type)
                    except (KeyError, ImportError, AttributeError, ModuleNotFoundError):
                        # Config errors are NOT transient — fail loud, not circuit breaker quota.
                        raise
                    except Exception:  # noqa: BLE001 — actual transport/transient errors feed circuit breaker
                        gate.after_error()
                        counts["errors"] += 1
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
                    gate.after_success(cost=5)
                    counts["canonical"] += 1
                    con.commit()
    finally:
        con.close()

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
    )
    return 0 if counts["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

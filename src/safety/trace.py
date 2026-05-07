import json
import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

TRACE_DIR = Path("data/traces")


@contextmanager
def span(
    name: str,
    parent_id: str | None = None,
    **attrs: Any,
) -> Generator[dict[str, Any], None, None]:
    span_id = uuid.uuid4().hex
    started = time.time()
    record: dict[str, Any] = {
        "span_id": span_id,
        "parent_id": parent_id,
        "name": name,
        "started": started,
        "attrs": attrs,
    }
    try:
        yield record
        record["status"] = "ok"
    except Exception as e:
        record["status"] = "error"
        record["error"] = repr(e)
        raise
    finally:
        record["duration_ms"] = int((time.time() - started) * 1000)
        TRACE_DIR.mkdir(parents=True, exist_ok=True)
        with (TRACE_DIR / f"{time.strftime('%Y%m%d')}.jsonl").open("a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_trace_for_batch(batch_id: str) -> list[dict[str, Any]]:
    """Читает все JSONL-записи за сегодня, фильтрует по batch_id из attrs."""
    today = time.strftime("%Y%m%d")
    path = TRACE_DIR / f"{today}.jsonl"
    if not path.exists():
        return []
    results: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record: dict[str, Any] = json.loads(line)
        if record.get("attrs", {}).get("batch_id") == batch_id:
            results.append(record)
    return results

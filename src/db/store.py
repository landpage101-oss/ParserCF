from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime

from src.safety.trace import span


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def record_attempt(
    con: sqlite3.Connection,
    source: str,
    source_id: str,
    url: str,
    raw_payload: dict,  # type: ignore[type-arg]
    trace_id: str,
) -> int:
    payload_str = json.dumps(raw_payload, ensure_ascii=False, sort_keys=True)
    content_hash = hashlib.sha256(payload_str.encode()).hexdigest()
    cur = con.execute(
        """
        INSERT INTO raw_content (source, source_id, url, content_hash,
                                 raw_payload, scraped_at, trace_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (source, source_id, url, content_hash, payload_str, _now_iso(), trace_id),
    )
    row_id: int = cur.lastrowid  # type: ignore[assignment]
    return row_id


def upsert_canonical(
    con: sqlite3.Connection,
    source: str,
    source_id: str,
    url: str,
    valid_payload: dict,  # type: ignore[type-arg]
    raw_id: int,
) -> None:
    prev = con.execute(
        "SELECT payload FROM canonical_records WHERE source = ? AND source_id = ?",
        (source, source_id),
    ).fetchone()
    if prev:
        old: dict = json.loads(prev[0])  # type: ignore[type-arg]
        for field in set(old) | set(valid_payload):
            if old.get(field) != valid_payload.get(field):
                con.execute(
                    """
                    INSERT INTO change_history
                        (source, source_id, field, old_value, new_value, changed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source,
                        source_id,
                        field,
                        json.dumps(old.get(field), ensure_ascii=False),
                        json.dumps(valid_payload.get(field), ensure_ascii=False),
                        _now_iso(),
                    ),
                )
    con.execute(
        """
        INSERT INTO canonical_records (source, source_id, url, payload,
                                       valid_from, raw_id)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(source, source_id) DO UPDATE SET
            url = excluded.url,
            payload = excluded.payload,
            valid_from = excluded.valid_from,
            raw_id = excluded.raw_id
        """,
        (source, source_id, url, json.dumps(valid_payload, ensure_ascii=False), _now_iso(), raw_id),
    )


def get_last_scraped_at(
    con: sqlite3.Connection,
    source: str,
    source_id: str,
) -> datetime | None:
    """Return scraped_at (tz-aware UTC) of the raw_content row backing the canonical
    record for (source, source_id), or None.

    Read-only. Freshness signal for run.py incremental refresh: scraped_at on
    raw_content reflects the actual fetch time. upsert_canonical overwrites
    raw_id on re-scrape, so the JOIN naturally returns the latest fetch.
    """
    row = con.execute(
        "SELECT r.scraped_at "
        "FROM canonical_records c "
        "JOIN raw_content r ON r.id = c.raw_id "
        "WHERE c.source = ? AND c.source_id = ? "
        "LIMIT 1",
        (source, source_id),
    ).fetchone()
    if row is None:
        return None
    dt = datetime.fromisoformat(row[0])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def append_validation_failure(
    con: sqlite3.Connection,
    source: str,
    url: str,
    raw_id: int,
    error: str,
) -> None:
    con.execute(
        """
        INSERT INTO validation_failed (source, url, raw_id, error, detected_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (source, url, raw_id, error, _now_iso()),
    )


_VALID_RESOLUTIONS: frozenset[str] = frozenset({"fixed", "discarded", "source_changed"})


def resolve_validation_failure(
    con: sqlite3.Connection,
    vf_id: int,
    *,
    resolution: str,
    reason: str,
) -> None:
    """Mark a validation_failed record as resolved.

    resolution: one of 'fixed', 'discarded', 'source_changed'
    reason: human-readable explanation — written to trace, not stored in DB
    """
    if resolution not in _VALID_RESOLUTIONS:
        raise ValueError(
            f"resolution must be one of {sorted(_VALID_RESOLUTIONS)}, got {resolution!r}"
        )
    row = con.execute("SELECT resolved_at FROM validation_failed WHERE id = ?", (vf_id,)).fetchone()
    if row is None:
        raise ValueError(f"validation_failed id={vf_id} not found")
    if row[0] is not None:
        raise ValueError(f"validation_failed id={vf_id} already resolved at {row[0]}")

    with span("resolve_vf", vf_id=vf_id, resolution=resolution, reason=reason):
        con.execute(
            "UPDATE validation_failed SET resolved_at = ?, resolution = ? WHERE id = ?",
            (_now_iso(), resolution, vf_id),
        )

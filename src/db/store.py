from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime


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

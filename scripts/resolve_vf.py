"""Resolve a validation_failed record by ID.

Usage:
    python scripts/resolve_vf.py --vf-id N \
        --resolution <fixed|discarded|source_changed> --reason "..."
    python scripts/resolve_vf.py --vf-id N --dry-run
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from src.db.store import resolve_validation_failure

DB_PATH = Path("data/scraped.db")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vf-id", required=True, type=int, metavar="N")
    parser.add_argument(
        "--resolution",
        choices=["fixed", "discarded", "source_changed"],
        help="resolution status (required unless --dry-run)",
    )
    parser.add_argument("--reason", default="", help="human-readable explanation")
    parser.add_argument("--dry-run", action="store_true", help="print record without applying")
    args = parser.parse_args()

    if not args.dry_run and args.resolution is None:
        print("error: --resolution is required unless --dry-run is set", file=sys.stderr)
        return 1

    if not DB_PATH.exists():
        print(f"db not found: {DB_PATH}", file=sys.stderr)
        return 1

    con = sqlite3.connect(str(DB_PATH))
    row = con.execute(
        "SELECT source, url, error, detected_at, resolved_at FROM validation_failed WHERE id = ?",
        (args.vf_id,),
    ).fetchone()

    if row is None:
        print(f"validation_failed id={args.vf_id} not found", file=sys.stderr)
        return 1

    source, url, error, detected_at, resolved_at = row

    if resolved_at is not None:
        print(
            f"validation_failed id={args.vf_id} already resolved at {resolved_at}",
            file=sys.stderr,
        )
        return 1

    resolution_display = args.resolution if not args.dry_run else "(dry-run)"
    print(f"vf_id:      {args.vf_id}")
    print(f"source:     {source}")
    print(f"url:        {url}")
    print(f"error:      {error}")
    print(f"detected:   {detected_at}")
    print(f"resolution: {resolution_display}")
    print(f"reason:     {args.reason}")

    if args.dry_run:
        return 0

    resolve_validation_failure(con, args.vf_id, resolution=args.resolution, reason=args.reason)
    con.commit()

    resolved_at_confirmed = con.execute(
        "SELECT resolved_at FROM validation_failed WHERE id = ?",
        (args.vf_id,),
    ).fetchone()[0]
    print(f"resolved_at: {resolved_at_confirmed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

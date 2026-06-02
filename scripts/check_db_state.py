"""Read-only diag: count canonical + unresolved validation_failed for a source.

Usage:
    python scripts/check_db_state.py --source developer_mozilla_org
    python scripts/check_db_state.py --source docs_python_org --show-ids
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path("data/scraped.db")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        required=True,
        help="canonical source name (e.g. developer_mozilla_org)",
    )
    parser.add_argument(
        "--show-ids",
        action="store_true",
        help="list source_id values",
    )
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"db not found: {DB_PATH}", file=sys.stderr)
        return 1

    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    c = con.cursor()
    canonical = c.execute(
        "SELECT COUNT(*) FROM canonical_records WHERE source = ?",
        (args.source,),
    ).fetchone()[0]
    unresolved_vf = c.execute(
        "SELECT COUNT(*) FROM validation_failed WHERE source = ? AND resolution IS NULL",
        (args.source,),
    ).fetchone()[0]
    print(f"source:        {args.source}")
    print(f"canonical:     {canonical}")
    print(f"unresolved vf: {unresolved_vf}")
    if args.show_ids:
        print("ids:")
        for (sid,) in c.execute(
            "SELECT source_id FROM canonical_records WHERE source = ? ORDER BY source_id",
            (args.source,),
        ):
            print(f"  {sid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

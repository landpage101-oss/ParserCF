# TODO: Incremental refresh via `since` parameter (#E-C)

## Context

`list_urls(since: str | None)` already accepts `since` in the Protocol
but all three adapters ignore it (# noqa: ARG002). For small seed lists
this is fine. Once seed coverage grows (via #E-A), re-scraping every
URL on each batch run wastes Firecrawl credits and adds noise to
`change_history`.

## What needs to happen

### 1. Protocol type upgrade (TODO #21)

`src/sources/_base.py::SourceAdapter.list_urls`:

```python
# current
def list_urls(self, since: str | None = None) -> Iterable[str]: ...

# target
from datetime import datetime
def list_urls(self, since: datetime | None = None) -> Iterable[str]: ...
```

Callers (`src/run.py`) pass `since` as a raw string today; update to
parse before passing:

```python
since_dt = datetime.fromisoformat(args.since) if args.since else None
adapter.list_urls(since_dt)
```

### 2. skip-if-fresh in `run.py` (recommended approach)

Add a guard in the batch loop — adapter-agnostic, one place to test:

```python
if since and source_id in canonical_ids_fresh_since:
    counts["skipped_fresh"] += 1
    continue
```

`canonical_ids_fresh_since` is a set queried once before the loop:
```sql
SELECT source_id FROM canonical_records
WHERE source = ? AND valid_from >= ?
```

This keeps adapters stateless; `change_history` still fires if content
actually changed on a forced re-scrape.

### 3. Adapter-level implementation (optional, later)

If some adapters have access to a publication date feed (RSS, sitemap
with lastmod), they can implement `since` directly to avoid fetching
known-old URLs at all. Anthropic news is a candidate once sitemap
coverage is confirmed.

## Prerequisites

- #E-A merged (more seeds make incremental refresh worthwhile)
- TODO #21 type upgrade (separate PR: one-liner in `_base.py` + run.py)

## Estimated size

2 PRs:
1. Type upgrade: ~10 lines + mypy fix
2. skip-if-fresh: ~25 lines in run.py + 2-3 tests

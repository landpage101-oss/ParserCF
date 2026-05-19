# ADR 0001: change_history noise — accept as audit cost

- **Status:** Accepted
- **Date:** 2026-05-19
- **Deciders:** Vitae (operator), architecture consultant
- **Supersedes:** —
- **Superseded by:** —

## Context

`src/db/store.py::upsert_canonical` writes one row to `change_history` for every
field whose value differs between the previously canonical payload and the new
payload. There is no dedupe layer and no threshold filter: any non-equal field
value produces an audit row.

The concern that motivated revisiting this design (carried as TODO #10 from
`HANDOFF_PHASE2.md`) was non-determinism in LLM-driven extraction. Firecrawl
JSON-mode runs an LLM over scraped content; repeated scrapes of an unchanged
source page can return payloads that differ at the byte level (whitespace
shifts, minor markdown reordering, equivalent code-block rephrasing) while
being semantically identical. Such trivial-diff rows would inflate
`change_history` without adding audit signal.

## Empirical baseline (as of 2026-05-19)

Aggregated `change_history` by `(source, source_id, field)`:

| source | source_id | field | count |
|---|---|---|---|
| docs_python_org | library/asyncio | body_md | 1 |
| docs_python_org | library/asyncio | code_block_count | 1 |
| docs_python_org | library/asyncio | section_path | 1 |
| docs_python_org | library/json | body_md | 1 |
| docs_python_org | library/json | code_block_count | 1 |
| docs_python_org | library/json | section_path | 1 |
| docs_python_org | library/json | source | 1 |
| docs_python_org | library/typing | body_md | 1 |
| docs_python_org | library/typing | code_block_count | 1 |
| docs_python_org | library/typing | section_path | 1 |
| docs_python_org | library/typing | source | 1 |
| docs_python_org | library/typing | title | 1 |

Total: 12 rows. All from the Phase 1 pilot/full-batch overlap on three
docs.python.org URLs. Each field changed exactly once — these capture real
deterministic differences between the pilot run and the full batch (the two
runs were separate Firecrawl calls with independently sampled LLM outputs),
not repeated-scrape LLM-noise.

No repeated batch on the same source has run yet, so the hypothetical LLM
noise has not materialized empirically.

## Decision

Accept current behaviour. Do not add dedupe or threshold logic to
`upsert_canonical`. `change_history` continues to record every field diff
verbatim.

This aligns with the project's append-only audit principle (ERRATA E-4):
ingestion writes raw observations; semantic analysis happens at read time.
Filtering inserts couples ingestion to interpretation, which the architecture
explicitly avoids.

## Alternatives considered

**A. Hash-skip in `upsert_canonical`.** Compute `sha256(old_payload_json)` vs
`sha256(new_payload_json)`; skip the whole upsert if equal. Cheap (one extra
hash), catches only byte-identical duplicates. Does not address LLM-noise,
which by definition produces byte-different payloads. Rejected as
disproportionate to the observed problem (zero byte-identical duplicates in
the current data).

**B. JSON-normalize compare.** Parse both payloads as JSON, normalize (sort
keys, strip whitespace), compare. Catches more duplicates than A. Risk:
loses legitimate diffs that happen to normalize away (e.g. trailing
whitespace in a code block is a real edit on some sources). Rejected:
upgrade is small but irreversible — we would no longer be able to
distinguish "no real change" from "change normalized away".

**C. Field-level semantic dedupe.** Per-field rules (e.g. for `body_md`,
strip whitespace and compare; for `code_block_count`, compare numerically).
Most accurate, also most complex. Each rule is a maintenance burden and a
potential false-negative source. Rejected on KISS grounds — only justified
if (B) proves insufficient.

**D. Accept as audit cost.** Chosen. No code change. The cost is
`change_history` table growth on repeated batches. The benefit is that
ingestion stays interpretation-free, and dedupe (if ever needed) can be
applied at read time by analysis tools that have full context.

## Consequences

- `change_history` will grow on each repeated batch even when source content
  is materially unchanged. Expected growth on the current two sources
  (docs.python.org + developer.mozilla.org) is bounded by their refresh
  cadence and the LLM noise floor; we will measure once the second MDN
  batch runs.
- Downstream consumers (`/investigate-failed`, future analytics) need to be
  aware that some `change_history` rows represent LLM-trivial diffs rather
  than real content changes. This is acceptable for the design-time HITL
  workflow where the operator is in the loop.
- No migration is needed. Existing 12 rows remain valid audit records.

## Triggers for revisit

This decision should be reconsidered if any of the following holds:

- Sustained growth above 50 `change_history` rows per month averaged over
  active sources, indicating the audit-trail signal-to-noise ratio is
  degrading.
- `/investigate-failed` runs (or other downstream tools) report being
  misled by trivial-diff rows — i.e. the noise hides real signal.
- Storage volume on `data/scraped.db` becomes an operational concern
  (loose threshold: `change_history` exceeding 10% of total DB size).

When any of these fires, re-open this ADR, evaluate alternatives B / C /
hash-skip against the then-current data, and supersede with ADR 0001-N.

## References

- `src/db/store.py::upsert_canonical` — the function under discussion.
- `src/db/schema.sql` — `change_history` table definition (append-only,
  no unique constraint on `(source, source_id, field)`).
- `HANDOFF_PHASE2.md` TODO #10 — original concern.
- `HANDOFF_PHASE2_MIDPOINT.md` TODO #10 — empirical observation that no
  noise has yet materialized.
- ERRATA E-4 (in `ERRATA.md`) — append-only audit principle.

# First batch — docs.python.org — 2026-05-13

## Run command
python -m src.run --source docs_python_org --max-credits 50

## DB state — baseline and deltas

| Table | Pre-batch | Post-batch | Δ |
|---|---|---|---|
| raw_content | 3 | 10 | +7 |
| canonical_records | 3 | 7 | +4 |
| validation_failed | 0 | 0 | 0 |
| change_history | 0 | 12 | +12 |

Pre-batch state reflects an earlier 3-URL pilot run. The full batch added 7 raw rows (ids 4–10). Upsert keyed by `(source, source_id)` replaced three pre-existing canonical entries with fresh `raw_id`s 4–6; the pilot raws (ids 1–3) are now archival — no live FK from `canonical_records`, but retained intact as part of the append-only audit trail.

## Post-run summary

| Metric | Value |
|---|---|
| canonical | 7 |
| validation_failed | 0 |
| skipped_robots | 0 |
| errors | 0 |
| credits_used | 35 (of 50 budget) |
| root_span_id | `3d5d33c724a843a19c9d8b5dd7e9396e` |
| wall_clock | 266.8 s (~38 s/URL) |

## URLs processed

| # | source_id | raw_id | URL | fate |
|---|---|---|---|---|
| 1 | library/json | 4 | https://docs.python.org/3/library/json.html | canonical |
| 2 | library/typing | 5 | https://docs.python.org/3/library/typing.html | canonical |
| 3 | library/asyncio | 6 | https://docs.python.org/3/library/asyncio.html | canonical |
| 4 | library/sqlite3 | 7 | https://docs.python.org/3/library/sqlite3.html | canonical |
| 5 | library/re | 8 | https://docs.python.org/3/library/re.html | canonical |
| 6 | library/pathlib | 9 | https://docs.python.org/3/library/pathlib.html | canonical |
| 7 | library/dataclasses | 10 | https://docs.python.org/3/library/dataclasses.html | canonical |

Archived (pilot-only, no current FK): raw_id 1 (json), 2 (typing), 3 (asyncio).

## Spot-check — canonical_records[library/json]
source:     docs_python_org
source_id:  library/json
url:        https://docs.python.org/3/library/json.html
raw_id:     4
valid_from: 2026-05-13T19:00:12.402721+00:00
payload:
source:        "Python JSON Encoder and Decoder Documentation"   ← see Finding #1
source_url:    https://docs.python.org/3/library/json.html
source_id:     "json"                                             ← see Finding #1
title:         "json — JSON encoder and decoder"
section_path:  ["json", "json encoder and decoder"]
body_md:       (~full page; opens "## JSON (JavaScript Object Notation)\n\nJSON, ...")

## Findings

**1. `payload.source` and `payload.source_id` are filled by Firecrawl LLM, not programmatically.**

The Pydantic fields `source` and `source_id` were added in ERRATA E-2 to identify the adapter (e.g. `source="docs_python_org"`, `source_id="library/json"`). In the local-extraction path (Path A, Stage 8) both are set programmatically as kwargs. In the production path, the schema is sent to Firecrawl's JSON-mode and the LLM treats these as content to extract — here it produced `payload.source="Python JSON Encoder and Decoder Documentation"` (from page meta) and `payload.source_id="json"` (URL leaf). Both disagreed with the correctly-filled DB table columns. Pydantic did not reject (valid strings), but the semantics were wrong. See TODO #8.

**2. `section_path` is correctly populated by Firecrawl extraction.**

`["json", "json encoder and decoder"]` — non-empty, matches the page breadcrumb. HANDOFF TODO #7 (concern that the `<nav class="breadcrumb">` heuristic in `_parse_docs` might miss live HTML) does not apply: the production path uses Firecrawl JSON-mode, not `_parse_docs`. TODO #7 from HANDOFF is not materialized on this batch.

**3. `change_history` recorded 12 rows on second batch.**

Three URLs (json, typing, asyncio) were scraped in both the pilot and the full batch. Upsert detected differences and recorded 12 change rows (~4 changed fields × 3 URLs). The most plausible diffs are `valid_from` (always changes) and `body_md` (LLM extraction is non-deterministic). `change_history` will be noisy in steady-state re-scrapes of unchanged pages. See TODO #10.

**4. Throughput: ~38 s/URL on docs.python.org.**

Firecrawl JSON-mode + LLM extraction takes ~30–40 s per page on docs.python.org. A 100-URL batch would take ~1 hour and consume ~500 credits — the full free-tier daily quota. Future batch sizing must account for both wall-clock and credit budget.

**5. End-to-end pipeline confirmed functional.**

CLI → load_sources → adapter → is_allowed → fetch_via_firecrawl → sanitize → record_attempt → validate_extracted → upsert_canonical → trace, all six layers, exercised on live data. No errors, no validation failures, no robots refusals, no credit overruns.

## TODO / next iteration

- **TODO #8 — [RESOLVED 2026-05-14, commit `7917a33`].** `run.py` now overrides `raw["source"]`, `raw["source_id"]`, `raw["source_url"]` with adapter-provided values before `validate_extracted`. Applies Path A symmetrically to the production path. Verified via `tests/test_run_smoke.py::test_run_overrides_source_metadata`.
- **TODO #9 (new).** `trace.py` writes to `data/traces/<date>.jsonl` unconditionally; smoke-tests pollute the same file. Parametrize via env var or pytest fixture in Phase 2.
- **TODO #10 (new).** `change_history` records noise from non-deterministic LLM output. Decide whether to dedupe trivially-equal payload diffs before logging.
- **HANDOFF TODO #1.** `reject_placeholder` markers in Article/Product/ReferenceEntry still use flat `"404"`. Not exercised in this batch (all 7 URLs are DocsPage). Still pending for Phase 2.
- **HANDOFF TODO #4.** `FIRECRAWL_API_KEY` not yet added as GitHub Secret; `eval-live.yml` fails on manual dispatch until added.

## Conclusion

Stage 11b acceptance met: `canonical ≥ 5` (got 7), `validation_failed = 0`, `credits_used ≤ 50` (used 35). Pipeline is end-to-end functional on `docs.python.org`. Two new TODOs surfaced (#9, #10); Finding #1 was resolved post-batch as TODO #8.

---

*Report committed retroactively after Stage 12. Batch executed 2026-05-13; TODO #8 (Finding #1) resolved 2026-05-14 in commit `7917a33` before this report landed.*

# HANDOFF — agent-parser, Phase 5: incremental refresh + placeholder validator fix + MDN full coverage

## Дата

2026-06-04

## TL;DR

Эта сессия закрыла Phase 4 TODO #1 (добор 13 MDN seeds) и #2 (incremental refresh),
а также vf #4 (`Web/HTTP/Status/404`, schema-too-strict ложно-положительный). MDN
теперь имеет **полное покрытие seed-листа** — 34 canonical. TODO #3 (timeout-class
для MDN) переклассифицирован из «accepted infra-flake» в «monitor»: те же 3 URL,
которые timeout'нули в первом батче, прошли в retry без вмешательства, что
подтверждает transient-характер (Firecrawl/network variance, не свойство URL).
Suммарный coverage по трём источникам — **80 canonical** (было 67), 0 unresolved
`validation_failed`.

## Что merged в этой сессии

| Branch                                       | Title                                                                              |
|----------------------------------------------|------------------------------------------------------------------------------------|
| `feat/store-canonical-captured-at-helper`    | `feat(db): add get_last_scraped_at helper for incremental refresh`                 |
| `feat/run-incremental-refresh`               | `feat(run): incremental refresh — skip-if-fresh with --max-age-days and --force`   |
| `fix/schemas-placeholder-content-aware`      | `fix(schemas): content-aware placeholder check (closes vf #4 false positive)`      |
| `chore` (housekeeping)                       | `chore: archive phase4 handoff`                                                    |

Три feature/fix PR + один housekeeping chore. Каждый — отдельная ветка, один коммит,
squash- или rebase-and-merge.

## Детали по каждому PR

### `feat/store-canonical-captured-at-helper` — preliminary helper (operator-manual)

Helper `get_last_scraped_at(con, source, source_id) -> datetime | None` в
`src/db/store.py`. Read-only SELECT с JOIN `canonical_records c → raw_content r ON
r.id = c.raw_id`, возвращает tz-aware `datetime`. Defensive `LIMIT 1` несмотря на
гарантированную уникальность `PRIMARY KEY (source, source_id)`. Defensive `if
dt.tzinfo is None: replace(tzinfo=UTC)` для legacy/external данных (на горячем пути
no-op — `_now_iso()` пишет ISO с `+00:00`).

Оператор написал руками поскольку `src/db/` — CODEOWNERS. +3 unit-тестов
(`returns_none_for_unknown`, `returns_tz_aware_datetime`, `reflects_re_scrape`).

### `feat/run-incremental-refresh` — skip-if-fresh logic (Claude Code)

В `src/run.py` добавлены:
- CLI flags `--max-age-days N` (default 7) и `--force`.
- Helper `_is_fresh(con, source, source_id, url, max_age_days, *, force)` — force
  short-circuit + `get_last_scraped_at` lookup + age check + `logger.info` on skip.
  Вынесен из `run()` для удержания C901=10 (на ruff-лимите).
- В counts dict добавлен ключ `"skipped_fresh"`.
- Skip-fresh ветка размещена **после** `is_allowed`-проверки (compliance > optimization)
  и **до** `time.sleep(delay)` (не спим перед skip — fetch не делаем).
- Invariant: `assert sum(counts.values()) == iterated_count` после finally. Asserts
  допустимы здесь — ruff S101 не включён для `src/`, +1 branch уложился бы в C901=11
  (над лимитом), а инвариант — sanity (нарушение = баг кода, не данных).

+5 unit-тестов (`skips_fresh_url`, `processes_stale_url`, `processes_when_no_canonical`,
`force_flag_bypasses_skip_fresh`, `invariant_holds_across_buckets`). Тестовый
`_seed_canonical` helper — прямой INSERT в `raw_content` + `canonical_records` с
контролируемым `scraped_at`, обходит `_now_iso()` для предсказуемости.

### `fix/schemas-placeholder-content-aware` — content-aware placeholder check (Claude Code)

Корневая причина vf #4: `reject_placeholder` в четырёх схемах (`docs`, `article`,
`reference`, `product`) делал substring match на лоуэркейсе тела против фиксированного
marker-set'а. Любая страница, **документирующая** error-state-тему (HTTP 404, anti-bot,
captcha) ложно-positively матчила маркер.

Фикс — DRY-рефактор в shared module `src/schemas/_validators.py` с двухуровневой
логикой:

- **Hard markers** (`{"lorem ipsum"}`) — reject at any length (никогда не legitimate
  content).
- **Soft markers** (`{"page not found", "access denied", "404 not found",
  "403 forbidden", "are you a robot"}`) — reject **только** если `len(text) < 500`.
  Real placeholder/anti-bot/error pages — typically <500 chars; long content,
  обсуждающее эти темы — legitimate.

Threshold `500` — золотая середина: vf #4 body было 4542 chars (не отверг), существующие
`test_404_not_found_still_rejected` имели body ~80 chars (по-прежнему отвергает).

Все 4 схемы заменили inline marker sets на вызов `detect_placeholder_marker()`,
сохранив field-specific сообщения (`body` / `definition` / `description`).
`Product.reject_placeholder` сохранил `if v is None: return v` guard для Optional поля.

+8 helper-тестов (oба tier'а, length boundary, case-insensitivity, edge cases) +
4 регрессионных теста в `tests/schemas/test_{docs,article,reference,product}.py`
(`test_legitimate_long_content_with_marker_accepted`). Существующие keepers
(`test_placeholder_rejected`, `test_legitimate_404_mention_accepted`,
`test_404_not_found_still_rejected`) — без изменений, прошли как есть.

### `chore: archive phase4 handoff`

Housekeeping-коммит оператора: закрытие фантомного `deleted: HANDOFF_PHASE3_COMPLETE.md`
в working tree, который висел при ребейзе из Phase 4. Отдельный коммит, не примешан к
feature-веткам.

## Production batch результаты — MDN

### Batch 1 (`9eb4520263b34b66998291849da8ff12`, 07:31 UTC)

Первое использование incremental refresh после merge'а `feat/run-incremental-refresh`.

| Bucket | Count |
|---|---|
| skipped_fresh | 20 |
| canonical | 10 |
| validation_failed | 1 |
| errors (transport) | 3 |
| invariant total | 34 |

credits_used=50, не упёрся в CostGate (cap=100).

- Skipped 20 (а не ожидаемые 21) из-за parse_id format inconsistency на одной из трёх
  старых CSS-seed'ов (Phase 4 handoff упоминал «несогласованность допустима, нормализация
  — отдельный PR»). См. open TODO ниже.
- vf #1 (id=4 в DB): `Web/HTTP/Status/404`, error `body looks like placeholder/error:
  'page not found'`. Корень — schema-too-strict (см. fix-PR выше).
- 3 transport timeouts: `Promise`, `Fetch_API/Using_Fetch`, `Headers/Cache-Control`. Все
  ~120938-120634 ms duration — характерный fingerprint Firecrawl request timeout.
  Прочитано из trace'а `data/traces/20260604.jsonl`.

### Batch 2 (`a476f5a61ed641e7aa51d031b27b74e2`, после merge fix-PR)

Re-scrape: 4 ранее-неуспешных URL автоматически попадают в attempted (нет canonical
→ `_is_fresh` пропускает).

| Bucket | Count |
|---|---|
| skipped_fresh | 30 |
| canonical | 4 |
| validation_failed | 0 |
| errors (transport) | 0 |
| invariant total | 34 |

credits_used=20. Все 4 — успех:

- `Web/HTTP/Status/404`: validate проходит, +1 canonical.
- `Promise`, `Fetch_API/Using_Fetch`, `Headers/Cache-Control`: scrape прошёл за нормальное
  время. Подтверждает transient-характер вчерашних timeouts.

После закрытия vf #4 через `resolve_validation_failure(con, vf_id=4, resolution='fixed',
reason='schema relaxed placeholder check via PR fix/schemas-placeholder-content-aware; '
're-scrape on batch a476f5a6 wrote canonical')`.

## Текущее состояние репо

DB (`data/scraped.db`, gitignored):

- `developer_mozilla_org`: **34 canonical**, 0 unresolved vf — **полное покрытие
  seed-листа** (Phase 4 цель)
- `docs_python_org`: **27 canonical**, 0 unresolved vf
- `anthropic_news`: **19 canonical**, 0 unresolved vf
- **TOTAL: 80 canonical**, 0 unresolved validation_failed

`config/sources.yaml`: без изменений (3 источника).

Tests: **155 total** (130 unit + 25 eval) на `main`, ruff + mypy --strict чистые.

## Открытые TODO

1. **CSS source_id format normalization (Phase 4 / Phase 5 разделение).** Три исходных
   CSS-seed'а используют OLD-формат пути (`Web/CSS/Reference/Properties/<prop>`), новые
   семь — modern (`Web/CSS/<prop>`). Result в batch 1: один URL не skip'нулся, попал в
   attempted, UPSERT'нулся снова — отсюда «20 skipped вместо 21». Не блокер, но
   формальный TODO. Закрытие — один из:
   - Нормализовать `parse_id` под единый формат и мигрировать OLD-canonical row'ы
     (требует data-migration PR).
   - Принять как permanent inconsistency и снять упоминание в Phase 4 handoff (no-op).

2. **TODO #3 (MDN timeout-class) — переход в `monitor`.** Тот же URL-set timeout'нул в
   batch 1 (3 шт., 21% от 14 attempted) и прошёл в batch 2 (0 timeouts). Это
   transient, не systematic. Порог эскалации (>1/3 запусков подряд) не нарушен.
   Сохранить под наблюдением: если в следующих 2-3 MDN runs >1/3 — эскалация
   `wait_for=1500` или `timeout` поднятие в `extract.py`.

3. **TODO #4 (408 retry policy)** — открыт с Phase 3, систематики пока нет.

4. **TODO #5 (CRLF noise на Windows)** — лечится у оператора одной командой
   `git config --global core.autocrlf true`. Альтернатива — централизованный
   `.gitattributes` с `* text=auto eol=lf` (отдельный PR, не сделано).

5. **`resolve_vf_*.py` script-scaffolding.** В Phase 5 использовали разовый
   `scripts/resolve_vf4.py`. Если такие резолюции станут регулярными — обобщить в
   `scripts/resolve_vf.py --vf-id N --resolution <fixed|discarded|source_changed>
   --reason "..."`. Сейчас не блокер, но pattern проявляется.

## Заметки для следующей сессии

- Run-time агентские роли неизменны: `/investigate-failed`, `/onboard-source`, `/query`.
- **Incremental refresh теперь стандарт.** `python -m src.run --source <name>` с
  default `--max-age-days=7` пропускает свежие canonicals. Bulk refresh —
  `--force`. Partial-window — `--max-age-days N`.
- **Placeholder validator теперь content-aware.** Длинный контент с упоминанием
  error-state-тем (HTTP 4xx/5xx, anti-bot, captcha) — legitimate. Если новый
  адаптер для error-docs сайта будет нужен — никаких подкручиваний валидатора, всё
  работает.
- **Two-PR workflow для `src/db/` helper'ов** установлен: оператор руками пишет helper
  в `store.py` (CODEOWNERS-path), затем Claude Code в отдельной ветке вызывает его.
  Никаких `/update-config` обходов.
- Скрипт `python scripts/check_db_state.py --source <name>` — быстрая read-only
  pre-flight / post-flight sanity для любого источника. Используй перед paid run'ом.

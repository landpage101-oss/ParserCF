# HANDOFF — agent-parser, Phase 3: all TODO #A–#E closed

## Дата

2026-05-31

## TL;DR

Эта сессия закрыла все пять открытых TODO из `HANDOFF_PHASE2_PR5_COMPLETE.md`
(#B, #A, #C, #D, #E), прогнала production batch'и на `anthropic_news` (19/19) и
`docs_python_org` (27/27), и довела суммарный coverage до **54 canonical** по двум
источникам (MDN — 8, без изменений в этой сессии).

## Что merged в этой сессии

| Commit    | Message                                                                          | TODO  |
|-----------|----------------------------------------------------------------------------------|-------|
| `4a67fd1` | `fix(run): log transport exceptions instead of silently swallowing`              | #B    |
| `e096ad9` | `fix(extract): add wait_for=1500 ms to prevent JS hydration race on Anthropic CDN` | #A  |
| `be7aa1b` | `feat(db): add resolve_validation_failure() to store API`                        | #C    |
| `ad4df82` | `fix(schemas): add author field description to steer LLM away from org attribution` | #D |
| `d8f8f76` | `feat(sources): expand anthropic_news seeds from 8 to 19 URLs`                  | #E-A  |
| `47f7106` | `feat(sources): expand docs_python_org seeds from 7 to 27 URLs`                 | —     |

История линейная, все PR'ы — отдельная ветка, один коммит, rebase-and-merge.

## Детали по каждому TODO

### #B — logger.exception в run.py

`src/run.py` строка 82: `except Exception` молча глотал traceback.
Добавлен `import logging`, `logger = logging.getLogger(__name__)`,
`logger.exception("fetch failed for %s", url)`. `# noqa: BLE001` убран — ruff
больше не флагит bare except когда исключение логируется явно.
Тест: `test_run_transport_error_is_logged` (caplog, ERROR level). Baseline 129 → 130.

### #A — root-cause core-views-on-ai-safety flake

Investigation script `scripts/investigate_core_views.py` — 2 серии по 5 runs (10
total attempts). Выявлено два независимых бага:

1. **Truncated content** — CDN возвращал JS-stub до hydration. Fix: `wait_for=1500`.
2. **408 timeouts** — биmodal pattern при 31s и 62s (1× и 2× SDK retry ceiling).
   Оставлен как accepted flake — logger.exception + circuit breaker уже обрабатывают.
   Увеличение timeout не поможет (SDK internal ceiling ~120s независимо от нашего параметра).

После fix: title truncation устранён (полный тайтл на всех successful runs),
body_len стабилен ~12–39k. 408 остаётся intermittent (~1/5 runs) — инфраструктурный
флейк Firecrawl/Anthropic CDN. Закрыт как «root-cause confirmed, residual flake accepted».

### #C — resolve_validation_failure() API

`src/db/store.py`: новая функция `resolve_validation_failure(con, vf_id, *, resolution, reason)`.
Валидирует `resolution` по frozenset `{fixed, discarded, source_changed}`, защищает
от двойного резолва и несуществующего ID. UPDATE в DB + `span("resolve_vf", ...)` в trace.
`reason` идёт только в trace span, не в DB (schema не менялась).
Экспортирована через `src/db/__init__.__all__`. 5 unit-тестов. Baseline +5.

### #D — author field description

`src/schemas/article.py`: `author: str | None = None` → `Field(default=None, description="Real human author byline only; organisation-level attribution -> None")`.
Description идёт в `model_json_schema()` → Firecrawl LLM.
Паттерн тот же что и `language` fix (PR `69d689b`). Normalizer не добавлен —
нет замкнутого множества плохих значений. ASCII `->` вместо Unicode `→` (избегаем RUF003).

### #E — расширение coverage

**E-A (anthropic_news):** `scripts/discover_anthropic_seeds.py` — discovery через
`firecrawl.map()` (v4 SDK: не `map_url`, result items имеют `.url` attr).
80 article URLs обнаружено; 11 добавлено (model releases, safety policy, technical
research, ecosystem, usage research). 76 пропущено (press releases, региональные
анонсы — низкая diversity). Seeds: 8 → 19. Batch: **19/19, 0 errors, 95 credits**.

**E-C (incremental refresh):** задокументировано как отдельный ticket в
`docs/tickets/TODO_incremental_refresh.md`. Рекомендованный подход: skip-if-fresh
в `run.py` (adapter-agnostic), не в адаптерах. Prerequisites: #E-A merged + TODO #21
type upgrade (`since: str → datetime`). Estimated: 2 PR'а ~35 lines + тесты.

**docs_python_org:** 20 новых seeds вручную (без map — PSF сайт статичный, map
избыточен). Категории: concurrency, data structures/functional, file/os,
serialization/config, date/numeric, introspection/testing. Seeds: 7 → 27.
Batch: **27/27, 0 errors, 135 credits**.

## Текущее состояние репо

`main` HEAD: **`47f7106`** (`feat(sources): expand docs_python_org seeds from 7 to 27 URLs`)

`config/sources.yaml`: **3 источника** — `docs.python.org`, `developer.mozilla.org`,
`www.anthropic.com`. Без изменений в этой сессии.

`data/scraped.db` (gitignored):
- `anthropic_news`: **19 canonical**, 0 unresolved vf
- `docs_python_org`: **27 canonical**, 0 unresolved vf
- `developer_mozilla_org`: **8 canonical**, 0 unresolved vf (не трогали в этой сессии)
- TOTAL: **54 canonical**

Тестовый baseline: **~140 unit** (точная цифра — `pytest tests/ --co -q | tail -3`),
**25 eval**. ruff, mypy --strict, pre-commit — чисто на `main`.

`scripts/`: добавлены `discover_anthropic_seeds.py` (reusable, v4 SDK-compatible)
и `investigate_core_views.py` (investigation artefact, оставлен для истории).

`docs/tickets/`: добавлен `TODO_incremental_refresh.md`.

## Открытые TODO

Из `HANDOFF_PHASE2_PR5_COMPLETE.md` **всё закрыто** (#B, #A, #C, #D, #E).

**Новые открытые:**

1. **incremental refresh** (`docs/tickets/TODO_incremental_refresh.md`) — skip-if-fresh
   в `run.py` + TODO #21 type upgrade. Актуализируется когда seed-листы станут большими.

2. **MDN coverage expansion** — `developer_mozilla_org` остаётся на 8 seeds.
   Можно адаптировать `discover_anthropic_seeds.py` под MDN или добавить seeds вручную
   (CSS, JS, HTTP reference страницы). Не блокер.

3. **408 retry policy** — если `core-views` будет падать в production batch'ах
   систематически (>1/3 прогонов), добавить exponential backoff поверх 408 в
   `src/safety/cost.py`. Сейчас: logger.exception + circuit breaker достаточно.

4. **_normalise_author** — если после D в следующих batch'ах LLM всё ещё возвращает
   org-level author, добавить validator в `src/schemas/article.py` (по аналогии с
   `_normalise_language`).

## Lessons этой сессии

1. **Windows mount truncates large file writes via Edit tool.** Edit и Write tools
   обрезают файлы на Windows NTFS mount при записи. Workaround: `cat > file << 'EOF'`
   через bash. Применялось для `article.py`, `test_run_smoke.py`, `anthropic_news.py`.

2. **git index.lock не удаляется из sandbox.** При corrupted index в sandbox нельзя
   делать `rm .git/index.lock` — нет прав. Все git-операции (branch, commit, push)
   выполняются пользователем локально; Claude готовит файлы + даёт команды.

3. **Firecrawl SDK v4: map() не map_url(), result.links → list[LinkResult] с .url.**
   Поймано при написании `discover_anthropic_seeds.py`. SDK методы нужно проверять
   по `inspect` или source, не полагаться на training data.

4. **wait_for=1500 решает JS hydration race, не 408.** Два независимых бага
   на одном URL: truncation (fix: wait_for) и timeout (accepted flake).
   Важно не смешивать диагнозы.

# HANDOFF — agent-parser, Phase 8: HTTP foundation + first HTTP source (dummyjson_com)

## Дата

2026-06-07

## TL;DR

Сессия закрыла TODO #8 в части foundation + первого реального HTTP-источника. Добавлены HTTP-bucket в CostGate (PR1a), `_http_base.py` Protocol + `fetch_via_http` + `run.py` dispatch (PR1b), адаптер `dummyjson_com` + sources.yaml entry + Decimal→float hotfix (PR2 + fixup + PR2-hotfix). DB выросла с 80 → **96 canonical** (Phase 7 завершила на 86; +10 от dummyjson). Тестовый baseline 163 → **183**. Открытых `validation_failed` нет.

`jovianarchive.com` **окончательно отклонён** по ToS (явный запрет «automated data collection... database construction»). Phase 7 backlog'ил его в ожидании готового `_http_base`, но ToS-блокер не зависит от технологии.

## Что сделано в этой сессии

| Артефакт | Статус |
|---|---|
| `src/safety/cost.py` HTTP-bucket helpers + `tests/test_cost_http.py` (4 теста) | merged PR1a (`feat/cost-http-bucket-helper`, operator manual) |
| `reports/specs/2026-06-05-http-base-adapter-pr1.md` | merged PR1a |
| `src/sources/_http_base.py` (Protocol + `fetch_via_http` + константы) | merged PR1b (`feat/http-base-adapter-skeleton`) |
| `src/run.py` dispatch + `_fetch_for_adapter` helper | merged PR1b |
| `tests/sources/test_http_base.py` (6 тестов) + `tests/test_run_dispatch.py` (2 теста) | merged PR1b |
| `src/sources/dummyjson_com.py` (DummyjsonComAdapter) | merged PR2 (`feat/dummyjson-com-source`) |
| `tests/sources/test_dummyjson_com.py` (7 → 8 после hotfix) | merged PR2 + PR2-hotfix |
| `src/run.py` `--max-http-calls` flag + `max_iterations` bug fix | merged PR2 |
| `reports/specs/2026-06-07-dummyjson-com-pr2.md` | merged PR2 |
| `config/sources.yaml` dummyjson entry | merged fixup PR (`chore/dummyjson-com-allow-list`, operator manual) |
| Decimal→float hotfix в адаптере + integration lock-in test | merged PR2-hotfix (`fix/dummyjson-price-keep-float-for-json-audit`) |
| Первый paid HTTP-batch | done — `{canonical: 10, vf: 0, errors: 0}`, credits_used=0, root_span_id `e101b7da7e664a33ad2e0b0dbe385130` |

## Архитектурный сдвиг: HTTP-источники

### Новый Protocol — `HttpSourceAdapter`

`src/sources/_http_base.py::HttpSourceAdapter` — отдельный Protocol от существующего `SourceAdapter` в `_base.py`. Контракт:

- `kind: ClassVar[str]` (MUST be `KIND_HTTP`)
- `domain: str`, `name: str`, `page_type: str`
- `list_urls(since) -> Iterable[str]` — pagination/discovery скрыты здесь
- `parse_id(url) -> str`
- `parse_response(response_json, url) -> dict[str, object]` — JSON-shape → схема-совместимый dict

Один URL → один HTTP GET → один parsed payload → один canonical-record. Pagination — внутри `list_urls`, не в fetch.

### Dispatch в `run.py`

`getattr(adapter, "kind", KIND_FIRECRAWL)` — default Firecrawl для четырёх существующих адаптеров (без атрибута `kind`). HTTP-адаптеры явно ставят `kind = KIND_HTTP`. Helper `_fetch_for_adapter(adapter, url, adapter_kind, gate, counts) -> dict | None` инкапсулирует обе ветки симметрично, возвращает `None` на handled (logged + counted) error. Span получает атрибут `kind=adapter_kind` для traceability.

### Cost модель

`CostBudget.max_http_calls_per_run: int = 200` параллельно `max_credits_per_run`. Шкалы независимы (HTTP-вызовы и Firecrawl-кредиты — разные порядки величин). `CostGate.before_http_call()` / `after_http_success()` симметричны Firecrawl-методам. `after_error()` общий, circuit breaker (3 consecutive errors) делится между двумя путями.

### CLI flag `--max-http-calls`

В `run.py` добавлен flag (default 200). HTTP-вызовы практически бесплатны, но cap остаётся safety net.

### Bug fix: `max_iterations` теперь реально пробрасывается

Pre-Phase-8 код `gate = CostGate(CostBudget(max_credits_per_run=max_credits))` молча игнорировал `max_iterations` параметр (всегда default 50). CLI flag `--max-iterations` существовал, но не применялся. PR2 явно пробрасывает все три cap'а:

```python
gate = CostGate(
    CostBudget(
        max_credits_per_run=max_credits,
        max_iterations=max_iterations,        # FIX
        max_http_calls_per_run=max_http_calls, # NEW
    )
)
```

Для существующих Firecrawl-источников эффект только при явном `--max-iterations N` или вызове `run(max_iterations=N)` (default 200 идентичен прежнему bot behaviour для всех seed-листов ≤200 URL).

## Новый источник: `dummyjson_com`

- **Домен:** `dummyjson.com`
- **page_type:** `product`
- **kind:** `http` (первый HTTP-источник в проекте)
- **Seeds:** 10 фиксированных URL'ов `https://dummyjson.com/products/{1..10}`
- **robots.txt:** wildcard `User-agent: *` → `Allow: /`. Наш UA `agent-parser/1.0` не среди named-disallow ботов (ClaudeBot, GPTBot, Bytespider, CCBot, Amazonbot, Applebot-Extended, Google-Extended, meta-externalagent). `Disallow: /auth/` respected.
- **Content-Signal:** `search=yes, ai-train=no` — наш use case (analytical catalog) respect'ит оба сигнала; мы не training.
- **Legal basis:** Public testing sandbox REST API (self-description «Free Fake REST API for Placeholder JSON Data»), open-source community project (github.com/Ovi/DummyJSON), fake/placeholder data без proprietary content. No explicit ToS page — open-source community модус.
- **Первый batch:** 10/10 canonical, 0 vf, 0 credits, root_span_id `e101b7da7e664a33ad2e0b0dbe385130`.

### `api_available: true` — впервые

Четыре существующих источника имеют `api_available: false` (Firecrawl-scrape). dummyjson — первый с `api_available: true` (HTTP-adapter direct). Семантика поля по факту: «у источника есть публичный API, и мы его используем напрямую через `_http_base.py`».

### Decimal→float hotfix

PR2 main spec требовала `Decimal(str(price_raw))` в `parse_response` — идея была сохранить precision. Первый paid batch упал на первом fetch'е: `record_attempt` пишет `raw_payload` через `json.dumps` ДО Pydantic-валидации, Python json не сериализует Decimal — TypeError. Адаптер переписан на float pass-through; Pydantic schema-validator конвертит float→Decimal на стадии `validate_extracted` (внутренне применяет `Decimal(str(value))`, precision сохраняется). Symmetric с Firecrawl flow, где LLM возвращает float и conversion тоже в Pydantic. Lesson #22 (см. ниже).

DB была clean после crash (транзакция откатилась на `con.close()` без `con.commit()`), re-run после hotfix дал 10/0/0 с первого захода.

## Отклонённые онбординги (Phase 8)

### jovianarchive.com — окончательный отказ

Phase 7 backlog'ил как кандидата для HTTP-адаптера. ToS-check этой сессии нашёл прямые запреты:

> «users are prohibited from engaging in any systematic or automated data collection activities on or in relation to the website without the Company's express written consent»

> «no portion of the Software... use such content to construct any kind of database... without the explicit prior written permission»

`/agents.md` сайта описывает commerce workflow для shopping agents с buyer-approved checkout (UCP/MCP) — это не освобождает от общих ToS-ограничений на automated database construction. Наш use case (canonical_records DB) — прямо в запрещённой зоне.

**Backlog-метка снята.** Без явного письменного разрешения от Jovian — не возвращаемся. См. Lesson #21.

## Текущее состояние репо

DB (`data/scraped.db`, gitignored):

- `developer_mozilla_org`: **34 canonical**, 0 unresolved vf
- `docs_python_org`: **27 canonical**, 0 unresolved vf
- `anthropic_news`: **19 canonical**, 0 unresolved vf
- `scrapethissite_com`: **6 canonical**, 0 unresolved vf
- `dummyjson_com`: **10 canonical**, 0 unresolved vf ← новый
- **TOTAL: 96 canonical**, 0 unresolved validation_failed

Tests: **183 total** (175 после PR1b + 7 в PR2 main + 1 integration test в PR2-hotfix; test 6 был переименован hotfix'ом, не добавлен). Eval 25 unchanged.

`config/sources.yaml`: **5 sources** (4 Firecrawl + 1 HTTP).

`main` после merge четырёх PR этой сессии (PR1a, PR1b, PR2, PR2-fixup config) и одного hotfix-PR.

## Открытые TODO

1. **TODO #3 (MDN timeout monitor)** — без изменений с Phase 7. Три URL под наблюдением (`Promise`, `Fetch_API/Using_Fetch`, `Headers/Cache-Control`). Эскалация при >1/3 батчей подряд с timeout'ами.

2. **TODO #8 (HTTP-адаптер без Firecrawl)** — **foundation закрыт, остались расширения:**
   - **Pagination engine для HTTP** (cursor / limit+skip / page-by-page). Для dummyjson нужно при расширении с 10 → 194 products. Pattern должен быть generic для других HTTP-источников.
   - **HTTP-response caching** (TTL similar to robots.txt cache в `compliance/robots.py`).
   - **`rate_limit_rps` из sources.yaml применять для HTTP-вызовов в run.py.** Это давний gap (не применяется и для Firecrawl), но для HTTP более релевантен (`rate_limit_rps=1.0` = `time.sleep(1.0)` между HTTP-fetch'ами).

3. **TODO #9 (новый) — dummyjson seed expansion.** Расширить с 10 до полного каталога (194 products). Возможно через pagination engine (TODO #8 sub-task) или через ручной список handle-ID'ов в адаптере.

## Lessons uncovered в Phase 8

### Lesson #21 (новый): `/agents.md` ≠ ToS-разрешение

Сайт может публиковать `/agents.md` как commerce facilitator для shopping agents (UCP/MCP с buyer-approved payment), но в общих ToS запрещать automated data extraction для database construction. Перед онбордингом источника с `/agents.md` — отдельно прочитать ToS и убедиться что наш use case (analytical catalog) разрешён, не только shopping workflow. Phase 8 example: jovianarchive.com — `/agents.md` приглашает UCP/MCP shopping, ToS блокирует «systematic or automated data collection... construct any kind of database».

### Lesson #22 (новый): HTTP-адаптеры НЕ конвертируют JSON primitive → Decimal в `parse_response`

`record_attempt` пишет `raw_payload` через `json.dumps` ДО Pydantic-валидации (`raw_content` — append-only audit). Decimal в payload даёт `TypeError: Object of type Decimal is not JSON serializable`. Conversion делает Pydantic schema-validator на стадии `validate_extracted` — внутренне применяет `Decimal(str(value))`, precision сохраняется. Symmetric с Firecrawl flow, где LLM возвращает float и Pydantic тоже делает str-coercion. Phase 8 example: `dummyjson_com` first paid batch crash → hotfix PR `fix/dummyjson-price-keep-float-for-json-audit`. Integration lock-in test `test_parse_response_output_validates_as_product_with_decimal_price` в `tests/sources/test_dummyjson_com.py` закрывает регрессию.

## Ожидающие PR

Нет. Все смерджены в течение сессии.

## Заметки для следующей сессии

- **5 источников в allow-list:** 4 Firecrawl (anthropic_news, docs_python_org, developer_mozilla_org, scrapethissite_com) + 1 HTTP (dummyjson_com). `api_available: true` только у dummyjson — semantic indicator HTTP-adapter источника.
- **TODO #8 foundation готова.** Расширения (pagination, caching, rate_limit_rps for HTTP) — отдельные PR'ы, каждое — самостоятельная задача.
- **jovianarchive — не онбордить** без письменного разрешения от owner'а. Backlog-метка снята.
- **Run-time роли неизменны:** `/investigate-failed`, `/onboard-source`, `/query`.
- **dummyjson seed expansion** — кандидат для следующей итерации (либо через pagination engine, либо вручную). 194 products в каталоге.
- **HttpSourceAdapter Protocol контракт** — `kind: ClassVar[str] = KIND_HTTP`, `parse_response` returns JSON-primitives (не Decimal). Для второго HTTP-источника контракт уже стабилен.
- **`scripts/check_db_state.py --source <name> [--show-ids]`** — стандартный pre-flight для HTTP- и Firecrawl-источников одинаково.
- **`scripts/resolve_vf.py`** — стандартный инструмент для vf-резолюций (Phase 6).

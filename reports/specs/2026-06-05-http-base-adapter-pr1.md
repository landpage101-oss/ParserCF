# Spec: PR1b — `_http_base.py` (TODO #8, foundation)

## Дата

2026-06-05 (rev1: split в two-PR workflow по Lesson #13)

## Что это

ТЗ для Claude Code на вторую часть PR1 ветки TODO #8 — HTTP-адаптер без Firecrawl. Только каркас + dispatch + тесты для HTTP-инфры. Без онбординга реального источника, без правок `config/sources.yaml`. Jovianarchive (и любой реальный Shopify-онбординг) — отдельный PR2 после merge этого.

## Предусловие: PR1a уже merged

Из-за CODEOWNERS-периметра `src/safety/**`, расширение `CostGate`/`CostBudget` для HTTP-bucket делается ОТДЕЛЬНЫМ PR1a руками оператора (ветка `feat/cost-http-bucket-helper`). PR1b ниже зависит от PR1a как от готового helper'а.

В PR1a добавляются:
- `CostBudget.max_http_calls_per_run: int = 200`
- `CostGate.http_calls_used: int = 0`
- `CostGate.before_http_call() -> None`
- `CostGate.after_http_success() -> None`
- `tests/test_cost_http.py` — 4 теста (`tests/` НЕ под CODEOWNERS, но включён в PR1a атомарно с helper'ом).

Если PR1a НЕ merged — PR1b не стартует. Импорты `before_http_call` / `after_http_success` из `src.safety.cost` сломают acceptance chain.

## Цель

Дать инфраструктуру для источников с публичным JSON-API: Shopify product/collection endpoints, UCP/MCP endpoints, любые REST/JSON-возвращающие. Эти источники не должны идти через Firecrawl: scrape поверх API нарушает принцип «API first» (см. Lesson #20).

## Разрешённые архитектурные решения (приняты до старта)

1. **Один URL → один raw → одна canonical-запись.** Контракт `SourceAdapter` НЕ ломаем. HTTP-адаптеры разворачивают пагинацию и discovery handle'ов внутри `list_urls`, наружу выдают индивидуальные URL'ы вида `https://site/products/{handle}.json`. Цена решения: N HTTP-запросов вместо одного collection-вызова — приемлемо, HTTP практически бесплатен.
2. **Cost-модель: отдельный bucket в `CostBudget`.** Добавляется поле `max_http_calls_per_run` параллельно `max_credits_per_run`. Шкалы не смешиваются. Готовы к будущим смешанным батчам.
3. **Только каркас.** Никакого реального адаптера, никакой записи в `sources.yaml`, никаких paid-запусков.

## Whitelist файлов (PR1b, всё лишнее — запрещено явно)

Создаются:

- `src/sources/_http_base.py` — Protocol + fetch-функция + конст-ы.
- `tests/sources/test_http_base.py` — unit-тесты для fetch, Protocol-совместимость, sanitize hook, ошибки.
- `tests/test_run_dispatch.py` — unit-тест для dispatch в `run.py` (Firecrawl vs HTTP по `adapter.kind`).

Модифицируются:

- `src/run.py` — добавить dispatch по `getattr(adapter, "kind", KIND_FIRECRAWL)`. Firecrawl-ветка остаётся pixel-perfect такой как есть; HTTP-ветка — параллельная. (НЕ под CODEOWNERS, Claude Code может править.)

**НЕ модифицируются (CODEOWNERS и прочее):**

- `src/safety/cost.py` — **уже расширен в PR1a руками оператора.** В PR1b — только импортировать `before_http_call`, `after_http_success` как готовые helper'ы.
- `src/sources/_base.py` — Protocol остаётся неизменным. HTTP-Protocol живёт в `_http_base.py`, отдельный.
- `src/sources/anthropic_news.py`, `docs_python_org.py`, `developer_mozilla_org.py`, `scrapethissite_com.py` — существующие адаптеры **не трогать**. У них нет атрибута `kind` — `getattr` в `run.py` вернёт дефолт `KIND_FIRECRAWL`.
- `src/extract.py` — `fetch_via_firecrawl`, `validate_extracted` остаются как есть.
- `src/db/store.py` — `record_attempt`, `upsert_canonical` универсальны, изменений не требуют (CODEOWNERS).
- `src/safety/sanitize.py`, `src/safety/classifier.py`, `src/safety/trace.py` — без изменений (CODEOWNERS).
- `src/compliance/sources_config.py`, `src/compliance/robots.py` — без изменений.
- `config/sources.yaml` — без изменений (CODEOWNERS; запись для будущего HTTP-источника — отдельный PR).
- `.claude/**`, `.github/**`, любые eval-fixtures.
- `tests/test_cost_http.py` — **уже создан в PR1a.** Не дублировать.

## Ветка / коммит

- Branch: `feat/http-base-adapter-skeleton` от свежего `main` **после merge PR1a**.
- Один коммит. Title: `feat(sources): add _http_base adapter skeleton + run dispatch (TODO #8 part 1b)`.

## Контракт `src/sources/_http_base.py`

### Константы

```python
KIND_FIRECRAWL: Final[str] = "firecrawl"
KIND_HTTP: Final[str] = "http"

USER_AGENT: Final[str] = "agent-parser/1.0 (+contact@example.com)"
# Берём из robots.USER_AGENT — должен совпадать. Импортировать оттуда, не дублировать.

_SANITIZE_FIELDS: Final[tuple[str, ...]] = ("body_md", "definition", "description")
# Совпадает с src/extract.py::_SANITIZE_FIELDS. Дублирование осознанное:
# extract.py остаётся Firecrawl-specific; _http_base.py самодостаточен.
# Если в будущем _SANITIZE_FIELDS расходятся — это сигнал к рефактору в shared
# helper в src/safety/, отдельным PR.

_HTTP_TIMEOUT_SECONDS: Final[float] = 30.0
```

### Protocol

```python
from collections.abc import Iterable
from typing import ClassVar, Protocol

class HttpSourceAdapter(Protocol):
    """Adapter for sources with public JSON API. Not Firecrawl.

    One URL → one HTTP GET → one parsed payload → one canonical record.
    Pagination / handle-discovery — внутри list_urls, не в fetch.
    """

    kind: ClassVar[str]  # MUST be KIND_HTTP — used for run.py dispatch
    domain: str
    name: str
    page_type: str  # one of 'article'|'docs'|'product'|'reference'

    def list_urls(self, since: str | None = None) -> Iterable[str]: ...
    def parse_id(self, url: str) -> str: ...
    def parse_response(
        self,
        response_json: dict[str, object],
        url: str,
    ) -> dict[str, object]:
        """Map JSON API response to dict matching PAGE_TYPE_TO_SCHEMA[page_type].

        MUST populate at minimum: source, source_id, source_url (caller will
        override these defensively but adapter should still produce them).
        Pure function — no I/O, no sanitize. Sanitize happens in fetch_via_http.
        """
        ...
```

`HttpSourceAdapter` **не наследует** от `src/sources/_base.py::SourceAdapter`. Это отдельный Protocol. `run.py` определяет тип адаптера по `getattr(adapter, "kind", KIND_FIRECRAWL)`, не по isinstance. Это даёт нулевой риск для существующих 4 адаптеров.

### Функция `fetch_via_http`

```python
def fetch_via_http(
    adapter: HttpSourceAdapter,
    url: str,
) -> dict[str, object]:
    """Fetch JSON from a public API, parse via adapter, sanitize unsafe fields.

    Returns dict suitable for record_attempt + validate_extracted.

    Raises:
      ValueError on non-2xx HTTP, malformed JSON, empty parsed payload.
      urllib.error.URLError on transport failure (caller wraps via gate.after_error).

    NOT responsible for: robots.txt (caller checks via is_allowed), CostGate
    bookkeeping (caller wraps in before_http_call / after_*), DB writes.
    """
```

Internals (рекомендуемый дизайн):

1. `urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})`.
2. `urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_SECONDS)` внутри `with`.
3. Прочитать body, проверить `Content-Type` начинается с `application/json` (warning в log если нет, но не raise — некоторые сервера отдают `text/json` или `application/vnd.api+json`).
4. `json.loads(body.decode("utf-8"))`. Не `decode("utf-8", errors="replace")` — для API хотим строгий контракт; bad encoding = ошибка.
5. `payload = adapter.parse_response(response_json, url)`.
6. Если `payload` пуст (`not payload` или нет обязательных source/source_id/source_url) — `raise ValueError(f"empty payload from {url}")`.
7. Sanitize по `_SANITIZE_FIELDS` (только str-значения).
8. Defensive overrides: `payload["source"] = adapter.name; payload["source_id"] = adapter.parse_id(url); payload["source_url"] = url` — на случай, если `parse_response` ошибся (та же логика что в `run.py` для Firecrawl, см. строки 141-143). Решает заранее: если адаптер забыл выставить, мы выставляем.

   **NB:** оставить `source = adapter.name`, не `cfg.adapter` stem. Это соответствует существующей логике (`source` в `raw["source"]` в `run.py` — это `_config_name(cfg)`, что равно `Path(cfg.adapter).stem` = `name` адаптера). Источник имени единственный.

9. Возвращает `payload`.

`urlopen` — это `noqa: S310` нужно, как в `robots.py`. Альтернативы (`requests`, `httpx`) — нет новых зависимостей в PR1.

### Без `kind = KIND_HTTP` в Protocol-default

Protocol не поддерживает defaults для атрибутов. Реализующие классы (в будущем PR2) явно ставят `kind: ClassVar[str] = KIND_HTTP`. Это часть контракта.

## `src/safety/cost.py` — уже расширен в PR1a

Helper'ы доступны как готовый API после merge PR1a:

```python
from src.safety.cost import CostBudget, CostGate

# CostBudget.max_http_calls_per_run: int = 200 (default)
# CostGate.http_calls_used: int = 0
# CostGate.before_http_call() -> None      # raises RuntimeError on cap/breaker
# CostGate.after_http_success() -> None    # increments http_calls_used + iterations, resets consecutive_errors
# CostGate.after_error()                   # общий, переиспользуем
```

В PR1b — только использование. Никаких правок `src/safety/cost.py` и `tests/test_cost_http.py`.

**Default `max_http_calls_per_run = 200`** — достаточно для PoC любого Shopify-каталога средней руки, в три раза больше чем `max_iterations=50` (что отдельная проблема, см. «Известные грабли»).

## Изменения в `src/run.py`

В цикле, после `_is_fresh` skip-check и перед существующим `with span("scrape"...)`-блоком:

```python
from src.sources._http_base import KIND_FIRECRAWL, KIND_HTTP, fetch_via_http

# ... внутри for-loop ...
adapter_kind = getattr(adapter, "kind", KIND_FIRECRAWL)

with span("scrape", parent_id=root["span_id"], url=url, kind=adapter_kind) as s:
    if adapter_kind == KIND_FIRECRAWL:
        gate.before_call(cost=5)
        try:
            raw = fetch_via_firecrawl(url, adapter.page_type)
        except (KeyError, ImportError, AttributeError, ModuleNotFoundError):
            raise
        except Exception:
            logger.exception("fetch failed for %s", url)
            gate.after_error()
            counts["errors"] += 1
            continue
    elif adapter_kind == KIND_HTTP:
        gate.before_http_call()
        try:
            raw = fetch_via_http(adapter, url)
        except (KeyError, ImportError, AttributeError, ModuleNotFoundError):
            raise
        except Exception:
            logger.exception("http fetch failed for %s", url)
            gate.after_error()
            counts["errors"] += 1
            continue
    else:
        raise ValueError(f"unknown adapter kind: {adapter_kind!r}")

    # ... rest of body unchanged: parse_id, defensive overrides,
    # record_attempt, validate_extracted, upsert_canonical OR
    # append_validation_failure ...

    if adapter_kind == KIND_FIRECRAWL:
        gate.after_success(cost=5)
    else:
        gate.after_http_success()
    counts["canonical"] += 1
    con.commit()
```

Ключевое:

- Атрибут `kind=adapter_kind` в `span` — для traceability.
- Defensive overrides `raw["source"] = source` etc. — остаются после fetch для обоих путей. Для HTTP это дубль того, что сделал `fetch_via_http`, — допустимо (idempotent).
- ConfigError-catch (`KeyError`, `ImportError` и т.д.) — одинаковый для обоих путей; не circuit-breaker quota.
- `counts["errors"] += 1` единая семантика; в trace event `kind` разделяет.

Если в `run.py` функция уже близка к C901 (сложность) — вынесите fetch-блок в helper `_fetch_for_adapter(adapter, url, gate, logger) -> dict | None` (возвращает `None` при handled error). Это уменьшит цикломатику и упростит test_run_dispatch.py.

## Test plan

### `tests/sources/test_http_base.py` (6 тестов)

1. `test_fetch_via_http_returns_payload` — mock `urllib.request.urlopen` возвращает 200 + JSON body. `parse_response` test-double превращает в dict. Проверить: возвращённый dict совпадает с ожидаемым, source/source_id/source_url выставлены.
2. `test_fetch_via_http_sanitizes_body_fields` — JSON body содержит `body_md` с `​` (zero-width). После `fetch_via_http` поле очищено.
3. `test_fetch_via_http_raises_on_non_2xx` — `urlopen` поднимает `HTTPError` code=404 → `fetch_via_http` поднимает (не глотает).
4. `test_fetch_via_http_raises_on_malformed_json` — body не JSON → `ValueError`.
5. `test_fetch_via_http_raises_on_empty_parsed_payload` — `parse_response` возвращает `{}` → `ValueError`.
6. `test_fetch_via_http_overrides_identifiers_defensively` — `parse_response` ставит неправильные `source/source_id/source_url`; после fetch они перезаписаны от adapter/url.

Test-double `HttpSourceAdapter` — минимальный класс прямо в тестовом файле, реализующий contract.

### `tests/test_cost_http.py` — уже в PR1a

Не дублировать. Покрытие: 4 теста (within_cap, at_cap, success_resets_errors, shared_circuit_breaker).

### `tests/test_run_dispatch.py` (2 теста)

1. `test_run_dispatches_firecrawl_for_default_adapter` — fake adapter без `kind`, моки fetch_via_firecrawl, fetch_via_http; убедиться firecrawl вызван, http не вызван.
2. `test_run_dispatches_http_for_kind_http_adapter` — fake adapter с `kind=KIND_HTTP`, наоборот.

Тесты используют `tmp_path` sqlite DB, `is_allowed` mock (возврат `(True, None)`), seed-URL `["https://example.test/x"]`.

### Тестовый baseline

После merge PR1a baseline = **167** (163 + 4).
PR1b добавляет: **+8** (6 для test_http_base + 2 для test_run_dispatch).
Ожидаемый после PR1b: **175**.

При прогоне `pytest tests/` подтвердить вслух: «167 → +8 → 175». Если число не сходится — стоп, разбираемся.

`pytest tests/eval/` — не меняется, 25 eval-тестов.

## Acceptance chain (перед commit'ом)

```powershell
ruff check src/ tests/ --no-fix
ruff format --check src/ tests/
mypy --strict src/
pytest tests/
pytest tests/eval/
pre-commit run --all-files
```

Затем оператор смотрит **сырой `git diff --cached`** построчно, верифицирует blob-хэши, потом GO.

## Известные lint-грабли

- **S310** (`urllib.request.urlopen` — audit URL open). Точечный `# noqa: S310` на строке вызова, причина «public JSON API, robots.txt + allow-list уже проверены caller'ом». Как в `src/compliance/robots.py`.
- **BLE001** (blind except). В `run.py` уже есть `except Exception:` — паттерн установлен, тот же подход для HTTP-ветки. Не глушить `# noqa` без необходимости.
- **PERF203** (try-except в цикле). Не применимо — структура унаследована от существующего run.py.
- **ARG002** (unused `since` argument). В test-double адаптерах внутри тестов — `# noqa: ARG002`, как в существующих адаптерах.
- **DTZ005/DTZ007** — не релевантно, новых datetime-конструкций нет.
- **RUF100** — `# noqa: S310` ставить **после** `ruff format`, только если правило реально стрельнуло. Не превентивно.
- **C901** (function complexity). Если `run.py::run()` пробивает порог 10 после добавления dispatch — вынести `_fetch_for_adapter` helper. Не лепить `noqa: C901` на функцию без рефактора.

## Что НЕ входит в PR1 (явно, для предотвращения scope creep)

- Реальный HTTP-адаптер для какого-либо источника. Никаких файлов `src/sources/jovianarchive_com.py` или подобных.
- Правка `config/sources.yaml`. CODEOWNERS-zone, операторская задача в PR2 после реального онбординга.
- Retries / backoff для HTTP. Текущий circuit breaker + `gate.after_error` достаточно как safety net в каркасе.
- Кеширование HTTP-ответов. На уровне `is_allowed` уже есть TTL-кэш для robots.txt; для контента кэш — отдельный вопрос для PR3+.
- Pagination engine / cursor follow. Pagination — внутри `list_urls` конкретного адаптера, не в `_http_base.py`.
- Замена `requests`/`httpx`. stdlib `urllib.request` достаточно для PoC.
- Применение `rate_limit_rps` из `sources.yaml` в `run.py`. Это давний gap (не используется и в Firecrawl-ветке), отдельный PR, нерелевантно скоупу #8.
- Изменения в `src/extract.py`, `src/safety/sanitize.py`, `src/db/store.py`. Эти модули остаются стабильными.

## Известные предостережения (для оператора, не для Claude Code)

1. **`CostBudget.max_iterations=50` default + 200 HTTP-вызовов** — несовместимы из коробки. При первом реальном HTTP-батче (PR2) нужно либо поднять `max_iterations` через CLI override (если добавим), либо bump default. На текущий PR1 — фиксируем default 200 для `max_http_calls_per_run`, оставляем `max_iterations=50`. Тесты cost_http используют локальные `CostBudget(...)` инстансы с подходящими значениями — не зависят от default.
2. **Sanitize-fields дублируются** между `src/extract.py` и `src/sources/_http_base.py`. Если списки начнут расходиться — отдельный PR на shared helper `src/safety/_sanitize_fields.py`. Преждевременной DRY не делать.
3. **Никаких реальных HTTP-вызовов в CI**. Тесты используют `unittest.mock.patch("urllib.request.urlopen", ...)` — никаких сетевых I/O.

## Что от оператора нужно после merge PR1

Ничего срочного. PR2 (реальный HTTP-источник) — отдельная задача. Перед PR2 — стандартный onboard-source flow: legal-check (robots + ToS), seed-URL'ы (через collection JSON), pre-flight `python scripts/check_db_state.py`. Кандидаты на PR2: jovianarchive.com (Shopify) или любой другой sandbox с public JSON API для отработки контракта.

## Summary для финального сообщения Claude Code

После acceptance + push, в финальном сообщении ожидается:
- Краткая сводка: число добавленных тестов (175 baseline), список созданных/изменённых файлов, факт что `mypy --strict` чист, факт что eval не тронут.
- Сырой `git diff --cached` (для diff-review).
- Команды push (`git push -u origin feat/http-base-adapter-skeleton`) и заготовка PR-описания.

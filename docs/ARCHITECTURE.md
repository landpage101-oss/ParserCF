# ARCHITECTURE

## Принцип

Шесть слоёв: пять последовательных в основном пайплайне (вертикально) + один cross-cutting safety perimeter, оборачивающий слои 2, 3 и 5. Полная схема — `architecture.mermaid` / SVG в `agent_parser_full_report.html`.

## Слой 1 · Compliance & Detection (workflow)

Pre-flight перед любым обращением к домену. Полностью детерминирован, агент решений не принимает.

Компоненты: `src/compliance/robots.py` (парсинг robots.txt и crawl-delay), `config/sources.yaml` (allow-list источников с `legal_basis`, `rate_limit_rps`, отметкой о наличии API). Если домен не в allow-list — `RuntimeError`, не fallback. Если домен новый — HITL-gate (review человеком до добавления в YAML).

## Слой 2 · Discovery (workflow + agent в design-time)

Run-time: для известного источника адаптер из `src/sources/<domain>.py` реализует протокол `SourceAdapter` (`list_urls`, `parse_id`) и возвращает поток URL. Внутри использует `firecrawl_map`, RSS, sitemap или собственную пагинацию.

Design-time: при добавлении нового источника разово запускается `/onboard-source <domain>` — агент пишет драфт адаптера и тестов, дальше PR-ревью человеком. После merge — обычный run-time.

## Слой 3 · Extraction (workflow)

`src/extract.py`. Вызов `firecrawl_scrape` с `formats=[{type:"json", schema: PydanticModel.model_json_schema()}]` и валидация результата через `Pydantic.model_validate`. Несоответствие схеме → запись в `validation_failed`, batch продолжается.

Pydantic-схемы — в `src/schemas/`: `Article`, `DocsPage`, `Product`, `ReferenceEntry` (см. `evals_and_ci.md` §3 для полных определений). Каждая включает field-validator'ы против placeholder-страниц («access denied», «lorem ipsum», «404»).

## Слой 4 · Storage & Audit

SQLite, схема в `src/db/schema.sql`. Четыре таблицы:

`raw_content` — append-only журнал всех попыток скрапа с `content_hash` (sha256), `raw_payload`, `scraped_at`, `trace_id`. Никогда не модифицируется.

`canonical_records` — последняя валидная версия по `(source, source_id)`. Обновляется через UPSERT.

`change_history` — diff'ы по полям между версиями, append-only.

`validation_failed` — очередь записей, не прошедших Pydantic-валидацию или injection classifier; разбирается агентом в Слое 5.

Запись инкапсулирована в `src/db/store.py` (`record_attempt`, `upsert_canonical`). Агенту запрещено писать в БД напрямую.

## Слой 5 · Agent (run-time, узкий)

Три слот-команды, каждая со своим узким `allowed-tools`:

`/investigate-failed <source>` — расследование `validation_failed`. Tools: `Read(src/sources/**)`, `Read(data/**)`, `firecrawl_scrape` с cost cap, `Write(reports/investigations/**)`. Агент не правит адаптер сам — формирует предложение фикса.

`/onboard-source <domain>` — design-time онбординг. Tools: `Read`, `Write(src/sources/**)`, `Write(tests/sources/**)`, `firecrawl_map`, `firecrawl_scrape` с cost cap. Результат проходит PR-ревью.

`/query <NL-query>` — read-only трансляция в SQL поверх `canonical_records`. Tools: только `Bash(sqlite3 data/scraped.db -readonly *)`. Никакого Firecrawl, никаких write-тулов.

## Слой 6 · Safety perimeter (cross-cutting)

`src/safety/`. Применяется ко всем вызовам Firecrawl и ко всем агентским ролям.

`sanitize.py` — strip zero-width chars, нейтрализация role-prefixes (`system:`, `assistant:`), детект injection-маркеров (`ignore previous instructions` и т.д.). Возвращает `(cleaned_text, warnings)`.

`classifier.py` — guard-LLM (Haiku-class) с бинарным выходом SAFE/UNSAFE. Запускается на длинных текстах перед попаданием в контекст агента.

`cost.py` — `CostGate` с `max_credits_per_run`, `max_iterations`, `max_consecutive_errors` (circuit breaker). Срабатывание = аварийный стоп batch'а.

`trace.py` — structured JSONL в `data/traces/<YYYYMMDD>.jsonl`. Каждый span: `tool_name`, `args_hash`, `cost_credits`, `tokens_in/out`, `result_hash`, `warnings_from_sanitize`. OpenTelemetry/LangSmith — расширение, не базовая зависимость.

## Архитектурные границы (нерушимые)

Агент не пишет в `canonical_records`, не трогает `src/safety/**`, `src/db/**`, `config/sources.yaml` без PR-ревью. Эти ограничения зафиксированы в `.claude/settings.json` (deny-list) и продублированы в `CLAUDE.md`.

`firecrawl_crawl` (рекурсивный обход) — запрещён агенту в run-time. Запускается только из явного workflow-кода с обязательным `limit` и `CostGate`.

API-ключи — только через `${FIRECRAWL_API_KEY}` / `${ANTHROPIC_API_KEY}` в env, никогда в коде, конфиге или URL MCP-сервера.

## Связанные документы

- `docs/PROJECT_OVERVIEW.md` — что и зачем.
- `docs/TECH_STACK.md` — конкретные библиотеки.
- `agent_parser_secure_v2.md` — полная инструкция с кодом каждого слоя.
- `evals_and_ci.md` — eval-каркас и CI.

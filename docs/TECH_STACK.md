# TECH_STACK

## Runtime и core

**Python 3.12+** — основной язык. Современные дженерики (`list[str]`, `T | None`), pattern matching, точные ошибки Pydantic v2.

**Claude Code** — CLI-агент Anthropic; используется как агентский слой в трёх узких run-time ролях и в design-time онбординге. Установка через официальный установщик Anthropic; авторизация — OAuth с подпиской либо `ANTHROPIC_API_KEY`.

**Firecrawl MCP** — внешний скрапинг через Model Context Protocol. Подключение — stdio через `npx -y firecrawl-mcp` с подстановкой `${FIRECRAWL_API_KEY}` из env. Hosted MCP с ключом в URL не используется.

## Извлечение и валидация

**Pydantic v2** — schema-as-contract для четырёх типов сущностей (`Article`, `DocsPage`, `Product`, `ReferenceEntry`). `model_json_schema()` передаётся в Firecrawl как extraction schema; `model_validate` — финальная валидация перед записью. Field-validators отклоняют placeholder/error-страницы.

**Firecrawl JSON-mode** — `formats=[{"type": "json", "schema": ...}]`. Стоит дороже базового scrape по их прайсу, но избавляет от LLM-парсера на нашей стороне.

## Хранилище

**SQLite** через стандартный `sqlite3` (без ORM). Четыре таблицы: `raw_content` (append-only audit), `canonical_records` (last valid by source_id), `change_history` (field-level diffs), `validation_failed` (очередь для агента-следователя). Полная схема — в `src/db/schema.sql`.

Постгрес/MySQL — расширение, не базовая зависимость. SQLite выбран из-за zero-ops и упрощения локального воспроизведения багов.

## Безопасность

**`urllib.robotparser`** (stdlib) — robots.txt и crawl-delay.

**Свой sanitize-слой** в `src/safety/sanitize.py` — `unicodedata.normalize("NFKC")`, regex для zero-width chars, role-prefixes, injection markers.

**Guard-LLM** через Anthropic API (Haiku-class) — `src/safety/classifier.py`, бинарный SAFE/UNSAFE.

**`CostGate`** в `src/safety/cost.py` — лимиты по кредитам, итерациям, последовательным ошибкам (circuit breaker).

## Observability

**Structured JSONL trace** — `src/safety/trace.py`, `contextmanager span(...)`, файлы `data/traces/<YYYYMMDD>.jsonl`. Без внешних SaaS на старте.

**OpenTelemetry / LangSmith** — опционально, добавляется когда проект перерастёт one-developer формат.

**duckdb** или **jq** — для ad-hoc анализа traces (не зависимость, рекомендация в README).

## Тестирование

**pytest** — `pytest_generate_tests` для авто-дискавера 20 fixtures из `tests/eval/fixtures/`. Hard-checks для структурных полей, soft-checks (`*_min_length`, `*_must_contain`) для markdown-тел.

**Synthetic + captured fixtures** — синтетические HTML/MD авторятся вручную (контролируемый ground-truth), captured-фикстуры (3 шт.) снимаются через `tests/eval/tools/capture_fixture.py` со стабильных URL (`docs.python.org/3/library/json.html`, `developer.mozilla.org/.../HTTP/Methods/GET`, `arxiv.org/abs/2210.03629`).

**Live smoke** — отдельный workflow `eval-live-smoke` на schedule (раз в сутки), переснимает captured-фикстуры и сравнивает `content_hash`. Warning, не failure.

## CI/CD

**GitHub Actions** — два workflow:

`.github/workflows/eval.yml` — per-PR eval, без сетевых вызовов и без `FIRECRAWL_API_KEY`. Timeout 10 минут. Постит результат комментарием на PR через `actions/github-script@v7`.

`.github/workflows/eval-live.yml` — schedule раз в сутки, использует `secrets.FIRECRAWL_API_KEY`, проверяет дрейф captured-фикстур.

Branch-protection на `main`: merge заблокирован, пока `eval-suite / eval` не зелёный.

## Dev-tools

**`pip install -e ".[dev]"`** — установка проекта в editable mode с dev-зависимостями (pytest, ruff, mypy).

**ruff** — линтер и форматтер (заменяет flake8/black/isort).

**mypy** в strict-mode — проверка типов; критично для Pydantic-схем и Protocol-интерфейсов адаптеров.

## Внешние сервисы

**Anthropic API** — Claude (Sonnet по умолчанию для агентских команд, Haiku для guard-LLM).

**Firecrawl** — scrape/map/extract. На старте — free tier (500 кредитов lifetime, concurrency 2); далее — Hobby/Standard по нагрузке.

## Связанные документы

- `docs/PROJECT_OVERVIEW.md` — цели и не-цели.
- `docs/ARCHITECTURE.md` — где какие технологии живут.
- `docs/CURRENT_STATUS.md` — что из стека уже подтверждено в коде, что только в дизайне.

# CURRENT_STATUS

## Phase

**Phase 0 — Design complete, implementation not started.**

На сегодня готова только проектная документация и архитектура. Кода в `src/`, `tests/`, `config/`, `.claude/`, `.github/` нет; репозиторий пустой кроме `docs/` и связанных reference-документов в корне.

## Что готово

Архитектурная инструкция (полная, с кодом каждого слоя) — `agent_parser_secure_v2.md` в корне репо.

Eval-каркас (20 fixtures смешанного типа: 5 article, 5 docs, 5 product, 5 reference включая 1 prompt-injection edge-case) — `evals_and_ci.md` в корне репо.

GitHub Actions workflow (per-PR eval + live-smoke schedule) — описан в `evals_and_ci.md`, не закоммичен.

Архитектурная схема в Mermaid — `architecture.mermaid` в корне репо.

Контекстные файлы для Claude Code — `docs/PROJECT_OVERVIEW.md`, `docs/ARCHITECTURE.md`, `docs/TECH_STACK.md`, этот файл.

Пошаговая инструкция для Claude Code — `IMPLEMENTATION_ROADMAP.md`.

Список баг-фиксов в проектной документации, которые нужно применить до старта кодинга — `ERRATA.md`.

## Решения по открытым вопросам (зафиксированы 2026-05-04)

**Пилотный источник: `docs.python.org/3`.** Стабильная документация, дружелюбный robots.txt, нет anti-bot. Page type — `docs`. Первая Pydantic-схема, доводимая до production-готовности — `DocsPage`. Первый адаптер — `src/sources/docs_python_org.py`. Captured-fixture `08_python_json` уже планируется в `evals_and_ci.md`.

**Зависимости: `pyproject.toml` + extras (PEP 621).** `[project.optional-dependencies]` для `dev`. Установка — `pip install -e ".[dev]"`. `requirements.txt` не используется как источник истины (можно автогенерировать через `pip-compile`, если потребуется для Docker, но source-of-truth — `pyproject.toml`).

**Линтинг: strict с первого коммита.** `ruff` с `select = ["ALL"]` и точечными `ignore` в `[tool.ruff.lint]`. `mypy --strict` для всего `src/`. Конкретный набор `ignore` фиксируется в первом же коммите и проходит через PR review.

**Owner allow-list: solo.** Единственный approver на `config/sources.yaml` — `@landpage101-oss`. `CODEOWNERS` записывается строкой `config/sources.yaml @landpage101-oss`. Когда команда вырастет до 2+ — переходим на CODEOWNERS group; TODO зафиксирован ниже.

## Что НЕ готово

Весь кодовый слой:

`src/compliance/robots.py` — реализация `is_allowed`.

`src/safety/{sanitize,classifier,cost,trace}.py` — четыре компонента safety perimeter.

`src/schemas/{article,docs,product,reference}.py` — четыре Pydantic-модели.

`src/sources/_base.py` — Protocol `SourceAdapter`.

`src/sources/<domain>.py` — ни одного адаптера ещё нет (первый — `docs_python_org.py`).

`src/db/{schema.sql,store.py}` — DDL и UPSERT-логика.

`src/extract.py` — обёртка вокруг Firecrawl + `extract_from_local` для тестов.

`src/run.py` — точка входа batch'а.

Конфигурация:

`config/sources.yaml` — пустой allow-list (на старте Phase 1 туда заносится `docs.python.org` после согласования).

`.claude/settings.json` — права с deny-list.

`.claude/commands/{investigate-failed,onboard-source,query}.md` — три slash-команды.

`.claude/rules/*.md` — расширенные правила, импортируемые через `@`.

`CLAUDE.md` — минимальный файл инструкций агенту.

`.mcp.json` — конфиг Firecrawl MCP.

`.env.example`, `.gitignore`, `pyproject.toml`, `CODEOWNERS`.

Тесты и фикстуры:

`tests/eval/conftest.py`, `tests/eval/test_eval_suite.py` — pytest-харнес.

`tests/eval/fixtures/{article,docs,product,reference}/` — 20 файлов input + 20 expected.json.

`tests/eval/tools/capture_fixture.py` — скрипт захвата captured-фикстур.

CI:

`.github/workflows/eval.yml`, `.github/workflows/eval-live.yml`.

## Следующие шаги (см. `IMPLEMENTATION_ROADMAP.md` для полной развёртки)

**Этап 0 — Применить ERRATA.** До любого кода: исправить баги в `agent_parser_secure_v2.md` и `evals_and_ci.md`, перечисленные в `ERRATA.md`. Один коммит.

**Этап 1 — Bootstrap репо.** Создать структуру папок, `pyproject.toml` с dev-зависимостями, `.gitignore`, `.env.example`, `CODEOWNERS`, README. Один коммит.

**Этап 2 — Pydantic-схемы.** `src/schemas/` (4 модели) с unit-тестами. Без вызовов Firecrawl. Один коммит.

**Этап 3 — Safety perimeter.** `src/safety/` (4 компонента) с unit-тестами. Один коммит.

**Этап 4 — Compliance.** `src/compliance/robots.py`, валидатор `config/sources.yaml`. Один коммит.

**Этап 5 — Storage.** `src/db/schema.sql`, `src/db/store.py`, миграция. Unit-тесты на UPSERT и change_history. Один коммит.

**Этап 6 — SourceAdapter base + первый адаптер.** `src/sources/_base.py` + `src/sources/docs_python_org.py`. Согласовать домен в `config/sources.yaml`. Один коммит.

**Этап 7 — Extraction.** `src/extract.py` (`extract_from_local` + `extract_via_firecrawl`). Один коммит.

**Этап 8 — Eval fixtures.** Создать 20 fixtures по реестру из `evals_and_ci.md` §5 (3 captured через `capture_fixture.py`, 17 синтетических вручную). Один коммит.

**Этап 9 — Pytest-харнес.** `tests/eval/conftest.py`, `tests/eval/test_eval_suite.py`. Локальный прогон зелёный. Один коммит.

**Этап 10 — CI.** `.github/workflows/eval.yml`, `.github/workflows/eval-live.yml`, branch-protection. Один коммит.

**Этап 11 — Run + первый batch.** `src/run.py`, прогнать первый batch end-to-end на 5–10 страницах docs.python.org. Один коммит + один отчёт-проверка.

**Этап 12 — Claude Code config.** `.claude/settings.json`, `.claude/commands/`, `.claude/rules/`, `CLAUDE.md`, `.mcp.json`. Один коммит.

После этапа 12 проект переходит в Phase 1 — MVP working on docs.python.org.

## Открытые TODO (не блокирующие Phase 1)

`CODEOWNERS` group для `config/sources.yaml` — добавить, когда команда вырастет до 2+ человек.

Hosted Firecrawl MCP вместо stdio — пересмотреть, когда Anthropic стабилизирует поддержку и решит вопрос с ключом-в-URL.

Вторая schema — `Article` или `Product` — поднимается до production-готовности после Phase 1, когда `DocsPage` уже работает.

## Связанные документы

- `docs/PROJECT_OVERVIEW.md` — цели проекта.
- `docs/ARCHITECTURE.md` — что должно быть построено.
- `docs/TECH_STACK.md` — какими инструментами строить.
- `agent_parser_secure_v2.md` — полная инструкция-референс.
- `evals_and_ci.md` — детали eval-каркаса.
- `ERRATA.md` — список баг-фиксов в проектной документации (применить до Этапа 1).
- `IMPLEMENTATION_ROADMAP.md` — пошаговая инструкция для Claude Code.

# ERRATA — список баг-фиксов в проектной документации

Документ перечисляет восемь конкретных правок в `agent_parser_secure_v2.md` и `evals_and_ci.md`, которые нужно применить **до** старта Этапа 1 (Bootstrap репо). Это не косметика, а реальные баги: оставленные в коде, они приведут к скрытым отказам в production.

Применять одним коммитом: `docs: fix bugs in design docs (sanitize regex, schemas, eval harness, raw_payload)`.

---

## E-1. `sanitize.py`: literal Unicode chars в regex → переписать через `\u`-escapes

**Файл:** `agent_parser_secure_v2.md`, §8.1.

**Проблема.** В коде стоит регулярка с буквальными невидимыми символами:

```python
INVISIBLE = re.compile(
    r"["
    r"​-‏"   # ZW space, ZWNJ, ZWJ, LRM, RLM
    r"  "    # LINE SEPARATOR, PARAGRAPH SEPARATOR
    r"‪-‮"   # bidi overrides
    r"⁠-⁯"   # word joiner и т.д.
    r"﻿"          # BOM
    r"]"
)
```

Комментарий выше прямо требует `\u`-escape, но сам код это требование нарушает. Любой IDE с авто-фиксером line terminators (VS Code предлагает «Remove unusual line terminators» по умолчанию) молча вырежет U+2028/U+2029 из исходника, и детектор перестанет ловить ровно ту атаку, ради которой написан. Это худший класс багов — он невидим в diff'е.

**Фикс.** Заменить блок на:

```python
# src/safety/sanitize.py
import re
import unicodedata

# Codepoint-диапазоны zero-width / bidi-control / line-separator символов,
# которые атакующие часто используют для маскировки prompt-injection payload'ов
# в скрапленном контенте.
#
# ВАЖНО: только \u-escape sequences. Литералами писать запрещено code-review-правилом —
# любой IDE с auto-fix для "unusual line terminators" вырежет U+2028/U+2029 молча
# и сломает детектор.
INVISIBLE = re.compile(
    "["
    "​-‏"  # ZW space, ZWNJ, ZWJ, LRM, RLM
    "  "   # LINE SEPARATOR, PARAGRAPH SEPARATOR
    "‪-‮"  # bidi overrides (LRE, RLE, PDF, LRO, RLO)
    "⁠-⁯"  # word joiner, invisible operators, deprecated formatters
    "﻿"         # BOM / zero-width no-break space
    "]"
)

ROLE_PREFIXES = re.compile(
    r"^\s*(system|assistant|user|developer)\s*:",
    re.IGNORECASE | re.MULTILINE,
)

INJECTION_HINTS = re.compile(
    r"(ignore (all |previous )?instructions|"
    r"disregard (the )?(above|prior)|"
    r"you are now|new instructions:)",
    re.IGNORECASE,
)

def sanitize(text: str) -> tuple[str, list[str]]:
    """Возвращает (clean_text, warnings)."""
    warnings: list[str] = []
    cleaned = unicodedata.normalize("NFKC", text)
    if INVISIBLE.search(cleaned):
        warnings.append("invisible_characters_stripped")
        cleaned = INVISIBLE.sub("", cleaned)
    if ROLE_PREFIXES.search(cleaned):
        warnings.append("role_prefix_neutralized")
        cleaned = ROLE_PREFIXES.sub("[neutralized-role-prefix]:", cleaned)
    if INJECTION_HINTS.search(cleaned):
        warnings.append("injection_hint_detected")
    return cleaned, warnings
```

**Acceptance:** ruff не должен ругаться на noqa-marker'ы; unit-тест на NFKC + zero-width strip + role-prefix substitution проходит.

---

## E-2. `Article` — две разные схемы между документами

**Файлы:** `agent_parser_secure_v2.md` §5.1 vs `evals_and_ci.md` §3.

**Проблема.**
- В `agent_parser_secure_v2.md` §5.1: `source_id: str`, `url: HttpUrl`, без `language` валидатора-формы (он там есть, но в evals другой).
- В `evals_and_ci.md` §3: `source_url: HttpUrl`, без `source_id`, `language` с pattern `^[a-z]{2}$`.

`extract.py` и `eval_suite` будут использовать разные модели, тесты упадут на ровном месте.

**Фикс.** Источник истины — `evals_and_ci.md` §3 (там полный реестр всех четырёх схем, согласованный с fixture'ами). В `agent_parser_secure_v2.md` §5.1 заменить пример `Article` на тот, что в `evals_and_ci.md` §3, и добавить примечание:

> Полный реестр Pydantic-схем для всех четырёх типов сущностей (`Article`, `DocsPage`, `Product`, `ReferenceEntry`) — в `evals_and_ci.md` §3. Этот документ показывает только пример для `Article`, чтобы не дублировать.

В коде в `src/schemas/` источник истины — `evals_and_ci.md` §3.

**Дополнительно:** в обеих версиях `Article` нет `source` (имя источника, например `"docs_python_org"`). Это поле нужно для `(source, source_id)` ключа в `canonical_records`. Решение: добавить поле `source: str` во все четыре схемы как обязательное.

Финальная форма `Article`:

```python
# src/schemas/article.py
from pydantic import BaseModel, HttpUrl, Field, field_validator
from datetime import datetime

class Article(BaseModel):
    source: str = Field(min_length=1, max_length=64)         # имя адаптера
    source_url: HttpUrl
    source_id: str = Field(min_length=1, max_length=256)     # канонический ID на источнике
    title: str = Field(min_length=1, max_length=500)
    author: str | None = None
    published_at: datetime | None = None
    body_md: str = Field(min_length=10)
    language: str = Field(pattern=r"^[a-z]{2}$")

    @field_validator("body_md")
    @classmethod
    def reject_placeholder(cls, v: str) -> str:
        markers = {"lorem ipsum", "page not found", "access denied",
                   "404", "403 forbidden", "are you a robot"}
        low = v.lower()
        for m in markers:
            if m in low:
                raise ValueError(f"body looks like placeholder/error: '{m}'")
        return v
```

Аналогично — добавить `source: str` и `source_id: str` в `DocsPage`, `Product`, `ReferenceEntry`. Обновить `evals_and_ci.md` §3 и все 20 `expected.json` fixture, где раньше было только `source_url`.

---

## E-3. `test_eval_suite.py`: баг в извлечении базового имени поля

**Файл:** `evals_and_ci.md` §8.

**Проблема.** Код:

```python
base_field = k.rsplit("_", 2)[0] if k.endswith("_min_length") \
    else k.rsplit("_", 2)[0] if k.endswith("_must_contain") \
    else k.rsplit("_", 1)[0]
```

Для ключа `body_md_min_length`:
- `k.rsplit("_", 2)` → `["body", "md_min", "length"]`. Wait, проверим: `"body_md_min_length".rsplit("_", 2)` даёт `["body_md", "min", "length"]`, `[0]` = `"body_md"`. OK тут правильно.

Но для `definition_min_length`:
- `"definition_min_length".rsplit("_", 2)` → `["definition", "min", "length"]`, `[0]` = `"definition"`. OK.

А для `definition_must_contain`:
- `"definition_must_contain".rsplit("_", 2)` → `["definition", "must", "contain"]`, `[0]` = `"definition"`. OK.

Хм, на самом деле баг не там, где я подумал. Перепроверим: для `code_block_count_min`:
- `endswith("_min")` → `True`, попадает в последнюю ветку.
- `"code_block_count_min".rsplit("_", 1)` → `["code_block_count", "min"]`, `[0]` = `"code_block_count"`. OK.

Стоп — а теперь `title_must_contain`:
- `"title_must_contain".rsplit("_", 2)` → `["title", "must", "contain"]`, `[0]` = `"title"`. OK.

Похоже, моя первоначальная диагностика была неверна: для `body_md_*` баг не возникает из-за `rsplit("_", 2)` — он схлопывает последние два «_», и `body_md` остаётся в `[0]`. Но логика всё равно хрупкая и плохо читается. Подменим на однозначные `removesuffix`:

**Фикс.**

```python
def _resolve_base_field(rule_key: str) -> str:
    for suffix in ("_min_length", "_must_contain", "_min"):
        if rule_key.endswith(suffix):
            return rule_key.removesuffix(suffix)
    raise ValueError(f"unknown soft-rule suffix: {rule_key}")
```

И в основном цикле:

```python
for k, v in expected_fields.items():
    if any(k.endswith(suf) for suf in ("_min_length", "_must_contain", "_min")):
        base_field = _resolve_base_field(k)
        _check_soft(dump.get(base_field), k, v)
    else:
        assert str(dump.get(k)) == str(v), \
            f"field {k}: got {dump.get(k)!r}, expected {v!r}"
```

**Acceptance:** unit-тест `test_resolve_base_field` на наборе пар (`body_md_min_length` → `body_md`, `definition_must_contain` → `definition`, `code_block_count_min` → `code_block_count`).

---

## E-4. `record_attempt` в `run.py` сохраняет validated payload вместо raw

**Файл:** `agent_parser_secure_v2.md` §11.1.

**Проблема.** В `run.py` стоит:

```python
article = extract_article(url)
raw_id = record_attempt(con, source, article.source_id,
                        url, article.model_dump(),    # ← это уже validated!
                        trace_id=s["span_id"])
```

`article.model_dump()` — это уже отвалидированный и нормализованный Pydantic-объект. Если позже выяснится, что Pydantic-схема была некорректной (валидатор слишком агрессивный, потерялось поле), восстановить original Firecrawl-payload по `raw_content` будет невозможно. Это ломает идею append-only audit, ради которой `raw_content` существует.

**Фикс.** `extract_article` должна возвращать пару `(raw_payload: dict, article: Article)`, и в `run.py` пишем raw в `record_attempt`, а validated — в `upsert_canonical`:

```python
# src/extract.py
def extract_article(url: str) -> tuple[dict, Article]:
    raw = fc.scrape(
        url,
        formats=[{"type": "json", "schema": Article.model_json_schema()}],
        only_main_content=True,
        timeout=30000,
    )
    raw_json = getattr(raw, "json", None)
    if raw_json is None:
        raise ValueError(f"empty extraction for {url}")
    article = Article.model_validate(raw_json)
    return raw_json, article
```

```python
# src/run.py
raw_payload, article = extract_article(url)
raw_id = record_attempt(con, source, article.source_id, url,
                        raw_payload,                          # ← raw, не validated
                        trace_id=s["span_id"])
upsert_canonical(con, source, article.source_id, url,
                 article.model_dump(mode="json"),             # ← validated
                 raw_id)
```

**Acceptance:** integration-тест на синтетическом fixture проверяет, что в `raw_content.raw_payload` лежит JSON, который пришёл от Firecrawl (с потенциально лишними полями), а в `canonical_records.payload` — только то, что валидно по Pydantic-схеме.

---

## E-5. `.claude/settings.json`: убрать `Bash(python -m src.run *)` из allow

**Файл:** `agent_parser_secure_v2.md` §10.3.

**Проблема.** В allow-list стоит `Bash(python -m src.run *)`. Это даёт агенту право запускать batch-скрапы — хотя по архитектуре §7 агент имеет ровно три run-time роли (`/investigate-failed`, `/onboard-source`, `/query`), и батчи запускает только человек.

**Фикс.** Удалить строку `"Bash(python -m src.run *)"` из `permissions.allow`. Запуск batch'а — отдельная команда оператора, не задача агента.

Финальный фрагмент:

```json
{
  "permissions": {
    "allow": [
      "Bash(python -m src.tools.investigate *)",
      "Bash(sqlite3 data/scraped.db -readonly *)",
      "Bash(pytest tests/**)",
      "Read(src/**)",
      "Read(config/**)",
      "Read(data/raw/**)",
      "Read(reports/**)",
      "Edit(src/sources/**)",
      "Edit(reports/investigations/**)",
      "Write(src/sources/**)",
      "Write(tests/sources/**)",
      "Write(reports/investigations/**)",
      "mcp__firecrawl__firecrawl_map",
      "mcp__firecrawl__firecrawl_scrape"
    ],
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Bash(rm *)",
      "Bash(curl *)",
      "Bash(wget *)",
      "Bash(pip install *)",
      "Bash(python -c *)",
      "Bash(python -m src.run *)",
      "Edit(src/safety/**)",
      "Edit(src/db/**)",
      "Edit(config/sources.yaml)",
      "Edit(.github/**)",
      "Edit(.claude/**)",
      "mcp__firecrawl__firecrawl_crawl"
    ],
    "defaultMode": "ask"
  },
  "model": "sonnet"
}
```

Дополнительно перенесено в deny: `Bash(wget *)`, `Bash(python -m src.run *)`, `Edit(.github/**)`, `Edit(.claude/**)` — четыре класса операций, которыми агент не должен распоряжаться без явного человеческого PR.

---

## E-6. Уточнить, что `firecrawl_crawl` deny — про MCP-канал, не про Python-импорт

**Файл:** `agent_parser_secure_v2.md` §10.3 + §4.1.

**Проблема.** В §10.3 в deny: `mcp__firecrawl__firecrawl_crawl`. В §4.1: «Имплементация для конкретного источника может использовать `firecrawl_crawl` с обязательным `limit`». На code review будет путаница: разрешено или нет?

**Фикс.** Добавить пояснение под §10.3:

> Запрет `mcp__firecrawl__firecrawl_crawl` касается прямого вызова агентом через MCP-канал. Workflow-код в `src/sources/<domain>.py` имеет право использовать рекурсивный обход через прямой Python-импорт `from firecrawl import Firecrawl` — но только с обязательным `limit`, обёрткой `CostGate` и явным review адаптера в PR. Различение: MCP-вызов — это «агент решает в рантайме»; Python-импорт — это «детерминированный код, который человек прочитал и согласовал».

В §4.1 — добавить ссылку на это пояснение.

---

## E-7. Описать контракт `extract_from_local`

**Файл:** `evals_and_ci.md` §8 (test) + `agent_parser_secure_v2.md` §5 (новый подпункт §5.4).

**Проблема.** `extract_from_local(cleaned, page_type)` упомянут в тестах, но контракт нигде не зафиксирован. Что он принимает (markdown? html? оба?), что возвращает (`dict` для `model_validate` или сразу `BaseModel`?), как себя ведёт на placeholder-страницах?

**Фикс.** Добавить в `agent_parser_secure_v2.md` §5.4:

```python
# src/extract.py (фрагмент)

from typing import Literal

PageType = Literal["article", "docs", "product", "reference"]

def extract_from_local(
    raw: str,
    page_type: PageType,
    *,
    fallback_url: str = "https://example.invalid/synthetic",
) -> dict:
    """Локальная имитация extraction-слоя для unit/eval-тестов.

    Принимает уже скачанный markdown или HTML (как пришёл бы от Firecrawl
    в формате markdown / только-main-content). НЕ делает сетевых вызовов.

    Логика:
      1. Если `raw` начинается с '<' — считаем HTML, конвертируем в markdown
         через `markdownify` (только основные теги: h1-h6, p, code, pre, ul, ol, li, a).
      2. По page_type парсим набор обязательных полей собственными regex'ами/
         html-парсерами. Это сознательная упрощённая реализация: на production
         вместо неё используется JSON-mode Firecrawl с `model_json_schema()`.
      3. Возвращает `dict`, который потом передаётся в `Schema.model_validate`.
         Если поле не найдено — кладём `None` (Pydantic решит, обязательное оно или нет).

    Не делает: anti-bot обход, retry, сетевые вызовы, post-processing на LLM.

    Используется только в тестах (`tests/eval/`, `tests/safety/`). В run-time
    используется `extract_via_firecrawl`, которая обёрнута в `CostGate`,
    sanitize-слой и trace.
    """
```

И в `evals_and_ci.md` §8 — заменить `from src.extract import extract_from_local` на тот же импорт + ссылку на новую секцию §5.4.

**Acceptance:** контракт зафиксирован; на ревью PR с `src/extract.py` понятно, что `extract_from_local` — это test double, а не production-путь.

---

## E-8. Fixture #20 (prompt injection): комментарий про чувствительность к конвертеру

**Файл:** `evals_and_ci.md` §6.4.

**Проблема.** Тест ожидает `expected_sanitize_warnings: ["role_prefix_neutralized", "injection_hint_detected"]`. `ROLE_PREFIXES` regex срабатывает только если префикс в начале строки (`^\s*(system|...)\s*:`, `MULTILINE`). Если html→md конвертер схлопнет `<p>system: ignore...</p>` в один абзац с предыдущим текстом без переноса — префикс окажется не в начале строки и `role_prefix_neutralized` не сработает.

**Фикс.** Добавить в `evals_and_ci.md` §6.4 после JSON expected'а:

> Замечание для имплементатора `extract_from_local`. Тест опирается на то, что html→md-конвертер сохраняет `<p>` как абзац с переносом строки (стандартное поведение `markdownify`). Если кастомный конвертер этого не делает (например, объединяет соседние `<p>` без `\n\n`), regex `ROLE_PREFIXES` не сработает и eval упадёт. Это ожидаемое поведение fixture'а: он одновременно тестирует и sanitize-слой, и инвариант на конвертер.

И в `src/safety/sanitize.py` оставить комментарий выше `ROLE_PREFIXES`, что регулярка опирается на `MULTILINE` + наличие `\n` перед префиксом.

---

---

## E-9. Имя файла `agent_parser_secure_v2.md` vs `agent_parser_secure_ver2.md`

**Файлы:** все ссылающиеся на полную инструкцию (`PROJECT_OVERVIEW.md`, `CURRENT_STATUS.md`, `ARCHITECTURE.md`, `TECH_STACK.md`, `IMPLEMENTATION_ROADMAP.md`, `ERRATA.md`).

**Проблема.** В docs ссылаются на `agent_parser_secure_v2.md`, но фактический файл загружен как `agent_parser_secure_ver2.md`. На любом case-sensitive файловом ресольвере (Linux CI) ссылки в docs не разрешатся.

**Фикс.** Переименовать файл в репо в `agent_parser_secure_v2.md` (короче, совпадает с принятой во всех docs нотацией). Действие — `git mv agent_parser_secure_ver2.md agent_parser_secure_v2.md`. После этого `grep -rn "agent_parser_secure_ver2" .` обязан возвращать пусто.

**Acceptance.** Все ссылки в `docs/*.md` и в корневых `*.md` ведут на существующий путь.

---

## E-10. CLAUDE.md: `data/raw_content` — это не путь, а имя таблицы

**Файл:** `agent_parser_secure_v2.md` §10.2 (блок CLAUDE.md, секция «Запреты»).

**Проблема.** Строка `НЕ удаляй ничего из data/raw_content и data/traces — это аудит`. `raw_content` — имя таблицы SQLite в `data/scraped.db`, не путь на ФС. Эта формулировка путает агента: если он попытается выполнить `rm data/raw_content` — увидит, что файла нет, и может «починить» это, удалив базу целиком.

**Фикс.** Переписать строку явно, разделяя ФС-объекты и таблицы:

```markdown
- НЕ удаляй и не модифицируй `data/scraped.db` (там append-only таблицы `raw_content` и `change_history` — это аудит).
- НЕ удаляй файлы из `data/traces/` и `data/raw/`.
```

**Acceptance.** В `CLAUDE.md` нет упоминания `data/raw_content` как пути.

---

---

## E-11. `architecture.mermaid` упоминается в трёх документах, но в репо отсутствует

**Файлы:** `docs/ARCHITECTURE.md` §1, `docs/CURRENT_STATUS.md` (раздел «Что готово»), `agent_parser_secure_v2.md` §2.

**Проблема.** Все три документа ссылаются на `architecture.mermaid` как существующий артефакт «в корне репо». На момент фиксации Phase 0 файла нет — это призрачная ссылка. Любой новый разработчик, который попробует открыть `architecture.mermaid` после клонирования, получит «file not found» и потеряет доверие к остальной документации.

**Фикс.** Поместить минимальный черновик `architecture.mermaid` в корень репо. Содержимое подготовлено в `outputs/architecture.mermaid` — это flowchart по шести слоям ровно как описано в `docs/ARCHITECTURE.md` §3–§8. Черновик намеренно простой: 6 subgraph'ов, основные узлы, потоки данных, cross-cutting safety perimeter. Дальнейшие итерации — отдельные PR.

`docs/CURRENT_STATUS.md` обновлён в составе этой ERRATA: упоминание `architecture.mermaid` перенесено из «Что готово» в «Что НЕ готово» с ссылкой на черновик. После того как черновик попадёт в корень репо коммитом Этапа 0 — строка возвращается обратно в «Что готово».

**Acceptance.** `ls architecture.mermaid` в корне репо возвращает файл; `mermaid-cli` или `mmdc -i architecture.mermaid -o /tmp/test.svg` рендерит без синтаксических ошибок (опционально, не блокер); `grep -rn "architecture.mermaid" .` находит ссылки только в трёх документах, упомянутых выше.

---

## Чек-лист применения ERRATA

Перед тем как закрыть Этап 0 коммитом:

- [x] E-1: `sanitize.py` — `\u`-escape sequences, литералы запрещены code-review-правилом.
- [x] E-2: все четыре Pydantic-схемы имеют `source`, `source_id`, `source_url`. `evals_and_ci.md` §3 + 20 `expected.json` обновлены.
- [x] E-3: `_resolve_base_field` через `removesuffix`, unit-тест добавлен.
- [x] E-4: `extract_article` возвращает `(raw_payload, article)`; `record_attempt` пишет raw, `upsert_canonical` пишет validated.
- [x] E-5: `Bash(python -m src.run *)` удалён из allow, добавлен в deny; добавлены deny `wget`, `Edit(.github/**)`, `Edit(.claude/**)`.
- [x] E-6: пояснение про MCP vs Python-импорт добавлено в §10.3 и §4.1.
- [x] E-7: контракт `extract_from_local` зафиксирован в §5.4 `agent_parser_secure_v2.md`.
- [x] E-8: комментарий про `ROLE_PREFIXES`-чувствительность добавлен в `evals_and_ci.md` §6.4.
- [x] E-9: файл переименован в `agent_parser_secure_v2.md`; `grep -rn "agent_parser_secure_ver2"` пусто.
- [x] E-10: `CLAUDE.md` различает SQLite-таблицы и пути ФС.
- [x] E-11: `architecture.mermaid` положен в корень репо; `docs/CURRENT_STATUS.md` ссылается на него обратно из «Что готово».

После применения — `git commit -m "docs: apply ERRATA, sync schemas, fix sanitize regex (E-1..E-10)"`. Дальше можно стартовать Этап 1.

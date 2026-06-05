# HANDOFF — agent-parser, Phase 7: new source, user manual, onboarding rejections

## Дата

2026-06-05

## TL;DR

Сессия добавила четвёртый источник (`scrapethissite_com`), написала пользовательский
мануал и зафиксировала два обоснованных отказа от онбординга (`openai.com`, `jovianarchive.com`).
DB выросла с 80 до **86 canonical**. Тестовый baseline вырос с 155 до **163**.
Открытых `validation_failed` нет.

## Что сделано в этой сессии

| Артефакт | Статус |
|---|---|
| `src/sources/scrapethissite_com.py` | merged в `main` |
| `tests/sources/test_scrapethissite_com.py` | merged в `main` |
| `config/sources.yaml` — запись `www.scrapethissite.com` | добавлена оператором вручную |
| `docs/USER_MANUAL.md` | создан, ожидает PR |
| linter-fixup scrapethissite + sources.yaml | ожидает PR (`chore/scrapethissite-post-merge-fixup`) |

## Новый источник: scrapethissite_com

- **Домен:** `www.scrapethissite.com`
- **page_type:** `reference`
- **Seeds:** 6 URL (`/pages/` index + 5 sandbox-страниц)
- **robots.txt:** Allow `/pages/**`; Disallow `/lessons/`, `/faq/`
- **Legal basis:** публичный scraping-sandbox, создан специально для практики парсинга
- **Тесты:** 8 unit (все прошли)
- **Первый батч:** 6/6 canonical, 0 vf, 30 кредитов (`root_span_id=68f753621b71409fa1615dd82c45bade`)

### parse_id edge case

Корневая страница `/pages/` возвращает `"index"` вместо пустой строки — пустой `source_id`
не прошёл бы `Field(min_length=1)` в `ReferenceEntry`.

## Отклонённые онбординги

### openai.com

- **robots.txt:** Allow: / ✓
- **Причина отказа:** ToS содержит явный запрет: *«Automatically or programmatically extract
  data or Output»*, распространяется на сайты OpenAI включая openai.com/news.
- **Вывод:** robots.txt разрешение ≠ ToS разрешение. Клауза ToS имеет приоритет.

### jovianarchive.com

- **robots.txt:** Allow: / ✓, `/products/**` и `/collections/**` открыты
- **Причина отказа:** сайт предоставляет публичный machine-readable API:
  `GET /products/{handle}.json`, `GET /collections/{handle}/products.json`,
  `POST /api/ucp/mcp` (UCP/MCP endpoint), задокументированный в `/agents.md`.
  По проектному принципу: «если у площадки есть публичный API — используем его,
  scrape не альтернатива API».
- **Вывод:** для Shopify-магазинов с product JSON API нужен HTTP-адаптер без Firecrawl.
  Это архитектурная задача: `_http_base.py` + адаптер поверх него. В backlog.

## Текущее состояние репо

DB (`data/scraped.db`, gitignored):

- `developer_mozilla_org`: **34 canonical**, 0 unresolved vf
- `docs_python_org`: **27 canonical**, 0 unresolved vf
- `anthropic_news`: **19 canonical**, 0 unresolved vf
- `scrapethissite_com`: **6 canonical**, 0 unresolved vf
- **TOTAL: 86 canonical**, 0 unresolved validation_failed

Tests: **163 total** (155 unit + 8 новых для scrapethissite, 25 eval не менялись).
`config/sources.yaml`: 4 источника.
`main` после merge двух PR этой сессии.

## Открытые TODO

1. **TODO #3 (MDN timeout monitor)** — без изменений. Три URL под наблюдением
   (`Promise`, `Fetch_API/Using_Fetch`, `Headers/Cache-Control`). Порог эскалации:
   >1/3 батчей подряд с timeout'ами → поднять `wait_for` или `timeout` в `extract.py`.

2. **TODO #8 (HTTP-адаптер без Firecrawl)** — новый. Нужен для источников с публичным
   product/content JSON API (пример: jovianarchive.com / любой Shopify-магазин).
   Потребует: `src/sources/_http_base.py`, обновление `src/run.py` (ветвление по типу
   адаптера), новый тип cost-учёта (HTTP-вызовы не в кредитах Firecrawl).

## Ожидающие PR (открыть оператором)

```powershell
# 1. linter-fixup + sources.yaml
git checkout -b chore/scrapethissite-post-merge-fixup
git add src/sources/scrapethissite_com.py tests/sources/test_scrapethissite_com.py config/sources.yaml
git commit -m "chore(sources): ruff format fixup + add scrapethissite to allow-list"
git push -u origin chore/scrapethissite-post-merge-fixup

# 2. user manual
git checkout main && git pull --ff-only
git checkout -b docs/add-user-manual
git add docs/USER_MANUAL.md
git commit -m "docs: add beginner user manual"
git push -u origin docs/add-user-manual
```

## Заметки для следующей сессии

- **4 источника в allow-list.** Следующий осмысленный шаг — MDN-батч (закрытие TODO #3)
  или новый источник.
- **jovianarchive.com — в backlog** как кандидат на HTTP-адаптер. Сайт имеет полноценный
  Shopify product JSON API и UCP/MCP endpoint.
- **openai.com — не онбордить** без явного изменения ToS с их стороны.
- **Run-time роли неизменны:** `/investigate-failed`, `/onboard-source`, `/query`.
- **`scripts/resolve_vf.py`** — стандартный инструмент для vf-резолюций.
- **`docs/USER_MANUAL.md`** — пользовательский мануал для начинающих, охватывает
  все команды, структуру БД, safety-слой, CostGate, типичные проблемы.

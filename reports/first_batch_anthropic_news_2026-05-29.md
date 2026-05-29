# First end-to-end batch report — www.anthropic.com

## Дата

2026-05-29

## Scope

Первый production-batch на третьем онбординг-нутом источнике (anthropic.com/news). Адаптер `src/sources/anthropic_news.py` (commit `f7ee936`), `page_type=article` — **первый Article-source в production-path** (до этого validate-цикл шёл только на DocsPage: docs.python.org, MDN). Опирается на RFC 9309 robots-фикс (`16078ca`) и два schema-фикса, потребовавшихся по итогам предварительных прогонов: `_normalise_published_at` (`83c48bb`) для human-readable дат и `_normalise_language` (`69d689b`) для full-name → ISO кодов.

## Результат

| Metric                                  | Value                                  |
|-----------------------------------------|----------------------------------------|
| canonical_records                       | 7                                      |
| validation_failed (unresolved)          | 0                                      |
| validation_failed (historic, resolved)  | 3                                      |
| skipped_robots                          | 0                                      |
| errors                                  | 1                                      |
| credits_used                            | 35 / 50                                |
| root_span_id                            | `17e457ef609c4bca80f367140198d997`     |
| trace file                              | `data/traces/20260529.jsonl`           |
| change_history rows                     | 6 (re-upsert audit noise, ADR 0001)    |

7 из 8 seed-URL прошли end-to-end: Firecrawl JSON-mode → `Article.model_validate` → `record_attempt` → `upsert_canonical`. 1 URL (`core-views-on-ai-safety`) упал в `fetch_via_firecrawl` внутри батча — детали в секции «Known issue» ниже.

## Processed URLs

| source_id                            | URL                                                                | published_at | author      | body_md (bytes) |
|--------------------------------------|--------------------------------------------------------------------|--------------|-------------|-----------------|
| `anthropic-acquires-stainless`       | `https://www.anthropic.com/news/anthropic-acquires-stainless`      | 2026-05-18   | `None`      | 1732            |
| `automated-alignment-researchers`    | `https://www.anthropic.com/news/automated-alignment-researchers`   | 2026-04-14   | `None`      | 4237            |
| `claude-is-a-space-to-think`         | `https://www.anthropic.com/news/claude-is-a-space-to-think`        | 2026-02-04   | `None`      | 8048            |
| `claude-opus-4-7`                    | `https://www.anthropic.com/news/claude-opus-4-7`                   | 2026-04-16   | `None`      | 17861           |
| `claude-sonnet-4-6`                  | `https://www.anthropic.com/news/claude-sonnet-4-6`                 | 2026-02-17   | `Anthropic` | 16070           |
| `clio`                               | `https://www.anthropic.com/news/clio`                              | 2024-12-12   | `Anthropic` | 5663            |
| `the-case-for-targeted-regulation`   | `https://www.anthropic.com/news/the-case-for-targeted-regulation`  | 2024-10-31   | `Anthropic` | 11174           |

## Known issue: `core-views-on-ai-safety`

URL: `https://www.anthropic.com/news/core-views-on-ai-safety`.

Поведение: дважды в batch-контексте (2026-05-26 и 2026-05-29) этот URL отметился `+1` в счётчике `errors`, при этом trace-span `scrape` обе попытки `status: ok` с длительностью ~121 секунды. Объяснение в архитектуре: `except Exception` на `run.py:79` ловит исключение из `fetch_via_firecrawl` внутри `with span(...)`, инкрементирует `counts["errors"]`, `continue` чисто выходит из контекста span'а — поэтому span помечается `ok`. `raw_content` для этого URL не записан (исключение случилось до `record_attempt`).

Изолированный вызов `fetch_via_firecrawl` на тот же URL (вне batch'а, отдельным Python-процессом, 2026-05-29) — **успешен**: 8 полей, title `'Core Views on AI Safety: When, Why, What, and How'`, `body_md=3406` байт. То есть страница и Firecrawl JSON-mode сами по себе работают; провал воспроизводится **только в batch-контексте**.

Текст исключения из batch-прогона в stdout не сохранён — `except Exception` на `run.py:79` не логирует exception (observability gap, см. follow-up #B). Длительность 121с в обоих прогонах примерно соответствует SDK-ретраям (`timeout=30000ms` × 3-4 attempt с backoff'ом), но это рабочая гипотеза, не подтверждённый root-cause.

Решение для этого batch'а: принять 7/8 и зафиксировать core-views как known-flaky в текущей конфигурации. Третий fix-PR ради одного URL с неустановленной причиной — overshoot; retry-логика в `run.py` либо подкрутка SDK retry-config — это safety-perimeter и cost-discipline, отдельная архитектурная работа (см. follow-up #A).

## Sanity observations

1. **Оба schema-фикса работают эмпирически.** `_normalise_published_at` (`83c48bb`) — все 7 записей имеют валидный `published_at` в диапазоне `2024-10-31`–`2026-05-18` (Firecrawl LLM возвращает human-форматы вида «Apr 16, 2026», валидатор нормализует в ISO date-only до Pydantic). `_normalise_language` (`69d689b`) — clio и anthropic-acquires-stainless, которые валились на `'English'` в прошлом прогоне, в этот раз прошли с корректным `language='en'`.

2. **First Article-source в production-path подтверждён.** До этого batch'а validate-цикл проходил только на DocsPage. Article-схема (`source`, `source_url`, `source_id`, `title`, `author`, `published_at`, `body_md`, `language`) валидируется на реальном контенте без правок самой схемы — все правки были в нормализаторах перед валидацией.

3. **`author` — паттерн в данных.** 4/7 — `None` (unsigned org posts, ровно как описано в handoff'е по структуре anthropic-страниц); 3/7 — `'Anthropic'`. На странице реальной human-byline нет ни у одной записи — `'Anthropic'` это интерпретация Firecrawl LLM (org-level attribution). Article-схема `author: str | None = None` принимает оба варианта корректно. Если нужна строгая семантика «без byline → None» — см. follow-up #D.

4. **RFC 9309 robots-фикс — `skipped_robots=0`.** За прогон ни одной блокировки по robots.txt; WARNING'ов в `is_allowed` не наблюдалось. Anthropic CDN в этот раз отдал 200 на `/robots.txt` (предыдущие прогоны видели интермиттентный 403, который `16078ca` корректно переваривал как allow-all per §2.3.1.4).

5. **CostGate под контролем.** 35 кредитов потрачено при cap 50. Запас с учётом одного провалившегося fetch (~3-4 SDK-ретрая по 5 кредитов на attempt при таймаутном поведении).

6. **`change_history` — 6 строк, audit noise.** Не настоящие изменения контента, а артефакт повторных upsert'ов между прогонами (05-26 частичный 5/8 → 05-29 финальный 7/8) — поля diff'нулись на повторной обработке тех же URL (вероятно `published_at` после нормализации и/или мелкие вариации `body_md` между фетчами). По ADR 0001 (`docs/adr/0001-change-history-noise.md`) это accepted audit cost.

7. **3 historic `validation_failed` помечены `resolution='fixed'`.** opus (id=1, detected 2026-05-25, pre-fix `published_at`) — закрыт коммитом `83c48bb` и подтверждён повторной валидацией (новый raw_id в canonical). clio (id=2) и stainless (id=3, оба detected 2026-05-26, pre-fix `language`) — закрыты коммитом `69d689b` и подтверждены этим прогоном. Очередь `WHERE resolved_at IS NULL` пустая.

8. **Trace persistence.** Batch span `17e457ef609c4bca80f367140198d997` и 8 child scrape-спанов лежат в `data/traces/20260529.jsonl` — доступны для post-mortem.

## Открытые вопросы / follow-ups

- **#A. core-views batch-context flake — root-cause.** Серия изолированных прогонов (5×) для подтверждения «N/N в изоляции», затем инструментирование SDK-вызовов внутри batch'а (логирование retry / timeout / empty-response). Отдельный investigation cycle. До этого retry-логика в `run.py` не вводится.
- **#B. Observability gap в `run.py:79`.** Silent `except Exception` без `logger.exception(...)` маскирует exception text — следующий «1 error» снова потребует ручной диагностики через изолированный snippet. Мини-PR в `src/run.py`: добавить точечное логирование исключения с url и type. Помог бы здесь, поможет в будущем.
- **#C. Резолв-механизм `validation_failed`.** Текущий цикл закрыт разовым `UPDATE` (штатный жизненный цикл очереди, append-only-аудит на `raw_content`/`change_history` не нарушен). Долгосрочно — `resolve_validation_failure(con, id, *, resolution, reason)` в `src/db/store.py` (CODEOWNERS-protected) с записью в trace. Мини-PR.
- **#D. LLM-интерпретация `author`.** Firecrawl JSON-mode возвращает `'Anthropic'` для 3/7 записей при отсутствии реальной byline на странице. Если в продакшене нужна строгая семантика «no byline → None», возможные пути: `description=` в `Field('author', ...)` как подсказка LLM, либо post-process в адаптере, либо `_normalise_author` в схеме. Не блокер.
- **#E. Anthropic article coverage.** `page_type=article` в production-path зафиксирован. Расширение покрытия (firecrawl_map для большего seed-набора либо периодический refresh через `since` параметр в `list_urls`) — отдельный Phase 2+ цикл.

## Conclusion

7/8 canonical, 0 unresolved validation failures, оба нормализатора (`_normalise_published_at`, `_normalise_language`) подтверждены empirically на реальном контенте Anthropic news. Третий онбординг-нутый источник и **первый Article-source в production-path**. core-views-on-ai-safety — known-flaky в batch-контексте; диагностика и потенциальный фикс — отдельным циклом.

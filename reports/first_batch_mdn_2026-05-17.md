# First end-to-end batch report — developer.mozilla.org

## Дата

2026-05-17

## Scope

Первый production-батч на втором онбординг-нутом источнике (MDN Web Docs). Адаптер `src/sources/developer_mozilla_org.py`, page_type=docs, переиспользует `DocsPage`-схему, проверенную на `docs.python.org` в Phase 1. Адаптер и тесты добавлены в PR `phase2/onboard-mdn` — это первый реальный прогон `/onboard-source` slash-команды (Stage 12).

## Результат

| Metric              | Value |
|---------------------|-------|
| canonical_records   | 8     |
| validation_failed   | 0     |
| skipped_robots      | 0     |
| errors              | 0     |
| credits_used        | 40    |
| root_span_id        | `40761e4cf8b049cdb0fe04b44f8fc79e` |

Все 8 seed-URL'ов из `_SEEDS` обработаны end-to-end: Firecrawl JSON-mode → `DocsPage.model_validate` → `record_attempt` → `upsert_canonical`. Никаких записей в `validation_failed`, transport-ошибок или robots.txt-блокировок.

## Processed URLs

| source_id                                                | URL                                                                                          |
|----------------------------------------------------------|----------------------------------------------------------------------------------------------|
| `Web/API/EventSource`                                    | `https://developer.mozilla.org/en-US/docs/Web/API/EventSource`                               |
| `Web/API/View_Transition_API`                            | `https://developer.mozilla.org/en-US/docs/Web/API/View_Transition_API`                       |
| `Web/CSS/Reference/Properties/flex-wrap`                 | `https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/flex-wrap`            |
| `Web/CSS/Reference/Properties/justify-content`           | `https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/justify-content`      |
| `Web/CSS/Reference/Properties/z-index`                   | `https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/z-index`              |
| `Web/HTTP/Methods/GET`                                   | `https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/GET`                              |
| `Web/JavaScript/Reference/Global_Objects/ReferenceError` | `https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/ReferenceError` |
| `Web/JavaScript/Reference/Global_Objects/String/replace` | `https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/replace` |

## Sanity observations

1. **`/Reference/Properties/` сегмент в CSS-URL'ах работает.** Pre-flight в `phase2/onboard-mdn` PR флагировал эти URL'ы как подозрительные (предположение, что канонический MDN-формат — `Web/CSS/<property>` без `/Reference/Properties/`). End-to-end батч подтвердил: текущая MDN URL-структура действительно включает этот сегмент, агент при `/onboard-source` распознал её корректно. Pre-flight concern был избыточным.

2. **DocsPage-схема cross-domain работает.** Поля `title`, `section_path`, `body_md`, `code_block_count`, валидировавшиеся на `docs.python.org` в Phase 1 Stage 11b, валидируются на MDN без правок схемы. Schema-as-contract подтверждён empirically на втором источнике.

3. **Source override (TODO #8 fix из Stage 11a) отработал корректно.** Firecrawl JSON-mode hallucinations в полях `source` / `source_id` / `source_url` перезаписаны adapter-provided значениями до `record_attempt`. `canonical_records.source` всегда `developer_mozilla_org`, `source_id` всегда path-leaf после `parse_id`.

4. **CostGate под контролем.** 40 кредитов потрачено, default cap 100. Free-tier остаток после прогона — порядка 440 кредитов.

5. **Trace persistance.** Запись в `data/traces/20260517.jsonl` под `root_span_id=40761e4cf8b049cdb0fe04b44f8fc79e` — спаны доступны для post-mortem.

## Открытые вопросы / follow-ups

Блокеров нет. Ни один seed-URL не отвалился, поэтому follow-up «replace problematic seeds» не требуется — изначальный набор оказался валидным.

Дальнейшее расширение MDN coverage (через `firecrawl_map` для большего числа URL'ов, либо периодический рефреш через `since` parameter в `list_urls`) — feature work для Phase 2+ продолжения, не для этого PR.

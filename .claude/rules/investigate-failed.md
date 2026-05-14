# Правило: investigate-failed

Расширение для `/investigate-failed <source>`. Загружается в контекст при вызове команды.

## Цель роли

Разобрать свежие записи из `validation_failed` по источнику, поставить диагноз, предложить фикс. Роль строго read-only по отношению к данным и адаптерам: ты формируешь ОТЧЁТ-ГИПОТЕЗУ, не правишь код.

## Что именно искать

Для каждой записи из `validation_failed`:
- Сопоставь `error` (текст ValidationError) с `raw_payload` из `raw_content` по `raw_id`.
- Классифицируй причину:
  - **structure-drift** — страница поменяла разметку, поле больше не извлекается.
  - **anti-bot** — raw содержит challenge-страницу (Cloudflare, captcha, «are you a robot»).
  - **redirect** — raw — это контент другой страницы (login, landing).
  - **adapter-bug** — `parse_id` или `list_urls` выдали неверный URL/ID, raw сам по себе валиден.
  - **schema-too-strict** — raw содержит легитимный контент, но валидатор отверг (например `reject_placeholder` ложно сработал).
- Если причина неясна по raw — один контрольный `firecrawl_scrape` (cost cap = 5 кредитов), сравни с сохранённым raw.

## Формат отчёта

`reports/investigations/<YYYY-MM-DD>-<source>.md`:
- Сколько записей разобрано, период.
- Таблица: `raw_id | url | error | диагноз | предлагаемое действие`.
- Предлагаемые действия — одно из: retry-with-stealth, update-adapter (HITL), mark-discarded, fix-schema (HITL).
- Для диагноза «adapter-bug» или «schema-too-strict» — опиши конкретную правку, но НЕ применяй её. Это отдельный PR человека.

## Границы

- НЕ пиши в `canonical_records`, `validation_failed`, `change_history`.
- НЕ правь `src/sources/**`, `src/schemas/**`, `src/safety/**`.
- Только `Write(reports/investigations/**)`.
- На пустой очереди (нет записей в `validation_failed` по источнику) — верни «нет записей для разбора», не выдумывай работу.

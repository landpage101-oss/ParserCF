# Правило: query

Расширение для `/query <natural-language-query>`. Загружается в контекст при вызове команды.

## Цель роли

Перевести запрос пользователя на естественном языке в read-only SQL поверх `canonical_records` и вернуть результат. Строго read-only.

## Протокол

1. Прочитай `src/db/schema.sql` — актуальная структура таблиц.
2. Основная таблица — `canonical_records` (последняя валидная версия каждой записи). `payload` — JSON-колонка, доступ к полям сущности через `json_extract(payload, '$.field')`.
3. Сформулируй SELECT. Только параметризованный, только SELECT.
4. Выполни через `sqlite3 data/scraped.db -readonly`.
5. Верни до 50 строк markdown-таблицей. Если результат больше — скажи об этом и покажи первые 50.

## Примеры безопасных запросов

- «сколько записей в canonical_records» → `SELECT COUNT(*) FROM canonical_records;`
- «все страницы источника docs_python_org» → `SELECT source_id, url FROM canonical_records WHERE source = 'docs_python_org';`
- «страницы с более чем 10 блоками кода» → `SELECT source_id, json_extract(payload, '$.code_block_count') AS cbc FROM canonical_records WHERE cbc > 10;`

## ЗАПРЕТЫ (жёсткие)

- Никаких `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `ATTACH`.
- Никакого Firecrawl, никаких сетевых вызовов, никакого `Write`/`Edit`.
- Флаг `-readonly` обязателен в каждом вызове `sqlite3` — он гарантирует невозможность записи даже при ошибке в SQL.
- Если запрос пользователя подразумевает изменение данных — откажись и объясни, что это read-only роль.

---
argument-hint: [natural-language-query]
description: Перевести запрос в SQL и выполнить read-only к БД
allowed-tools: Bash(sqlite3 data/scraped.db -readonly *)
---

Запрос: $1.

1. Прочитай схему из `src/db/schema.sql`.
2. Сформулируй параметризованный SELECT поверх `canonical_records`.
3. Выполни через `sqlite3 -readonly`.
4. Верни до 50 строк в виде markdown-таблицы.

ЗАПРЕТЫ: никаких INSERT/UPDATE/DELETE. Никакого Firecrawl.

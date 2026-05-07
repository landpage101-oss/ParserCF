-- src/db/schema.sql

-- Все попытки скрапа, append-only, никогда не апдейтится
CREATE TABLE IF NOT EXISTS raw_content (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT NOT NULL,
    source_id     TEXT NOT NULL,
    url           TEXT NOT NULL,
    content_hash  TEXT NOT NULL,            -- sha256 of raw payload
    raw_payload   TEXT NOT NULL,            -- JSON, как пришло от Firecrawl
    scraped_at    TEXT NOT NULL,            -- ISO-8601 UTC
    trace_id      TEXT NOT NULL             -- ссылка на trace
);
CREATE INDEX IF NOT EXISTS idx_raw_source_id  ON raw_content(source, source_id);
CREATE INDEX IF NOT EXISTS idx_raw_hash       ON raw_content(content_hash);

-- Последняя валидная версия каждой записи
CREATE TABLE IF NOT EXISTS canonical_records (
    source        TEXT NOT NULL,
    source_id     TEXT NOT NULL,
    url           TEXT NOT NULL,
    payload       TEXT NOT NULL,            -- провалидированный JSON
    valid_from    TEXT NOT NULL,
    raw_id        INTEGER NOT NULL,         -- FK на raw_content
    PRIMARY KEY (source, source_id),
    FOREIGN KEY (raw_id) REFERENCES raw_content(id)
);

-- История изменений по полям
CREATE TABLE IF NOT EXISTS change_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT NOT NULL,
    source_id     TEXT NOT NULL,
    field         TEXT NOT NULL,
    old_value     TEXT,
    new_value     TEXT,
    changed_at    TEXT NOT NULL
);

-- Очередь записей с провалом валидации
CREATE TABLE IF NOT EXISTS validation_failed (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT NOT NULL,
    url           TEXT NOT NULL,
    raw_id        INTEGER NOT NULL,
    error         TEXT NOT NULL,
    detected_at   TEXT NOT NULL,
    resolved_at   TEXT,
    resolution    TEXT,                     -- 'fixed', 'discarded', 'source_changed'
    FOREIGN KEY (raw_id) REFERENCES raw_content(id)
);

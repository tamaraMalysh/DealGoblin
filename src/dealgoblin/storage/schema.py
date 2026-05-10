SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    title TEXT,
    added_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    rowid INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    text_raw TEXT,
    text_norm TEXT,
    source_username TEXT,
    source_title TEXT,
    author_id INTEGER,
    author_name_norm TEXT,
    dedupe_key TEXT,
    link TEXT,
    posted_at TEXT,
    ingested_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(chat_id, message_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    text_norm,
    content='messages',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, text_norm) VALUES (new.rowid, new.text_norm);
END;

CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, text_norm)
        VALUES('delete', old.rowid, old.text_norm);
END;

CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, text_norm)
        VALUES('delete', old.rowid, old.text_norm);
    INSERT INTO messages_fts(rowid, text_norm) VALUES (new.rowid, new.text_norm);
END;

CREATE TABLE IF NOT EXISTS bot_users (
    id INTEGER PRIMARY KEY,
    tg_user_id INTEGER,
    chat_id INTEGER UNIQUE NOT NULL,
    city TEXT NOT NULL DEFAULT 'Тбилиси',
    subscription TEXT NOT NULL DEFAULT 'FREE',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS search_sessions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES bot_users(id) ON DELETE CASCADE,
    raw_query TEXT NOT NULL,
    fts_query TEXT NOT NULL,
    snapshot_max_rowid INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS watches (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES bot_users(id),
    name TEXT NOT NULL,
    fts_query TEXT NOT NULL,
    price_min REAL,
    price_max REAL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS match_events (
    id INTEGER PRIMARY KEY,
    watch_id INTEGER NOT NULL REFERENCES watches(id),
    message_rowid INTEGER NOT NULL,
    notified_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(watch_id, message_rowid)
);
"""

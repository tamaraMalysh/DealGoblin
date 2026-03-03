from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

from dealgoblin.ingest.normalize import TEXT_NORMALIZATION_VERSION, normalize_text
from dealgoblin.storage.schema import SCHEMA_SQL

logger = logging.getLogger(__name__)

_META_KEY_TEXT_NORMALIZATION_VERSION = "text_normalization_version"
_REINDEX_BATCH_SIZE = 500


async def _ensure_runtime_meta_table(conn: aiosqlite.Connection) -> None:
    await conn.execute(
        "CREATE TABLE IF NOT EXISTS runtime_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )


async def _get_runtime_meta(conn: aiosqlite.Connection, key: str) -> str | None:
    async with conn.execute("SELECT value FROM runtime_meta WHERE key = ?", (key,)) as cur:
        row = await cur.fetchone()
    return str(row[0]) if row else None


async def _set_runtime_meta(conn: aiosqlite.Connection, key: str, value: str) -> None:
    await conn.execute(
        "INSERT INTO runtime_meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


async def _ensure_message_dedupe_columns(conn: aiosqlite.Connection) -> None:
    async with conn.execute("PRAGMA table_info(messages)") as cur:
        rows = await cur.fetchall()
    existing_columns = {str(row[1]) for row in rows}

    if "author_id" not in existing_columns:
        await conn.execute("ALTER TABLE messages ADD COLUMN author_id INTEGER")
    if "author_name_norm" not in existing_columns:
        await conn.execute("ALTER TABLE messages ADD COLUMN author_name_norm TEXT")
    if "dedupe_key" not in existing_columns:
        await conn.execute("ALTER TABLE messages ADD COLUMN dedupe_key TEXT")


async def _ensure_runtime_indexes(conn: aiosqlite.Connection) -> None:
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_dedupe_key ON messages(dedupe_key)")
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_match_events_watch_created_at "
        "ON match_events(watch_id, created_at)"
    )


async def _reindex_messages_if_needed(conn: aiosqlite.Connection) -> None:
    current_version = await _get_runtime_meta(conn, _META_KEY_TEXT_NORMALIZATION_VERSION)
    if current_version == TEXT_NORMALIZATION_VERSION:
        return

    async with conn.execute("SELECT COUNT(*) FROM messages") as cur:
        row = await cur.fetchone()
    total_messages = int(row[0]) if row else 0

    logger.info(
        "Starting text normalization reindex to v%s for %d message(s)",
        TEXT_NORMALIZATION_VERSION,
        total_messages,
    )

    updated = 0
    last_rowid = 0
    while True:
        async with conn.execute(
            "SELECT rowid, text_raw FROM messages WHERE rowid > ? ORDER BY rowid LIMIT ?",
            (last_rowid, _REINDEX_BATCH_SIZE),
        ) as cur:
            rows = await cur.fetchall()
        if not rows:
            break

        for rowid, text_raw in rows:
            await conn.execute(
                "UPDATE messages SET text_norm = ? WHERE rowid = ?",
                (normalize_text(text_raw), rowid),
            )
            updated += 1
        last_rowid = int(rows[-1][0])
        await conn.commit()

    await _set_runtime_meta(
        conn,
        _META_KEY_TEXT_NORMALIZATION_VERSION,
        TEXT_NORMALIZATION_VERSION,
    )
    await conn.commit()
    logger.info(
        "Completed text normalization reindex to v%s: updated %d message(s)",
        TEXT_NORMALIZATION_VERSION,
        updated,
    )


async def init_db(path: str) -> aiosqlite.Connection:
    # Ensure the parent directory exists so connecting doesn't fail on first run.
    db_path = Path(path)
    if db_path.parent:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(path)
    await conn.executescript(SCHEMA_SQL)
    await _ensure_runtime_meta_table(conn)
    await _ensure_message_dedupe_columns(conn)
    await _ensure_runtime_indexes(conn)
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    await _reindex_messages_if_needed(conn)
    await conn.commit()
    return conn

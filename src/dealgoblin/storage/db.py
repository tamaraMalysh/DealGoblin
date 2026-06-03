from __future__ import annotations

import logging
import sqlite3
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from dealgoblin.ingest.normalize import TEXT_NORMALIZATION_VERSION, normalize_text
from dealgoblin.storage.schema import SCHEMA_SQL
from dealgoblin.storage.sqlite_retry import run_with_sqlite_lock_retry

logger = logging.getLogger(__name__)

_META_KEY_TEXT_NORMALIZATION_VERSION = "text_normalization_version"
_REINDEX_BATCH_SIZE = 500

_SQLITE_CORRUPTION_MARKERS = (
    "database disk image is malformed",
    "file is not a database",
    "malformed database schema",
    "database corrupt",
)


def is_sqlite_corruption_error(exc: BaseException) -> bool:
    stack: list[BaseException] = [exc]
    visited: set[int] = set()
    while stack:
        current = stack.pop()
        current_id = id(current)
        if current_id in visited:
            continue
        visited.add(current_id)

        if isinstance(current, (sqlite3.DatabaseError, sqlite3.OperationalError)):
            message = str(current).lower()
            if any(marker in message for marker in _SQLITE_CORRUPTION_MARKERS):
                return True

        cause = getattr(current, "__cause__", None)
        context = getattr(current, "__context__", None)
        if isinstance(cause, BaseException):
            stack.append(cause)
        if isinstance(context, BaseException):
            stack.append(context)
    return False


async def _assert_integrity_ok(conn: aiosqlite.Connection) -> None:
    async with conn.execute("PRAGMA quick_check") as cur:
        rows = await cur.fetchall()
    checks = [str(row[0]) for row in rows if row]
    if not checks:
        raise sqlite3.DatabaseError("database corrupt: quick_check returned no result rows")

    for check in checks:
        if check.lower() != "ok":
            raise sqlite3.DatabaseError(f"database corrupt: quick_check failed: {check}")


def _build_corrupt_backup_base_path(db_path: Path, timestamp: str) -> Path:
    base_name = f"{db_path.name}.corrupt-{timestamp}"
    candidate = db_path.with_name(base_name)
    index = 1
    while candidate.exists():
        candidate = db_path.with_name(f"{base_name}.{index}")
        index += 1
    return candidate


def _build_unique_path(path: Path) -> Path:
    candidate = path
    index = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.{index}")
        index += 1
    return candidate


def _quarantine_corrupted_db_files(db_path: Path) -> list[Path]:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_base = _build_corrupt_backup_base_path(db_path, timestamp)
    candidates = (
        (db_path, backup_base),
        (
            db_path.with_name(f"{db_path.name}-wal"),
            backup_base.with_name(f"{backup_base.name}-wal"),
        ),
        (
            db_path.with_name(f"{db_path.name}-shm"),
            backup_base.with_name(f"{backup_base.name}-shm"),
        ),
    )

    moved: list[Path] = []
    for source, target in candidates:
        if not source.exists():
            continue
        final_target = _build_unique_path(target)
        source.replace(final_target)
        moved.append(final_target)
    return moved


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

    if "source_username" not in existing_columns:
        await conn.execute("ALTER TABLE messages ADD COLUMN source_username TEXT")
    if "source_title" not in existing_columns:
        await conn.execute("ALTER TABLE messages ADD COLUMN source_title TEXT")
    if "author_id" not in existing_columns:
        await conn.execute("ALTER TABLE messages ADD COLUMN author_id INTEGER")
    if "author_name_norm" not in existing_columns:
        await conn.execute("ALTER TABLE messages ADD COLUMN author_name_norm TEXT")
    if "dedupe_key" not in existing_columns:
        await conn.execute("ALTER TABLE messages ADD COLUMN dedupe_key TEXT")


async def _ensure_message_fts_update_trigger(conn: aiosqlite.Connection) -> None:
    # Existing databases may carry the unguarded `AFTER UPDATE ON messages`
    # trigger, which re-syncs FTS for every column change (e.g. the source
    # metadata backfill). Recreate it so it only fires when `text_norm` changes.
    await conn.execute("DROP TRIGGER IF EXISTS messages_au")
    await conn.execute(
        "CREATE TRIGGER messages_au AFTER UPDATE OF text_norm ON messages "
        "WHEN old.text_norm IS NOT new.text_norm BEGIN "
        "INSERT INTO messages_fts(messages_fts, rowid, text_norm) "
        "VALUES('delete', old.rowid, old.text_norm); "
        "INSERT INTO messages_fts(rowid, text_norm) VALUES (new.rowid, new.text_norm); "
        "END"
    )


async def _ensure_runtime_indexes(conn: aiosqlite.Connection) -> None:
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_dedupe_key ON messages(dedupe_key)")
    # Session pruning deletes by `created_at < ...`; `get_for_user` looks up by
    # primary key, so a `created_at`-leading index is what actually gets used.
    await conn.execute("DROP INDEX IF EXISTS idx_search_sessions_user_created_at")
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_search_sessions_created_at ON search_sessions(created_at)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_match_events_watch_created_at "
        "ON match_events(watch_id, created_at)"
    )


async def _backfill_message_source_metadata(conn: aiosqlite.Connection) -> None:
    await conn.execute(
        "UPDATE messages AS m "
        "SET source_username = COALESCE(m.source_username, s.username), "
        "source_title = COALESCE(m.source_title, s.title) "
        "FROM sources AS s "
        "WHERE s.chat_id = m.chat_id "
        "AND (m.source_username IS NULL OR m.source_title IS NULL)"
    )


async def _ensure_message_fts_synced(conn: aiosqlite.Connection) -> None:
    async with conn.execute("SELECT COUNT(*) FROM messages") as cur:
        messages_row = await cur.fetchone()
    async with conn.execute("SELECT COUNT(*) FROM messages_fts") as cur:
        fts_row = await cur.fetchone()

    messages_count = int(messages_row[0]) if messages_row else 0
    fts_count = int(fts_row[0]) if fts_row else 0
    if messages_count == fts_count:
        return

    await conn.execute("INSERT INTO messages_fts(messages_fts) VALUES ('rebuild')")


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

        async def _update_batch(batch_rows=rows) -> None:
            for rowid, text_raw in batch_rows:
                await conn.execute(
                    "UPDATE messages SET text_norm = ? WHERE rowid = ?",
                    (normalize_text(text_raw), rowid),
                )
            await conn.commit()

        await run_with_sqlite_lock_retry(
            _update_batch,
            operation_name="messages.reindex.batch",
            on_retry=conn.rollback,
        )
        updated += len(rows)
        last_rowid = int(rows[-1][0])

    async def _store_reindex_meta() -> None:
        await _set_runtime_meta(
            conn,
            _META_KEY_TEXT_NORMALIZATION_VERSION,
            TEXT_NORMALIZATION_VERSION,
        )
        await conn.commit()

    await run_with_sqlite_lock_retry(
        _store_reindex_meta,
        operation_name="messages.reindex.meta",
        on_retry=conn.rollback,
    )
    logger.info(
        "Completed text normalization reindex to v%s: updated %d message(s)",
        TEXT_NORMALIZATION_VERSION,
        updated,
    )


async def _init_db_once(path: str, busy_timeout_ms: int) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(path, timeout=busy_timeout_ms / 1000)
    try:
        await conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.executescript(SCHEMA_SQL)
        await _ensure_runtime_meta_table(conn)
        await _ensure_message_dedupe_columns(conn)
        await _ensure_message_fts_update_trigger(conn)
        # FTS indexes only `text_norm`; adding source columns doesn't change it,
        # so let the row-count check decide whether a rebuild is actually needed.
        await _ensure_message_fts_synced(conn)
        await _backfill_message_source_metadata(conn)
        await _ensure_runtime_indexes(conn)
        await _assert_integrity_ok(conn)
        await _reindex_messages_if_needed(conn)
        await conn.commit()
        return conn
    except Exception:
        with suppress(Exception):
            await conn.close()
        raise


async def init_db(path: str, busy_timeout_ms: int = 15000) -> aiosqlite.Connection:
    # Ensure the parent directory exists so connecting doesn't fail on first run.
    if busy_timeout_ms < 1:
        raise ValueError("busy_timeout_ms must be greater than or equal to 1")
    db_path = Path(path)
    if db_path.parent:
        db_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        return await _init_db_once(path, busy_timeout_ms)
    except Exception as exc:
        if not is_sqlite_corruption_error(exc):
            raise

        moved_paths = _quarantine_corrupted_db_files(db_path)
        if moved_paths:
            logger.critical(
                "SQLite corruption detected at %s. Quarantined files: %s",
                db_path,
                ", ".join(str(path) for path in moved_paths),
            )
        else:
            logger.critical(
                "SQLite corruption detected at %s, but no database files were found to quarantine",
                db_path,
            )

        logger.critical(
            "Rebuilding SQLite database at %s after detected corruption",
            db_path,
        )
        return await _init_db_once(path, busy_timeout_ms)

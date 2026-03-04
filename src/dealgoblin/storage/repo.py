from __future__ import annotations

import sqlite3
from collections.abc import Awaitable, Callable

import aiosqlite

from dealgoblin.storage.sqlite_retry import run_with_sqlite_lock_retry


def _rows_to_dicts(cursor_description, rows):
    cols = [d[0] for d in cursor_description]
    return [dict(zip(cols, row, strict=True)) for row in rows]


async def _run_write_with_retry[T](
    db: aiosqlite.Connection,
    operation_name: str,
    operation: Callable[[], Awaitable[T]],
) -> T:
    return await run_with_sqlite_lock_retry(
        operation,
        operation_name=operation_name,
        on_retry=db.rollback,
    )


class SourceRepo:
    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def add(
        self, chat_id: int, username: str | None = None, title: str | None = None
    ) -> bool:
        async def _operation() -> bool:
            async with self._db.execute(
                "INSERT OR IGNORE INTO sources (chat_id, username, title) VALUES (?, ?, ?)",
                (chat_id, username, title),
            ) as cur:
                inserted = cur.rowcount > 0
            await self._db.commit()
            return inserted

        return await _run_write_with_retry(self._db, "sources.add", _operation)

    async def remove(self, chat_id: int):
        async def _operation() -> None:
            await self._db.execute("DELETE FROM sources WHERE chat_id = ?", (chat_id,))
            await self._db.commit()

        await _run_write_with_retry(self._db, "sources.remove", _operation)

    async def list_all(self) -> list[dict]:
        async with self._db.execute("SELECT * FROM sources ORDER BY id") as cur:
            return _rows_to_dicts(cur.description, await cur.fetchall())

    async def get_all_chat_ids(self) -> list[int]:
        async with self._db.execute("SELECT chat_id FROM sources") as cur:
            return [row[0] for row in await cur.fetchall()]

    async def sync_authoritative(self, entries: list[dict[str, int | str | None]]) -> None:
        async def _operation() -> None:
            chat_ids = [int(entry["chat_id"]) for entry in entries]
            if chat_ids:
                incoming_chat_ids = set(chat_ids)
                async with self._db.execute("SELECT chat_id FROM sources") as cur:
                    existing_chat_ids = [row[0] for row in await cur.fetchall()]

                for existing_chat_id in existing_chat_ids:
                    if existing_chat_id not in incoming_chat_ids:
                        await self._db.execute(
                            "DELETE FROM sources WHERE chat_id = ?",
                            (existing_chat_id,),
                        )
            else:
                await self._db.execute("DELETE FROM sources")

            for entry in entries:
                await self._db.execute(
                    "INSERT INTO sources (chat_id, username, title) VALUES (?, ?, ?) "
                    "ON CONFLICT(chat_id) DO UPDATE SET "
                    "username = COALESCE(excluded.username, sources.username), "
                    "title = COALESCE(excluded.title, sources.title)",
                    (
                        int(entry["chat_id"]),
                        entry.get("username"),
                        entry.get("title"),
                    ),
                )

            await self._db.commit()

        await _run_write_with_retry(self._db, "sources.sync_authoritative", _operation)


class BotUserRepo:
    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def ensure(
        self,
        chat_id: int,
        tg_user_id: int | None = None,
        city: str = "Тбилиси",
        subscription: str = "FREE",
    ) -> dict:
        async def _operation() -> None:
            await self._db.execute(
                "INSERT OR IGNORE INTO bot_users (tg_user_id, chat_id, city, subscription) "
                "VALUES (?, ?, ?, ?)",
                (tg_user_id, chat_id, city, subscription),
            )
            if tg_user_id is not None:
                await self._db.execute(
                    "UPDATE bot_users SET tg_user_id = COALESCE(tg_user_id, ?) WHERE chat_id = ?",
                    (tg_user_id, chat_id),
                )
            await self._db.commit()

        await _run_write_with_retry(self._db, "bot_users.ensure", _operation)
        async with self._db.execute("SELECT * FROM bot_users WHERE chat_id = ?", (chat_id,)) as cur:
            row = await cur.fetchone()
            return dict(zip([d[0] for d in cur.description], row, strict=True))

    async def get_by_chat_id(self, chat_id: int) -> dict | None:
        async with self._db.execute("SELECT * FROM bot_users WHERE chat_id = ?", (chat_id,)) as cur:
            row = await cur.fetchone()
            return dict(zip([d[0] for d in cur.description], row, strict=True)) if row else None

    async def get_by_id(self, user_id: int) -> dict | None:
        async with self._db.execute("SELECT * FROM bot_users WHERE id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(zip([d[0] for d in cur.description], row, strict=True)) if row else None


class MessageRepo:
    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def insert(
        self,
        chat_id: int,
        message_id: int,
        text_raw: str | None,
        text_norm: str | None,
        author_id: int | None = None,
        author_name_norm: str | None = None,
        dedupe_key: str | None = None,
        link: str | None = None,
        posted_at: str | None = None,
    ) -> int | None:
        async def _operation() -> int | None:
            try:
                async with self._db.execute(
                    "INSERT INTO messages ("
                    "chat_id, message_id, text_raw, text_norm, author_id, author_name_norm, "
                    "dedupe_key, link, posted_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        chat_id,
                        message_id,
                        text_raw,
                        text_norm,
                        author_id,
                        author_name_norm,
                        dedupe_key,
                        link,
                        posted_at,
                    ),
                ) as cur:
                    rowid = cur.lastrowid
                await self._db.commit()
                return rowid
            except sqlite3.IntegrityError:
                return None

        return await _run_write_with_retry(self._db, "messages.insert", _operation)

    async def search_fts(self, query: str, limit: int = 10) -> list[dict]:
        async with self._db.execute(
            "SELECT m.*, bm25(messages_fts) AS rank "
            "FROM messages_fts f JOIN messages m ON f.rowid = m.rowid "
            "WHERE messages_fts MATCH ? ORDER BY rank LIMIT ?",
            (query, limit),
        ) as cur:
            return _rows_to_dicts(cur.description, await cur.fetchall())

    async def get_by_rowid(self, rowid: int) -> dict | None:
        async with self._db.execute("SELECT * FROM messages WHERE rowid = ?", (rowid,)) as cur:
            row = await cur.fetchone()
            return dict(zip([d[0] for d in cur.description], row, strict=True)) if row else None

    async def count_all(self) -> int:
        async with self._db.execute("SELECT COUNT(*) FROM messages") as cur:
            row = await cur.fetchone()
            return int(row[0])

    async def count_last_24h(self) -> int:
        async with self._db.execute(
            "SELECT COUNT(*) FROM messages WHERE ingested_at >= datetime('now', '-1 day')"
        ) as cur:
            row = await cur.fetchone()
            return int(row[0])

    async def list_recent(self, limit: int, offset: int = 0) -> list[dict]:
        async with self._db.execute(
            "SELECT * FROM messages ORDER BY ingested_at DESC, rowid DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ) as cur:
            return _rows_to_dicts(cur.description, await cur.fetchall())


class WatchRepo:
    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def add(
        self,
        user_id: int,
        name: str,
        fts_query: str,
        price_min: float | None = None,
        price_max: float | None = None,
    ) -> int:
        async def _operation() -> int:
            async with self._db.execute(
                "INSERT INTO watches (user_id, name, fts_query, price_min, price_max) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, name, fts_query, price_min, price_max),
            ) as cur:
                wid = cur.lastrowid
            await self._db.commit()
            return wid

        return await _run_write_with_retry(self._db, "watches.add", _operation)

    async def list_all(self) -> list[dict]:
        async with self._db.execute("SELECT * FROM watches ORDER BY id") as cur:
            return _rows_to_dicts(cur.description, await cur.fetchall())

    async def list_for_user(self, user_id: int, limit: int = 20, offset: int = 0) -> list[dict]:
        async with self._db.execute(
            "SELECT * FROM watches WHERE user_id = ? "
            "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        ) as cur:
            return _rows_to_dicts(cur.description, await cur.fetchall())

    async def count_for_user(self, user_id: int) -> int:
        async with self._db.execute(
            "SELECT COUNT(*) FROM watches WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return int(row[0])

    async def list_enabled(self) -> list[dict]:
        async with self._db.execute("SELECT * FROM watches WHERE enabled = 1 ORDER BY id") as cur:
            return _rows_to_dicts(cur.description, await cur.fetchall())

    async def set_enabled(self, watch_id: int, enabled: bool):
        async def _operation() -> None:
            await self._db.execute(
                "UPDATE watches SET enabled = ? WHERE id = ?", (int(enabled), watch_id)
            )
            await self._db.commit()

        await _run_write_with_retry(self._db, "watches.set_enabled", _operation)

    async def remove(self, watch_id: int):
        async def _operation() -> None:
            await self._db.execute("DELETE FROM match_events WHERE watch_id = ?", (watch_id,))
            await self._db.execute("DELETE FROM watches WHERE id = ?", (watch_id,))
            await self._db.commit()

        await _run_write_with_retry(self._db, "watches.remove", _operation)

    async def remove_for_user(self, watch_id: int, user_id: int):
        async def _operation() -> None:
            await self._db.execute(
                "DELETE FROM match_events WHERE watch_id = ? "
                "AND EXISTS (SELECT 1 FROM watches w WHERE w.id = ? AND w.user_id = ?)",
                (watch_id, watch_id, user_id),
            )
            await self._db.execute(
                "DELETE FROM watches WHERE id = ? AND user_id = ?", (watch_id, user_id)
            )
            await self._db.commit()

        await _run_write_with_retry(self._db, "watches.remove_for_user", _operation)

    async def get(self, watch_id: int) -> dict | None:
        async with self._db.execute("SELECT * FROM watches WHERE id = ?", (watch_id,)) as cur:
            row = await cur.fetchone()
            return dict(zip([d[0] for d in cur.description], row, strict=True)) if row else None

    async def get_for_user(self, watch_id: int, user_id: int) -> dict | None:
        async with self._db.execute(
            "SELECT * FROM watches WHERE id = ? AND user_id = ?",
            (watch_id, user_id),
        ) as cur:
            row = await cur.fetchone()
            return dict(zip([d[0] for d in cur.description], row, strict=True)) if row else None


class MatchEventRepo:
    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def create(self, watch_id: int, message_rowid: int) -> int | None:
        async def _operation() -> int | None:
            try:
                async with self._db.execute(
                    "INSERT INTO match_events (watch_id, message_rowid) VALUES (?, ?)",
                    (watch_id, message_rowid),
                ) as cur:
                    eid = cur.lastrowid
                await self._db.commit()
                return eid
            except sqlite3.IntegrityError:
                return None

        return await _run_write_with_retry(self._db, "match_events.create", _operation)

    async def list_pending(self) -> list[dict]:
        async with self._db.execute(
            "SELECT me.*, w.name AS watch_name, w.fts_query, bu.chat_id AS owner_chat_id "
            "FROM match_events me "
            "JOIN watches w ON me.watch_id = w.id "
            "JOIN bot_users bu ON bu.id = w.user_id "
            "WHERE me.notified_at IS NULL ORDER BY me.id"
        ) as cur:
            return _rows_to_dicts(cur.description, await cur.fetchall())

    async def count_for_user(self, user_id: int) -> int:
        async with self._db.execute(
            "SELECT COUNT(*) FROM match_events me "
            "JOIN watches w ON me.watch_id = w.id "
            "WHERE w.user_id = ?",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
            return int(row[0])

    async def has_recent_duplicate(
        self,
        watch_id: int,
        dedupe_key: str,
        duplicate_suppression_days: int,
    ) -> bool:
        if duplicate_suppression_days < 1:
            return False
        since = f"-{duplicate_suppression_days} days"
        async with self._db.execute(
            "SELECT 1 FROM match_events me "
            "JOIN messages m ON m.rowid = me.message_rowid "
            "WHERE me.watch_id = ? "
            "AND m.dedupe_key = ? "
            "AND me.created_at >= datetime('now', ?) "
            "LIMIT 1",
            (watch_id, dedupe_key, since),
        ) as cur:
            row = await cur.fetchone()
            return row is not None

    async def mark_notified(self, event_id: int):
        async def _operation() -> None:
            await self._db.execute(
                "UPDATE match_events SET notified_at = datetime('now') WHERE id = ?", (event_id,)
            )
            await self._db.commit()

        await _run_write_with_retry(self._db, "match_events.mark_notified", _operation)

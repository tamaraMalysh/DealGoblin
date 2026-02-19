from __future__ import annotations

import sqlite3

import aiosqlite


def _rows_to_dicts(cursor_description, rows):
    cols = [d[0] for d in cursor_description]
    return [dict(zip(cols, row)) for row in rows]


class SourceRepo:
    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def add(self, chat_id: int, username: str | None = None, title: str | None = None):
        await self._db.execute(
            "INSERT OR IGNORE INTO sources (chat_id, username, title) VALUES (?, ?, ?)",
            (chat_id, username, title),
        )
        await self._db.commit()

    async def remove(self, chat_id: int):
        await self._db.execute("DELETE FROM sources WHERE chat_id = ?", (chat_id,))
        await self._db.commit()

    async def list_all(self) -> list[dict]:
        async with self._db.execute("SELECT * FROM sources ORDER BY id") as cur:
            return _rows_to_dicts(cur.description, await cur.fetchall())

    async def get_all_chat_ids(self) -> list[int]:
        async with self._db.execute("SELECT chat_id FROM sources") as cur:
            return [row[0] for row in await cur.fetchall()]


class MessageRepo:
    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def insert(
        self,
        chat_id: int,
        message_id: int,
        text_raw: str | None,
        text_norm: str | None,
        link: str | None = None,
        posted_at: str | None = None,
    ) -> int | None:
        try:
            async with self._db.execute(
                "INSERT INTO messages (chat_id, message_id, text_raw, text_norm, link, posted_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (chat_id, message_id, text_raw, text_norm, link, posted_at),
            ) as cur:
                rowid = cur.lastrowid
            await self._db.commit()
            return rowid
        except sqlite3.IntegrityError:
            return None

    async def search_fts(self, query: str, limit: int = 10) -> list[dict]:
        async with self._db.execute(
            "SELECT m.*, bm25(messages_fts) AS rank "
            "FROM messages_fts f JOIN messages m ON f.rowid = m.rowid "
            "WHERE messages_fts MATCH ? ORDER BY rank LIMIT ?",
            (query, limit),
        ) as cur:
            return _rows_to_dicts(cur.description, await cur.fetchall())

    async def get_by_rowid(self, rowid: int) -> dict | None:
        async with self._db.execute(
            "SELECT * FROM messages WHERE rowid = ?", (rowid,)
        ) as cur:
            row = await cur.fetchone()
            return dict(zip([d[0] for d in cur.description], row)) if row else None


class WatchRepo:
    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def add(
        self,
        name: str,
        fts_query: str,
        price_min: float | None = None,
        price_max: float | None = None,
    ) -> int:
        async with self._db.execute(
            "INSERT INTO watches (name, fts_query, price_min, price_max) VALUES (?, ?, ?, ?)",
            (name, fts_query, price_min, price_max),
        ) as cur:
            wid = cur.lastrowid
        await self._db.commit()
        return wid

    async def list_all(self) -> list[dict]:
        async with self._db.execute("SELECT * FROM watches ORDER BY id") as cur:
            return _rows_to_dicts(cur.description, await cur.fetchall())

    async def list_enabled(self) -> list[dict]:
        async with self._db.execute(
            "SELECT * FROM watches WHERE enabled = 1 ORDER BY id"
        ) as cur:
            return _rows_to_dicts(cur.description, await cur.fetchall())

    async def set_enabled(self, watch_id: int, enabled: bool):
        await self._db.execute(
            "UPDATE watches SET enabled = ? WHERE id = ?", (int(enabled), watch_id)
        )
        await self._db.commit()

    async def remove(self, watch_id: int):
        await self._db.execute("DELETE FROM match_events WHERE watch_id = ?", (watch_id,))
        await self._db.execute("DELETE FROM watches WHERE id = ?", (watch_id,))
        await self._db.commit()

    async def get(self, watch_id: int) -> dict | None:
        async with self._db.execute(
            "SELECT * FROM watches WHERE id = ?", (watch_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(zip([d[0] for d in cur.description], row)) if row else None


class MatchEventRepo:
    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def create(self, watch_id: int, message_rowid: int) -> int | None:
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

    async def list_pending(self) -> list[dict]:
        async with self._db.execute(
            "SELECT me.*, w.name AS watch_name, w.fts_query "
            "FROM match_events me JOIN watches w ON me.watch_id = w.id "
            "WHERE me.notified_at IS NULL ORDER BY me.id"
        ) as cur:
            return _rows_to_dicts(cur.description, await cur.fetchall())

    async def mark_notified(self, event_id: int):
        await self._db.execute(
            "UPDATE match_events SET notified_at = datetime('now') WHERE id = ?", (event_id,)
        )
        await self._db.commit()

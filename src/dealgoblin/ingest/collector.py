from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from telethon import TelegramClient, events

from dealgoblin.ingest.dedupe import build_dedupe_key, normalize_author_name
from dealgoblin.ingest.links import build_message_link
from dealgoblin.ingest.normalize import normalize_text
from dealgoblin.storage.repo import MessageRepo, SourceRepo

logger = logging.getLogger(__name__)


class Collector:
    def __init__(
        self,
        client: TelegramClient,
        db,
        on_ingest: Callable[[int, str], Awaitable[None]] | None = None,
    ):
        self._client = client
        self._db = db
        self._on_ingest = on_ingest
        self._source_repo = SourceRepo(db)
        self._msg_repo = MessageRepo(db)

    async def start(self, backfill_limit: int = 100):
        allowed = await self._source_repo.get_all_chat_ids()
        if not allowed:
            logger.warning("No sources configured — collector idle")
        else:
            await self.backfill_sources(limit=backfill_limit)
        self._client.add_event_handler(self._handle, events.NewMessage)
        logger.info("Collector started, watching %d sources", len(allowed))

    async def backfill_sources(self, limit: int = 100) -> None:
        if limit <= 0:
            return

        allowed = await self._source_repo.get_all_chat_ids()
        for chat_id in allowed:
            try:
                chat = await self._client.get_entity(chat_id)
            except Exception as exc:
                logger.warning("Could not load source %s for backfill: %s", chat_id, exc)
                continue

            username = getattr(chat, "username", None)
            inserted = 0
            async for msg in self._client.iter_messages(chat, limit=limit):
                rowid = await self._ingest_message(chat_id=chat_id, message=msg, username=username)
                if rowid is not None:
                    inserted += 1
            logger.info("Backfilled %d messages from source %s", inserted, chat_id)

    async def _handle(self, event: events.NewMessage.Event):
        chat_id = event.chat_id
        allowed = await self._source_repo.get_all_chat_ids()
        if chat_id not in allowed:
            logger.debug("Skipping message from chat_id=%s (allowed=%s)", chat_id, allowed)
            return
        chat = await event.get_chat()
        msg = event.message
        username = getattr(chat, "username", None)
        rowid = await self._ingest_message(chat_id=chat_id, message=msg, username=username)
        if rowid is None:
            return

    async def _ingest_message(self, chat_id: int, message, username: str | None) -> int | None:
        if not message.text:
            return None
        link = build_message_link(username, chat_id, message.id)
        text_norm = normalize_text(message.text)
        raw_author_id = getattr(message, "sender_id", None)
        author_id = int(raw_author_id) if isinstance(raw_author_id, int) else None
        author_name_norm = normalize_author_name(getattr(message, "post_author", None))
        dedupe_key = build_dedupe_key(
            text_norm=text_norm,
            author_id=author_id,
            author_name_norm=author_name_norm,
        )
        posted_at = message.date.isoformat() if message.date else None
        rowid = await self._msg_repo.insert(
            chat_id=chat_id,
            message_id=message.id,
            text_raw=message.text,
            text_norm=text_norm,
            author_id=author_id,
            author_name_norm=author_name_norm,
            dedupe_key=dedupe_key,
            link=link,
            posted_at=posted_at,
        )
        if rowid is None:
            return None
        logger.info("Ingested message %d from %s", message.id, chat_id)
        if self._on_ingest and text_norm:
            await self._on_ingest(rowid, text_norm)
        return rowid

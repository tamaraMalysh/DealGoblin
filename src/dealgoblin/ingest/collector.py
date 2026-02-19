from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from telethon import TelegramClient, events

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

    async def start(self):
        allowed = await self._source_repo.get_all_chat_ids()
        if not allowed:
            logger.warning("No sources configured — collector idle")
        self._client.add_event_handler(self._handle, events.NewMessage)
        logger.info("Collector started, watching %d sources", len(allowed))

    async def _handle(self, event: events.NewMessage.Event):
        chat = await event.get_chat()
        chat_id = event.chat_id
        allowed = await self._source_repo.get_all_chat_ids()
        if chat_id not in allowed:
            return
        msg = event.message
        if not msg.text:
            return
        username = getattr(chat, "username", None)
        link = build_message_link(username, chat_id, msg.id)
        text_norm = normalize_text(msg.text)
        posted_at = msg.date.isoformat() if msg.date else None
        rowid = await self._msg_repo.insert(
            chat_id=chat_id,
            message_id=msg.id,
            text_raw=msg.text,
            text_norm=text_norm,
            link=link,
            posted_at=posted_at,
        )
        if rowid is None:
            return  # duplicate
        logger.info("Ingested message %d from %s", msg.id, chat_id)
        if self._on_ingest and text_norm:
            await self._on_ingest(rowid, text_norm)

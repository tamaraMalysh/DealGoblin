from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from dealgoblin.storage.db import is_sqlite_corruption_error
from dealgoblin.storage.repo import MatchEventRepo, MessageRepo

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(self, bot: Bot, db, poll_interval: float = 2.0):
        self._bot = bot
        self._db = db
        self._poll_interval = poll_interval
        self._me_repo = MatchEventRepo(db)
        self._msg_repo = MessageRepo(db)
        self._running = False

    async def start(self):
        self._running = True
        logger.info("Notifier started, polling every %.1fs", self._poll_interval)
        while self._running:
            try:
                await self._poll()
            except Exception as exc:
                if is_sqlite_corruption_error(exc):
                    logger.critical("SQLite corruption detected in notifier poll; failing runtime")
                    raise
                logger.exception("Notifier poll error")
            await asyncio.sleep(self._poll_interval)

    async def stop(self):
        self._running = False

    async def _poll(self):
        pending = await self._me_repo.list_pending()
        for event in pending:
            msg = await self._msg_repo.get_by_rowid(event["message_rowid"])
            if not msg:
                await self._me_repo.mark_notified(event["id"])
                continue
            snippet = (msg.get("text_raw") or "")[:200]
            link = msg.get("link") or ""
            watch_name = event.get("watch_name", "?")
            text = f"Match: {watch_name}\n\n{snippet}\n\n{link}"
            owner_chat_id = event.get("owner_chat_id")
            if owner_chat_id is None:
                logger.warning("Event %s has no owner_chat_id, skipping", event["id"])
                await self._me_repo.mark_notified(event["id"])
                continue
            try:
                await self._bot.send_message(owner_chat_id, text)
                await self._me_repo.mark_notified(event["id"])
            except Exception:
                logger.exception("Failed to send notification for event %d", event["id"])
                break  # back off on send failure

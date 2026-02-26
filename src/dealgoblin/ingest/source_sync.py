from __future__ import annotations

import logging

from telethon import TelegramClient

from dealgoblin.storage.repo import SourceRepo

logger = logging.getLogger(__name__)


async def sync_sources_from_env(
    client: TelegramClient,
    source_repo: SourceRepo,
    chat_ids: list[int],
) -> None:
    entries: list[dict[str, int | str | None]] = []
    for chat_id in chat_ids:
        username = None
        title = None
        try:
            entity = await client.get_entity(chat_id)
            username = getattr(entity, "username", None)
            title = getattr(entity, "title", None) or username
        except Exception as exc:
            logger.warning("Could not resolve source metadata for %s: %s", chat_id, exc)
        entries.append({"chat_id": chat_id, "username": username, "title": title})

    await source_repo.sync_authoritative(entries)

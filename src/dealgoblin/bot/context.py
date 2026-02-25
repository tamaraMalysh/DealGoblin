from __future__ import annotations

import aiosqlite
from aiogram.types import Message

from dealgoblin.storage.repo import BotUserRepo, MatchEventRepo, MessageRepo, SourceRepo, WatchRepo


def get_repos(db: aiosqlite.Connection):
    return {
        "source": SourceRepo(db),
        "message": MessageRepo(db),
        "watch": WatchRepo(db),
        "event": MatchEventRepo(db),
        "user": BotUserRepo(db),
    }


async def ensure_user(db: aiosqlite.Connection, message: Message) -> dict:
    user_repo = BotUserRepo(db)
    return await user_repo.ensure(
        chat_id=message.chat.id,
        tg_user_id=message.from_user.id if message.from_user else None,
    )

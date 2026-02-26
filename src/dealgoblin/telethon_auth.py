from __future__ import annotations

from telethon import TelegramClient

BOT_SESSION_ERROR = (
    "Telethon session is authenticated as a bot account. "
    "Ingestion requires a user-authenticated Telethon session. "
    "Remove data/telethon.session* and restart, then sign in with phone/code."
)


async def ensure_user_session(client: TelegramClient) -> None:
    me = await client.get_me()
    if me is None:
        raise RuntimeError("Failed to load Telegram account from Telethon session.")
    if getattr(me, "bot", False):
        raise RuntimeError(BOT_SESSION_ERROR)

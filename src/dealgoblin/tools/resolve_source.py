from __future__ import annotations

import argparse
import asyncio
import re

from telethon import TelegramClient
from telethon import utils as tl_utils

from dealgoblin.config import Settings
from dealgoblin.telethon_auth import ensure_user_session

SOURCE_RE = re.compile(r"^https?://t\.me/([A-Za-z0-9_]+)(?:/)?$")


def normalize_source_arg(value: str) -> str:
    raw = value.strip()
    if raw.startswith("@") and len(raw) > 1:
        return raw
    match = SOURCE_RE.match(raw)
    if match:
        username = match.group(1)
        if username == "addlist":
            raise ValueError("addlist URLs are not supported by this resolver")
        return f"@{username}"
    raise ValueError("Source must be @username or https://t.me/username")


async def _run(source: str, check_history: bool) -> None:
    settings = Settings()
    telethon = TelegramClient(
        settings.session_path,
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )
    await telethon.start()
    try:
        await ensure_user_session(telethon)
        normalized = normalize_source_arg(source)
        entity = await telethon.get_entity(normalized)
        peer_id = tl_utils.get_peer_id(entity)
        username = getattr(entity, "username", None)
        title = getattr(entity, "title", None)
        print(f"input={source}")
        print(f"normalized={normalized}")
        print(f"entity_type={type(entity).__name__}")
        print(f"peer_id={peer_id}")
        if username:
            print(f"username={username}")
        if title:
            print(f"title={title}")
        if check_history:
            try:
                messages = await telethon.get_messages(entity, limit=1)
                print(f"history_readable=yes messages={len(messages)}")
            except Exception as exc:
                print(f"history_readable=no error={exc}")
    finally:
        await telethon.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resolve Telegram source link/username to canonical chat ID"
    )
    parser.add_argument("source", help="@username or https://t.me/username")
    parser.add_argument(
        "--check-history",
        action="store_true",
        help="Attempt a lightweight message history read for this source",
    )
    args = parser.parse_args()
    asyncio.run(_run(source=args.source, check_history=args.check_history))


if __name__ == "__main__":
    main()

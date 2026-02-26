from __future__ import annotations

import argparse
import asyncio
import re
from typing import Literal

from telethon import TelegramClient, functions
from telethon import utils as tl_utils

from dealgoblin.config import Settings
from dealgoblin.telethon_auth import ensure_user_session

SOURCE_RE = re.compile(r"^https?://t\.me/([A-Za-z0-9_]+)(?:/)?$")
ADDLIST_RE = re.compile(r"^https?://t\.me/addlist/([A-Za-z0-9_-]+)(?:/)?$")


def normalize_source_arg(value: str) -> str:
    source_type, source_value = parse_source_arg(value)
    if source_type == "addlist":
        raise ValueError("addlist URL is not a single source username")
    return source_value


def parse_source_arg(value: str) -> tuple[Literal["username", "addlist"], str]:
    raw = value.strip()
    if raw.startswith("@") and len(raw) > 1:
        return "username", raw
    if raw.startswith("https://t.me/addlist/") or raw.startswith("http://t.me/addlist/"):
        addlist_match = ADDLIST_RE.match(raw)
        if addlist_match:
            return "addlist", addlist_match.group(1)
        raise ValueError("Invalid addlist URL format; expected https://t.me/addlist/<slug>")
    addlist_match = ADDLIST_RE.match(raw)
    if addlist_match:
        return "addlist", addlist_match.group(1)
    match = SOURCE_RE.match(raw)
    if match:
        return "username", f"@{match.group(1)}"
    raise ValueError(
        "Source must be @username, https://t.me/username, or https://t.me/addlist/<slug>"
    )


def extract_addlist_chat_ids(invite_result: object) -> list[int]:
    chat_ids: set[int] = set()
    for attr_name in ("chats", "peers", "missing_peers", "already_peers"):
        for item in getattr(invite_result, attr_name, []) or []:
            try:
                peer_id = tl_utils.get_peer_id(item)
            except Exception:
                continue
            # DealGoblin accepts only canonical chat/channel IDs (negative values).
            if peer_id < 0:
                chat_ids.add(peer_id)
    return sorted(chat_ids)


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
        source_type, source_value = parse_source_arg(source)
        print(f"input={source}")
        if source_type == "addlist":
            invite_result = await telethon(
                functions.chatlists.CheckChatlistInviteRequest(slug=source_value)
            )
            chat_ids = extract_addlist_chat_ids(invite_result)
            print("mode=addlist")
            print(f"slug={source_value}")
            print(f"resolved_count={len(chat_ids)}")
            for chat_id in chat_ids:
                print(f"chat_id={chat_id}")
            print(f"SOURCE_CHAT_IDS={','.join(str(chat_id) for chat_id in chat_ids)}")
            if check_history:
                print("history_check=skipped (addlist mode)")
            return

        entity = await telethon.get_entity(source_value)
        peer_id = tl_utils.get_peer_id(entity)
        username = getattr(entity, "username", None)
        title = getattr(entity, "title", None)
        print(f"normalized={source_value}")
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
    parser.add_argument(
        "source",
        help="@username, https://t.me/username, or https://t.me/addlist/<slug>",
    )
    parser.add_argument(
        "--check-history",
        action="store_true",
        help="Attempt a lightweight message history read for this source",
    )
    args = parser.parse_args()
    asyncio.run(_run(source=args.source, check_history=args.check_history))


if __name__ == "__main__":
    main()

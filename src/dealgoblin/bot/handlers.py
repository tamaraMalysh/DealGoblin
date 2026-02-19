from __future__ import annotations

import logging

import aiosqlite
from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from telethon import TelegramClient
from telethon import utils as tl_utils

from dealgoblin.bot.helpers import (
    format_search_results,
    format_source_list,
    format_watch_list,
    parse_source_arg,
)
from dealgoblin.match.fts_query import build_fts_query
from dealgoblin.storage.repo import MessageRepo, SourceRepo, WatchRepo

logger = logging.getLogger(__name__)
router = Router()


def _get_repos(db: aiosqlite.Connection):
    return SourceRepo(db), MessageRepo(db), WatchRepo(db)


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("DealGoblin - Flea market finder.\nUse /help to see available commands.")


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "/sources - list sources\n"
        "/source_add <link or @username> - add source\n"
        "/source_remove <id> - remove source\n"
        "/watches - list watches\n"
        "/watch_add <name> | <include,terms> | <exclude,terms> | <min-max>\n"
        "/watch_add_fts <name> <fts_query> - add raw FTS watch\n"
        "/watch_pause <id> - pause watch\n"
        "/watch_resume <id> - resume watch\n"
        "/watch_remove <id> - remove watch\n"
        "/search <query> - search messages\n"
        "/status - service status"
    )


@router.message(Command("status"))
async def cmd_status(message: Message, db: aiosqlite.Connection):
    source_repo, _, _ = _get_repos(db)
    sources = await source_repo.list_all()
    async with db.execute("SELECT COUNT(*) FROM messages") as cur:
        msg_count = (await cur.fetchone())[0]
    await message.answer(f"Sources: {len(sources)}\nMessages indexed: {msg_count}")


@router.message(Command("sources"))
async def cmd_sources(message: Message, db: aiosqlite.Connection):
    source_repo, _, _ = _get_repos(db)
    sources = await source_repo.list_all()
    await message.answer(format_source_list(sources))


@router.message(Command("source_add"))
async def cmd_source_add(message: Message, db: aiosqlite.Connection, telethon: TelegramClient):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /source_add <t.me link or @username>")
        return
    parsed = parse_source_arg(args[1])
    if not parsed:
        await message.answer("Invalid source. Use @username or https://t.me/username")
        return
    username = parsed.lstrip("@")
    try:
        entity = await telethon.get_entity(username)
        chat_id = tl_utils.get_peer_id(entity)
        title = getattr(entity, "title", username)
    except Exception as e:
        await message.answer(f"Could not resolve {parsed}: {e}")
        return
    source_repo, _, _ = _get_repos(db)
    await source_repo.add(chat_id=chat_id, username=username, title=title)
    await message.answer(f"Added source: {title} ({chat_id})")


@router.message(Command("source_remove"))
async def cmd_source_remove(message: Message, db: aiosqlite.Connection):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /source_remove <chat_id>")
        return
    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("Provide a numeric chat_id.")
        return
    source_repo, _, _ = _get_repos(db)
    await source_repo.remove(chat_id=chat_id)
    await message.answer(f"Removed source {chat_id}.")


@router.message(Command("watches"))
async def cmd_watches(message: Message, db: aiosqlite.Connection):
    _, _, watch_repo = _get_repos(db)
    watches = await watch_repo.list_all()
    await message.answer(format_watch_list(watches))


@router.message(Command("watch_add"))
async def cmd_watch_add(message: Message, db: aiosqlite.Connection):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "Usage: /watch_add <name> | <include,terms> | <exclude,terms> | <min-max>\n"
            "Example: /watch_add lamps | lamp,lantern | broken | 100-5000"
        )
        return
    parts = [p.strip() for p in args[1].split("|")]
    name = parts[0]
    include = [t.strip() for t in parts[1].split(",")] if len(parts) > 1 else []
    exclude = [t.strip() for t in parts[2].split(",")] if len(parts) > 2 else []
    price_min, price_max = None, None
    if len(parts) > 3 and "-" in parts[3]:
        lo, hi = parts[3].split("-", 1)
        price_min = float(lo) if lo.strip() else None
        price_max = float(hi) if hi.strip() else None
    fts = build_fts_query(include=include, exclude=exclude)
    if not fts:
        await message.answer("Include at least one search term.")
        return
    _, _, watch_repo = _get_repos(db)
    wid = await watch_repo.add(name=name, fts_query=fts, price_min=price_min, price_max=price_max)
    await message.answer(f"Watch #{wid} '{name}' created: {fts}")


@router.message(Command("watch_add_fts"))
async def cmd_watch_add_fts(message: Message, db: aiosqlite.Connection):
    args = (message.text or "").split(maxsplit=2)
    if len(args) < 3:
        await message.answer("Usage: /watch_add_fts <name> <fts_query>")
        return
    _, _, watch_repo = _get_repos(db)
    wid = await watch_repo.add(name=args[1], fts_query=args[2])
    await message.answer(f"Watch #{wid} '{args[1]}' created: {args[2]}")


@router.message(Command("watch_pause"))
async def cmd_watch_pause(message: Message, db: aiosqlite.Connection):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /watch_pause <id>")
        return
    _, _, watch_repo = _get_repos(db)
    await watch_repo.set_enabled(int(args[1]), False)
    await message.answer(f"Watch #{args[1]} paused.")


@router.message(Command("watch_resume"))
async def cmd_watch_resume(message: Message, db: aiosqlite.Connection):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /watch_resume <id>")
        return
    _, _, watch_repo = _get_repos(db)
    await watch_repo.set_enabled(int(args[1]), True)
    await message.answer(f"Watch #{args[1]} resumed.")


@router.message(Command("watch_remove"))
async def cmd_watch_remove(message: Message, db: aiosqlite.Connection):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /watch_remove <id>")
        return
    _, _, watch_repo = _get_repos(db)
    await watch_repo.remove(int(args[1]))
    await message.answer(f"Watch #{args[1]} removed.")


@router.message(Command("search"))
async def cmd_search(message: Message, db: aiosqlite.Connection):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /search <query>")
        return
    _, msg_repo, _ = _get_repos(db)
    results = await msg_repo.search_fts(args[1], limit=10)
    await message.answer(format_search_results(results))
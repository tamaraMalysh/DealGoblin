from __future__ import annotations

import aiosqlite
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from dealgoblin.bot.callbacks import (
    HelpCallback,
    HistoryCallback,
    KeywordsCallback,
    MenuCallback,
    SettingsCallback,
)
from dealgoblin.bot.context import ensure_user, get_repos
from dealgoblin.bot.handlers_keywords import render_keywords_screen
from dealgoblin.bot.helpers import (
    format_search_results,
    format_source_list,
    format_watch_list,
)
from dealgoblin.bot.ui import (
    HISTORY_PAGE_SIZE,
    help_info_text,
    help_markup,
    help_secondary_markup,
    help_support_text,
    help_text,
    history_markup,
    history_text,
    main_menu_markup,
    main_menu_text,
    settings_markup,
    settings_text,
    stats_markup,
    stats_text,
)
from dealgoblin.match.fts_query import build_fts_query

router = Router()


async def render_main_menu(message: Message) -> None:
    await message.answer(main_menu_text(), reply_markup=main_menu_markup())


async def render_settings_screen(query: CallbackQuery, db: aiosqlite.Connection) -> None:
    user = await ensure_user(db, query.message)
    repos = get_repos(db)
    watch_count = await repos["watch"].count_for_user(user["id"])
    found_count = await repos["event"].count_for_user(user["id"])
    await query.message.edit_text(
        settings_text(user=user, watch_count=watch_count, found_count=found_count),
        reply_markup=settings_markup(),
    )


async def render_stats_screen(query: CallbackQuery, db: aiosqlite.Connection) -> None:
    repos = get_repos(db)
    sources = await repos["source"].list_all()
    total_messages = await repos["message"].count_all()
    recent_messages = await repos["message"].count_last_24h()
    await query.message.edit_text(
        stats_text(
            sources_count=len(sources),
            messages_count=total_messages,
            last_24h_count=recent_messages,
        ),
        reply_markup=stats_markup(),
    )


async def render_history_screen(query: CallbackQuery, db: aiosqlite.Connection, page: int) -> None:
    repos = get_repos(db)
    total = await repos["message"].count_all()
    offset = (page - 1) * HISTORY_PAGE_SIZE
    messages = await repos["message"].list_recent(limit=HISTORY_PAGE_SIZE, offset=offset)
    await query.message.edit_text(
        history_text(messages=messages, page=page, total=total),
        reply_markup=history_markup(page=page, total=total),
    )


@router.message(CommandStart())
async def cmd_start(message: Message, db: aiosqlite.Connection):
    await ensure_user(db, message)
    await render_main_menu(message)


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(help_text(), reply_markup=help_markup())


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    await render_main_menu(message)


@router.callback_query(MenuCallback.filter(F.action == "back"))
async def menu_back(query: CallbackQuery):
    await query.message.edit_text(main_menu_text(), reply_markup=main_menu_markup())
    await query.answer()


@router.callback_query(MenuCallback.filter(F.action == "settings"))
async def menu_settings(query: CallbackQuery, db: aiosqlite.Connection):
    await render_settings_screen(query, db)
    await query.answer()


@router.callback_query(MenuCallback.filter(F.action == "stats"))
async def menu_stats(query: CallbackQuery, db: aiosqlite.Connection):
    await render_stats_screen(query, db)
    await query.answer()


@router.callback_query(MenuCallback.filter(F.action == "history"))
async def menu_history(query: CallbackQuery, db: aiosqlite.Connection):
    await render_history_screen(query, db, page=1)
    await query.answer()


@router.callback_query(MenuCallback.filter(F.action == "help"))
async def menu_help(query: CallbackQuery):
    await query.message.edit_text(help_text(), reply_markup=help_markup())
    await query.answer()


@router.callback_query(SettingsCallback.filter(F.action == "keywords"))
async def settings_keywords(query: CallbackQuery, db: aiosqlite.Connection):
    await render_keywords_screen(query, db, page=1)
    await query.answer()


@router.callback_query(SettingsCallback.filter(F.action == "back"))
async def settings_back(query: CallbackQuery):
    await query.message.edit_text(main_menu_text(), reply_markup=main_menu_markup())
    await query.answer()


@router.callback_query(KeywordsCallback.filter(F.action == "back"))
async def keywords_back(query: CallbackQuery, db: aiosqlite.Connection):
    await render_settings_screen(query, db)
    await query.answer()


@router.callback_query(HelpCallback.filter(F.action == "info"))
async def help_info(query: CallbackQuery):
    await query.message.edit_text(help_info_text(), reply_markup=help_secondary_markup())
    await query.answer()


@router.callback_query(HelpCallback.filter(F.action == "support"))
async def help_support(query: CallbackQuery):
    await query.message.edit_text(help_support_text(), reply_markup=help_secondary_markup())
    await query.answer()


@router.callback_query(HelpCallback.filter(F.action == "back"))
async def help_back(query: CallbackQuery):
    await query.message.edit_text(main_menu_text(), reply_markup=main_menu_markup())
    await query.answer()


@router.callback_query(HistoryCallback.filter())
async def history_page(
    query: CallbackQuery, callback_data: HistoryCallback, db: aiosqlite.Connection
):
    await render_history_screen(query, db, page=callback_data.page)
    await query.answer()


@router.message(Command("status"))
async def cmd_status(message: Message, db: aiosqlite.Connection):
    repos = get_repos(db)
    sources = await repos["source"].list_all()
    msg_count = await repos["message"].count_all()
    await message.answer(f"Sources: {len(sources)}\nMessages indexed: {msg_count}")


@router.message(Command("sources"))
async def cmd_sources(message: Message, db: aiosqlite.Connection):
    sources = await get_repos(db)["source"].list_all()
    await message.answer(format_source_list(sources))


@router.message(Command("watches"))
async def cmd_watches(message: Message, db: aiosqlite.Connection):
    user = await ensure_user(db, message)
    watches = await get_repos(db)["watch"].list_for_user(user["id"], limit=200)
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
    user = await ensure_user(db, message)
    wid = await get_repos(db)["watch"].add(
        user_id=user["id"],
        name=name,
        fts_query=fts,
        price_min=price_min,
        price_max=price_max,
    )
    await message.answer(f"Watch #{wid} '{name}' created: {fts}")


@router.message(Command("watch_add_fts"))
async def cmd_watch_add_fts(message: Message, db: aiosqlite.Connection):
    args = (message.text or "").split(maxsplit=2)
    if len(args) < 3:
        await message.answer("Usage: /watch_add_fts <name> <fts_query>")
        return
    user = await ensure_user(db, message)
    wid = await get_repos(db)["watch"].add(user_id=user["id"], name=args[1], fts_query=args[2])
    await message.answer(f"Watch #{wid} '{args[1]}' created: {args[2]}")


@router.message(Command("watch_pause"))
async def cmd_watch_pause(message: Message, db: aiosqlite.Connection):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /watch_pause <id>")
        return
    user = await ensure_user(db, message)
    watch = await get_repos(db)["watch"].get_for_user(int(args[1]), user["id"])
    if not watch:
        await message.answer("Watch not found.")
        return
    await get_repos(db)["watch"].set_enabled(int(args[1]), False)
    await message.answer(f"Watch #{args[1]} paused.")


@router.message(Command("watch_resume"))
async def cmd_watch_resume(message: Message, db: aiosqlite.Connection):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /watch_resume <id>")
        return
    user = await ensure_user(db, message)
    watch = await get_repos(db)["watch"].get_for_user(int(args[1]), user["id"])
    if not watch:
        await message.answer("Watch not found.")
        return
    await get_repos(db)["watch"].set_enabled(int(args[1]), True)
    await message.answer(f"Watch #{args[1]} resumed.")


@router.message(Command("watch_remove"))
async def cmd_watch_remove(message: Message, db: aiosqlite.Connection):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /watch_remove <id>")
        return
    user = await ensure_user(db, message)
    await get_repos(db)["watch"].remove_for_user(int(args[1]), user["id"])
    await message.answer(f"Watch #{args[1]} removed.")


@router.message(Command("search"))
async def cmd_search(message: Message, db: aiosqlite.Connection):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /search <query>")
        return
    results = await get_repos(db)["message"].search_fts(args[1], limit=10)
    await message.answer(format_search_results(results))

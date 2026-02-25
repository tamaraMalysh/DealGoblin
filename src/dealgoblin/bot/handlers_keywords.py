from __future__ import annotations

from contextlib import suppress

import aiosqlite
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from dealgoblin.bot.callbacks import KeywordsCallback
from dealgoblin.bot.context import ensure_user, get_repos
from dealgoblin.bot.states import AddKeywordState
from dealgoblin.bot.ui import (
    KEYWORDS_PAGE_SIZE,
    keyword_details_markup,
    keyword_details_text,
    keywords_markup,
    keywords_text,
)
from dealgoblin.match.fts_query import build_phrase_fts_query

router = Router()


async def render_keywords_screen(
    query: CallbackQuery, db: aiosqlite.Connection, page: int = 1
) -> None:
    user = await ensure_user(db, query.message)
    repos = get_repos(db)
    offset = (page - 1) * KEYWORDS_PAGE_SIZE
    watches = await repos["watch"].list_for_user(
        user["id"], limit=KEYWORDS_PAGE_SIZE, offset=offset
    )
    total = await repos["watch"].count_for_user(user["id"])
    await query.message.edit_text(
        keywords_text(watches=watches, page=page, total=total),
        reply_markup=keywords_markup(watches=watches, page=page, total=total),
    )


@router.callback_query(KeywordsCallback.filter(F.action == "page"))
async def keywords_page(
    query: CallbackQuery, callback_data: KeywordsCallback, db: aiosqlite.Connection
):
    await render_keywords_screen(query, db, page=callback_data.page)
    await query.answer()


@router.callback_query(KeywordsCallback.filter(F.action == "open"))
async def keywords_open(
    query: CallbackQuery, callback_data: KeywordsCallback, db: aiosqlite.Connection
):
    user = await ensure_user(db, query.message)
    watch = await get_repos(db)["watch"].get_for_user(callback_data.watch_id, user["id"])
    if not watch:
        await query.answer("Слово не найдено", show_alert=True)
        return
    await query.message.edit_text(
        keyword_details_text(watch),
        reply_markup=keyword_details_markup(watch_id=watch["id"], page=callback_data.page),
    )
    await query.answer()


@router.callback_query(KeywordsCallback.filter(F.action == "add"))
async def keywords_add_start(
    query: CallbackQuery, callback_data: KeywordsCallback, state: FSMContext
):
    await state.set_state(AddKeywordState.waiting_for_text)
    await state.update_data(list_page=callback_data.page, menu_message_id=query.message.message_id)
    await query.message.answer("🌱 Введите слово для поиска:")
    await query.answer()


@router.message(AddKeywordState.waiting_for_text)
async def keywords_add_finish(message: Message, state: FSMContext, db: aiosqlite.Connection):
    raw = (message.text or "").strip()
    fts_query = build_phrase_fts_query(raw)
    if not fts_query:
        await message.answer(
            "Не удалось распознать запрос. Введите фразу и опционально -минус-слова."
        )
        return

    user = await ensure_user(db, message)
    repos = get_repos(db)
    name = raw[:80]
    await repos["watch"].add(user_id=user["id"], name=name, fts_query=fts_query)

    data = await state.get_data()
    page = int(data.get("list_page", 1))
    menu_message_id = data.get("menu_message_id")
    await state.clear()

    if menu_message_id:
        offset = (page - 1) * KEYWORDS_PAGE_SIZE
        watches = await repos["watch"].list_for_user(
            user["id"], limit=KEYWORDS_PAGE_SIZE, offset=offset
        )
        total = await repos["watch"].count_for_user(user["id"])
        with suppress(TelegramBadRequest):
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=menu_message_id,
                text=keywords_text(watches=watches, page=page, total=total),
                reply_markup=keywords_markup(watches=watches, page=page, total=total),
            )
    await message.answer("Поисковое слово сохранено.")


@router.callback_query(KeywordsCallback.filter(F.action == "delete"))
async def keywords_delete(
    query: CallbackQuery, callback_data: KeywordsCallback, db: aiosqlite.Connection
):
    user = await ensure_user(db, query.message)
    watch_repo = get_repos(db)["watch"]
    watch = await watch_repo.get_for_user(callback_data.watch_id, user["id"])
    if not watch:
        await query.answer("Слово уже удалено", show_alert=False)
        return
    await watch_repo.remove_for_user(callback_data.watch_id, user["id"])
    await render_keywords_screen(query, db, page=callback_data.page)
    await query.answer("Удалено")

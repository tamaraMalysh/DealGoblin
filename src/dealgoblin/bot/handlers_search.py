from __future__ import annotations

import aiosqlite
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from dealgoblin.bot.callbacks import MenuCallback, SearchCallback
from dealgoblin.bot.context import ensure_user
from dealgoblin.bot.states import SearchState
from dealgoblin.bot.ui import (
    main_menu_markup,
    main_menu_text,
    search_prompt_markup,
    search_prompt_text,
    search_results_markup,
    search_results_text,
)
from dealgoblin.search.service import (
    HistorySearchService,
    InvalidSearchQueryError,
    SearchAccessError,
)

router = Router()

_INVALID_QUERY_TEXT = "Не удалось распознать запрос. Введите фразу и опционально -минус-слова."


async def _run_search(message: Message, db: aiosqlite.Connection, raw_query: str) -> None:
    user = await ensure_user(db, message)
    service = HistorySearchService(db)
    page = await service.start_search(user=user, raw_query=raw_query)
    await message.answer(search_results_text(page), reply_markup=search_results_markup(page))


@router.callback_query(MenuCallback.filter(F.action == "search"))
async def menu_search(query: CallbackQuery, state: FSMContext):
    await state.set_state(SearchState.waiting_for_query)
    await query.message.edit_text(search_prompt_text(), reply_markup=search_prompt_markup())
    await query.answer()


@router.callback_query(SearchCallback.filter(F.action == "new"))
async def search_new(query: CallbackQuery, state: FSMContext):
    await state.set_state(SearchState.waiting_for_query)
    await query.message.edit_text(search_prompt_text(), reply_markup=search_prompt_markup())
    await query.answer()


@router.callback_query(SearchCallback.filter(F.action == "back"))
async def search_back(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.edit_text(main_menu_text(), reply_markup=main_menu_markup())
    await query.answer()


@router.callback_query(SearchCallback.filter(F.action == "page"))
async def search_page(
    query: CallbackQuery,
    callback_data: SearchCallback,
    db: aiosqlite.Connection,
):
    user = await ensure_user(db, query.message)
    service = HistorySearchService(db)
    try:
        page = await service.get_page(
            user=user,
            search_id=callback_data.search_id,
            page=callback_data.page,
        )
    except SearchAccessError:
        await query.answer("Результаты поиска недоступны.", show_alert=True)
        return

    await query.message.edit_text(
        search_results_text(page), reply_markup=search_results_markup(page)
    )
    await query.answer()


@router.message(SearchState.waiting_for_query)
async def search_submit(message: Message, state: FSMContext, db: aiosqlite.Connection):
    raw_query = (message.text or "").strip()
    if not raw_query:
        await message.answer(_INVALID_QUERY_TEXT)
        return

    try:
        await _run_search(message, db, raw_query)
    except InvalidSearchQueryError:
        await message.answer(_INVALID_QUERY_TEXT)
        return

    await state.clear()


@router.message(Command("search"))
async def cmd_search(message: Message, db: aiosqlite.Connection):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /search <query>")
        return
    try:
        await _run_search(message, db, args[1].strip())
    except InvalidSearchQueryError:
        await message.answer(_INVALID_QUERY_TEXT)

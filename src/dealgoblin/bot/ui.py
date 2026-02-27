from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from dealgoblin.bot.callbacks import (
    HelpCallback,
    KeywordsCallback,
    MenuCallback,
    SettingsCallback,
)

KEYWORDS_PAGE_SIZE = 6


def main_menu_text() -> str:
    return "🌱 Меню чат-бота"


def main_menu_markup() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Настройки", callback_data=MenuCallback(action="settings"))
    builder.button(text="Статистика чатов", callback_data=MenuCallback(action="stats"))
    builder.button(text="Помощь", callback_data=MenuCallback(action="help"))
    builder.adjust(1)
    return builder.as_markup()


def settings_text(user: dict, watch_count: int, found_count: int) -> str:
    city = user.get("city") or "Тбилиси"
    return (
        "🌱 Настройки бота:\n"
        f"город: ✅ {city}\n"
        f"кол-во слов для поиска: {watch_count}\n"
        f"найдено объявлений: {found_count}\n"
    )


def settings_markup() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Добавить/удалить поисковые слова",
        callback_data=SettingsCallback(action="keywords"),
    )
    builder.button(text="<< Назад", callback_data=SettingsCallback(action="back"))
    builder.adjust(1)
    return builder.as_markup()


def keywords_text(watches: list[dict], page: int, total: int) -> str:
    if total == 0:
        lines = ["Список пока пуст."]
    else:
        lines = [f"{item['id']}. {item['name']}" for item in watches]
    pages = max(1, (total + KEYWORDS_PAGE_SIZE - 1) // KEYWORDS_PAGE_SIZE)
    return "🌱 Поисковые слова:\n" + "\n".join(lines) + f"\n\nСтраница {page}/{pages}"


def keywords_markup(watches: list[dict], page: int, total: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in watches:
        builder.button(
            text=item["name"],
            callback_data=KeywordsCallback(action="open", page=page, watch_id=item["id"]),
        )
    if page > 1:
        builder.button(text="◀️", callback_data=KeywordsCallback(action="page", page=page - 1))
    if page * KEYWORDS_PAGE_SIZE < total:
        builder.button(text="▶️", callback_data=KeywordsCallback(action="page", page=page + 1))
    builder.button(
        text="Добавить поисковое слово", callback_data=KeywordsCallback(action="add", page=page)
    )
    builder.button(text="<< Назад", callback_data=KeywordsCallback(action="back"))
    builder.adjust(*([1] * len(watches)), 2, 1, 1)
    return builder.as_markup()


def keyword_details_text(watch: dict) -> str:
    return f"🌱 Поисковое слово\n\nНазвание: {watch['name']}\nFTS: {watch['fts_query']}"


def keyword_details_markup(watch_id: int, page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Удалить поисковое слово",
        callback_data=KeywordsCallback(action="delete", page=page, watch_id=watch_id),
    )
    builder.button(text="<< Назад", callback_data=KeywordsCallback(action="page", page=page))
    builder.adjust(1)
    return builder.as_markup()


def help_text() -> str:
    return (
        "Меня настроить очень просто. Я помогу Вам это сделать в несколько шагов!\n"
        '🌱 1. Перейдите в "Настройки" (город сейчас по умолчанию: Тбилиси).\n'
        '🌱 2. В пункте "Добавить/удалить поисковые слова" добавьте поисковое слово/фразу.\n'
        "🌱 3. Там же можно удалить слово, если оно больше не нужно.\n\n"
        "Как я ищу слова в объявлениях:\n"
        '🍏 запрос "стиральная машина" ищет фразу подряд в указанном порядке.\n'
        '🍏 запрос "стиральная машина -lg -samsung" исключает минус-слова.'
    )


def help_markup() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Информация", callback_data=HelpCallback(action="info"))
    builder.button(text="Техподдержка", callback_data=HelpCallback(action="support"))
    builder.button(text="<< Назад", callback_data=HelpCallback(action="back"))
    builder.adjust(1)
    return builder.as_markup()


def help_info_text() -> str:
    return (
        "Информация о поиске:\n"
        "- фраза ищется подряд в заданном порядке;\n"
        "- окончания слов допускаются;\n"
        "- минус-слова убирают совпадения."
    )


def help_support_text() -> str:
    return "Техподдержка: пока в разработке."


def help_secondary_markup() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="<< Назад", callback_data=MenuCallback(action="help"))
    return builder.as_markup()


def stats_text(sources_count: int, messages_count: int, last_24h_count: int) -> str:
    return (
        "📊 Статистика чатов\n"
        f"Источников: {sources_count}\n"
        f"Проиндексировано сообщений: {messages_count}\n"
        f"За последние 24 часа: {last_24h_count}"
    )


def stats_markup() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="<< Назад", callback_data=MenuCallback(action="back"))
    return builder.as_markup()

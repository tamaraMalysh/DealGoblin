from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from dealgoblin.bot.callbacks import (
    HelpCallback,
    KeywordsCallback,
    MenuCallback,
    SearchCallback,
    SettingsCallback,
)
from dealgoblin.search.service import SearchResultPage

KEYWORDS_PAGE_SIZE = 6


def main_menu_text() -> str:
    return "🌱 Меню чат-бота"


def main_menu_markup() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Поиск", callback_data=MenuCallback(action="search"))
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
        '🌱 3. В меню "Поиск" можно искать по истории всех проиндексированных чатов.\n'
        "🌱 4. Там же можно удалить слово, если оно больше не нужно.\n\n"
        "Как я ищу слова в объявлениях:\n"
        '🍏 запрос "стиральная машина" ищет объявления, в которых есть:\n'
        "  - стиральная машина\n"
        "  - стиральную машину\n"
        "  но не найдет:\n"
        "  - машина стиральная\n"
        "  - стиральная узкая машина\n"
        '  (для этого можно использовать запрос "стиральная")\n'
        '🍏 запрос "стиральная машина -lg -samsung" ищет объявления, где есть '
        'словосочетание "стиральная машина", но нет минус-слов "lg" и "samsung".'
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
        "- формы слов допускаются (например: стиральная/стиральную);\n"
        "- минус-слова убирают совпадения;\n"
        "- эти правила одинаковы для сохраненных слов и исторического поиска."
    )


def help_support_text() -> str:
    return "Техподдержка: https://t.me/siberianErmine"


def help_secondary_markup() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="<< Назад", callback_data=MenuCallback(action="help"))
    return builder.as_markup()


def search_prompt_text() -> str:
    return (
        "🔎 Исторический поиск\n\n"
        "Введите фразу для поиска по всем проиндексированным чатам.\n"
        "Можно использовать минус-слова, например: mac laptop -broken"
    )


def search_prompt_markup() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="<< Назад", callback_data=SearchCallback(action="back"))
    return builder.as_markup()


def search_results_text(page: SearchResultPage) -> str:
    pages = max(1, (page.total + page.page_size - 1) // page.page_size)
    header = (
        "🔎 Исторический поиск\n"
        f"Запрос: {page.raw_query}\n"
        f"Найдено: {page.total}\n"
        f"Страница {page.page}/{pages}"
    )
    if not page.items:
        return header + "\n\nНичего не найдено."

    lines = [header, ""]
    for item in page.items:
        snippet = (item.text_raw or "")[:120]
        lines.append(f"- {item.source_name}")
        lines.append(f"  {snippet}")
        if item.link:
            lines.append(f"  {item.link}")
        lines.append("")
    return "\n".join(lines).rstrip()


def search_results_markup(page: SearchResultPage) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if page.has_prev:
        builder.button(
            text="◀️",
            callback_data=SearchCallback(
                action="page", search_id=page.search_id, page=page.page - 1
            ),
        )
    if page.has_next:
        builder.button(
            text="▶️",
            callback_data=SearchCallback(
                action="page", search_id=page.search_id, page=page.page + 1
            ),
        )
    builder.button(text="Новый поиск", callback_data=SearchCallback(action="new"))
    builder.button(text="<< Назад", callback_data=SearchCallback(action="back"))
    builder.adjust(2, 1, 1)
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

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class MenuCallback(CallbackData, prefix="menu"):
    action: str


class SettingsCallback(CallbackData, prefix="settings"):
    action: str


class KeywordsCallback(CallbackData, prefix="keywords"):
    action: str
    page: int = 1
    watch_id: int = 0


class HelpCallback(CallbackData, prefix="help"):
    action: str


class HistoryCallback(CallbackData, prefix="history"):
    page: int = 1

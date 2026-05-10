from __future__ import annotations

from types import SimpleNamespace

import pytest

from dealgoblin.bot.callbacks import SearchCallback
from dealgoblin.bot.handlers_search import cmd_search, menu_search, search_page
from dealgoblin.bot.states import SearchState
from dealgoblin.search.service import InvalidSearchQueryError, SearchResultItem, SearchResultPage


class _FakeMessage:
    def __init__(self, text: str = "", chat_id: int = 1, user_id: int = 1):
        self.text = text
        self.chat = SimpleNamespace(id=chat_id)
        self.from_user = SimpleNamespace(id=user_id)
        self.answers: list[tuple[str, object | None]] = []
        self.edits: list[tuple[str, object | None]] = []

    async def answer(self, text: str, reply_markup=None):
        self.answers.append((text, reply_markup))

    async def edit_text(self, text: str, reply_markup=None):
        self.edits.append((text, reply_markup))


class _FakeQuery:
    def __init__(self, message: _FakeMessage):
        self.message = message
        self.answer_calls: list[tuple[str | None, bool]] = []

    async def answer(self, text: str | None = None, show_alert: bool = False):
        self.answer_calls.append((text, show_alert))


class _FakeState:
    def __init__(self):
        self.state = None

    async def set_state(self, state):
        self.state = state


async def _fake_user(*_args, **_kwargs):
    return {"id": 11}


def _page(*, search_id: int = 7, page: int = 1, total: int = 1) -> SearchResultPage:
    return SearchResultPage(
        search_id=search_id,
        raw_query="lamp",
        page=page,
        total=total,
        page_size=5,
        items=[
            SearchResultItem(
                rowid=1,
                chat_id=-1001,
                message_id=10,
                text_raw="Vintage lamp 500р",
                link="https://t.me/flea/10",
                posted_at=None,
                source_name="Flea Channel",
            )
        ],
    )


@pytest.mark.asyncio
async def test_menu_search_enters_waiting_state():
    message = _FakeMessage()
    query = _FakeQuery(message)
    state = _FakeState()

    await menu_search(query, state)

    assert state.state == SearchState.waiting_for_query
    assert message.edits
    assert "исторический поиск" in message.edits[0][0].lower()


@pytest.mark.asyncio
async def test_cmd_search_uses_history_search_service(monkeypatch):
    message = _FakeMessage(text="/search lamp")
    calls: list[str] = []
    monkeypatch.setattr("dealgoblin.bot.handlers_search.ensure_user", _fake_user)

    class _FakeService:
        def __init__(self, _db):
            pass

        async def start_search(self, *, user, raw_query: str):
            calls.append(raw_query)
            return _page()

    monkeypatch.setattr("dealgoblin.bot.handlers_search.HistorySearchService", _FakeService)

    await cmd_search(message, db=None)

    assert calls == ["lamp"]
    assert message.answers
    assert "flea channel" in message.answers[0][0].lower()


@pytest.mark.asyncio
async def test_cmd_search_reports_invalid_query(monkeypatch):
    message = _FakeMessage(text="/search ---")
    monkeypatch.setattr("dealgoblin.bot.handlers_search.ensure_user", _fake_user)

    class _FakeService:
        def __init__(self, _db):
            pass

        async def start_search(self, *, user, raw_query: str):
            raise InvalidSearchQueryError("bad")

    monkeypatch.setattr("dealgoblin.bot.handlers_search.HistorySearchService", _FakeService)

    await cmd_search(message, db=None)

    assert message.answers == [
        ("Не удалось распознать запрос. Введите фразу и опционально -минус-слова.", None)
    ]


@pytest.mark.asyncio
async def test_search_page_uses_same_service_for_pagination(monkeypatch):
    message = _FakeMessage()
    query = _FakeQuery(message)
    seen: list[tuple[int, int]] = []
    monkeypatch.setattr("dealgoblin.bot.handlers_search.ensure_user", _fake_user)

    class _FakeService:
        def __init__(self, _db):
            pass

        async def get_page(self, *, user, search_id: int, page: int):
            seen.append((search_id, page))
            return _page(search_id=search_id, page=page, total=11)

    monkeypatch.setattr("dealgoblin.bot.handlers_search.HistorySearchService", _FakeService)

    await search_page(
        query,
        SearchCallback(action="page", search_id=9, page=2),
        db=None,
    )

    assert seen == [(9, 2)]
    assert message.edits
    assert "стрраница" not in message.edits[0][0].lower()

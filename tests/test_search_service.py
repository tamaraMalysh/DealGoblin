import pytest

from dealgoblin.search.service import (
    HistorySearchService,
    InvalidSearchQueryError,
    SearchAccessError,
)
from dealgoblin.storage.db import init_db
from dealgoblin.storage.repo import BotUserRepo, MessageRepo


@pytest.fixture
async def db(tmp_path):
    conn = await init_db(str(tmp_path / "test.sqlite3"))
    yield conn
    await conn.close()


async def test_start_search_rejects_unparseable_query(db):
    user = await BotUserRepo(db).ensure(chat_id=1000, tg_user_id=1000)
    service = HistorySearchService(db)

    with pytest.raises(InvalidSearchQueryError):
        await service.start_search(user=user, raw_query="---")


async def test_start_search_returns_first_page_with_phrase_semantics(db):
    user = await BotUserRepo(db).ensure(chat_id=1001, tg_user_id=1001)
    repo = MessageRepo(db)
    service = HistorySearchService(db)

    await repo.insert(
        chat_id=-1001,
        message_id=1,
        text_raw="mac laptop 2500",
        text_norm="mac laptop 2500",
        source_title="Channel A",
    )
    await repo.insert(
        chat_id=-1001,
        message_id=2,
        text_raw="laptop for mac users",
        text_norm="laptop for mac users",
        source_title="Channel A",
    )

    page = await service.start_search(user=user, raw_query="mac laptop")
    assert [item.message_id for item in page.items] == [1]
    assert page.search_id > 0
    assert page.total == 1


async def test_get_page_enforces_session_ownership(db):
    owner = await BotUserRepo(db).ensure(chat_id=1002, tg_user_id=1002)
    intruder = await BotUserRepo(db).ensure(chat_id=1003, tg_user_id=1003)
    repo = MessageRepo(db)
    service = HistorySearchService(db)

    await repo.insert(chat_id=-1001, message_id=1, text_raw="lamp", text_norm="lamp")
    first_page = await service.start_search(user=owner, raw_query="lamp")

    with pytest.raises(SearchAccessError):
        await service.get_page(user=intruder, search_id=first_page.search_id, page=1)

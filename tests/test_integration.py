import pytest

from dealgoblin.match.matcher import evaluate_message
from dealgoblin.storage.db import init_db
from dealgoblin.storage.repo import BotUserRepo, MatchEventRepo, MessageRepo, WatchRepo


@pytest.fixture
async def db(tmp_path):
    conn = await init_db(str(tmp_path / "test.sqlite3"))
    yield conn
    await conn.close()


async def test_ingest_match_notify_pipeline(db):
    """Full pipeline: insert message -> match watch -> match_event created."""
    msg_repo = MessageRepo(db)
    watch_repo = WatchRepo(db)
    me_repo = MatchEventRepo(db)
    user = await BotUserRepo(db).ensure(chat_id=1000, tg_user_id=1000)

    await watch_repo.add(
        user_id=user["id"], name="lamps", fts_query="lamp OR lantern", price_max=2000
    )

    rowid = await msg_repo.insert(
        chat_id=100,
        message_id=1,
        text_raw="Beautiful vintage lamp 800р",
        text_norm="beautiful vintage lamp 800р",
        link="https://t.me/flea/1",
    )
    events = await evaluate_message(db, rowid, "beautiful vintage lamp 800р")
    assert len(events) == 1

    pending = await me_repo.list_pending()
    assert len(pending) == 1
    assert pending[0]["watch_name"] == "lamps"

    await me_repo.mark_notified(pending[0]["id"])
    assert await me_repo.list_pending() == []


async def test_search_returns_ranked_results(db):
    msg_repo = MessageRepo(db)
    await msg_repo.insert(chat_id=1, message_id=1, text_raw="lamp", text_norm="lamp")
    await msg_repo.insert(chat_id=1, message_id=2, text_raw="sofa", text_norm="sofa")
    await msg_repo.insert(
        chat_id=1,
        message_id=3,
        text_raw="lamp lamp lamp",
        text_norm="lamp lamp lamp",
    )

    results = await msg_repo.search_fts("lamp", limit=10)
    assert len(results) == 2
    # Higher relevance first (bm25 returns negative, so more negative = better)
    # The document with more occurrences of "lamp" should come first.
    assert [row["text_raw"] for row in results] == ["lamp lamp lamp", "lamp"]


async def test_no_duplicate_alerts_across_evaluations(db):
    msg_repo = MessageRepo(db)
    watch_repo = WatchRepo(db)
    user = await BotUserRepo(db).ensure(chat_id=2000, tg_user_id=2000)

    await watch_repo.add(user_id=user["id"], name="w", fts_query="lamp")
    rowid = await msg_repo.insert(chat_id=1, message_id=1, text_raw="lamp", text_norm="lamp")

    events1 = await evaluate_message(db, rowid, "lamp")
    events2 = await evaluate_message(db, rowid, "lamp")
    assert len(events1) == 1
    assert len(events2) == 0  # dedupe prevents second match_event

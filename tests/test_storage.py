import pytest

from dealgoblin.storage.db import init_db
from dealgoblin.storage.repo import BotUserRepo, MatchEventRepo, MessageRepo, SourceRepo, WatchRepo


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.sqlite3")


@pytest.fixture
async def db(db_path):
    conn = await init_db(db_path)
    yield conn
    await conn.close()


async def test_schema_tables_exist(db):
    async with db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name") as cur:
        tables = [row[0] for row in await cur.fetchall()]
    assert "sources" in tables
    assert "messages" in tables
    assert "watches" in tables
    assert "bot_users" in tables
    assert "match_events" in tables
    assert "messages_fts" in tables


async def test_fts_sync_on_insert(db):
    await db.execute(
        "INSERT INTO messages (chat_id, message_id, text_norm) VALUES (1, 1, 'vintage lamp')"
    )
    await db.commit()
    async with db.execute("SELECT rowid FROM messages_fts WHERE messages_fts MATCH 'lamp'") as cur:
        rows = await cur.fetchall()
    assert len(rows) == 1


async def test_message_dedupe(db):
    await db.execute("INSERT INTO messages (chat_id, message_id, text_norm) VALUES (1, 1, 'first')")
    await db.commit()
    with pytest.raises(Exception):
        await db.execute(
            "INSERT INTO messages (chat_id, message_id, text_norm) VALUES (1, 1, 'duplicate')"
        )


async def test_match_event_dedupe(db):
    user = await BotUserRepo(db).ensure(chat_id=100, tg_user_id=100)
    await db.execute(
        "INSERT INTO watches (user_id, name, fts_query) VALUES (?, 'w', 'test')",
        (user["id"],),
    )
    await db.execute("INSERT INTO messages (chat_id, message_id, text_norm) VALUES (1, 1, 'test')")
    await db.commit()
    await db.execute("INSERT INTO match_events (watch_id, message_rowid) VALUES (1, 1)")
    await db.commit()
    with pytest.raises(Exception):
        await db.execute("INSERT INTO match_events (watch_id, message_rowid) VALUES (1, 1)")


async def test_source_add_and_list(db):
    repo = SourceRepo(db)
    await repo.add(chat_id=100, username="fleamarket", title="Flea Market")
    sources = await repo.list_all()
    assert len(sources) == 1
    assert sources[0]["chat_id"] == 100


async def test_source_remove(db):
    repo = SourceRepo(db)
    await repo.add(chat_id=100)
    await repo.remove(chat_id=100)
    assert await repo.list_all() == []


async def test_source_get_all_chat_ids(db):
    repo = SourceRepo(db)
    await repo.add(chat_id=100)
    await repo.add(chat_id=200)
    ids = await repo.get_all_chat_ids()
    assert set(ids) == {100, 200}


async def test_message_insert_and_search(db):
    repo = MessageRepo(db)
    rowid = await repo.insert(
        chat_id=1,
        message_id=10,
        text_raw="Vintage Lamp 500р",
        text_norm="vintage lamp 500р",
        link="https://t.me/flea/10",
        posted_at="2025-01-01T00:00:00",
    )
    assert rowid is not None
    results = await repo.search_fts("lamp", limit=5)
    assert len(results) == 1
    assert results[0]["link"] == "https://t.me/flea/10"


async def test_message_insert_duplicate_returns_none(db):
    repo = MessageRepo(db)
    r1 = await repo.insert(chat_id=1, message_id=10, text_raw="a", text_norm="a")
    r2 = await repo.insert(chat_id=1, message_id=10, text_raw="b", text_norm="b")
    assert r1 is not None
    assert r2 is None


async def test_watch_crud(db):
    user = await BotUserRepo(db).ensure(chat_id=300, tg_user_id=300)
    repo = WatchRepo(db)
    wid = await repo.add(user_id=user["id"], name="lamps", fts_query="lamp OR lantern")
    watches = await repo.list_all()
    assert len(watches) == 1
    assert watches[0]["name"] == "lamps"
    await repo.set_enabled(wid, False)
    watches = await repo.list_enabled()
    assert len(watches) == 0
    await repo.remove(wid)
    assert await repo.list_all() == []


async def test_match_event_create_and_pending(db):
    user = await BotUserRepo(db).ensure(chat_id=555, tg_user_id=555)
    repo_w = WatchRepo(db)
    repo_msg = MessageRepo(db)
    repo_me = MatchEventRepo(db)
    wid = await repo_w.add(user_id=user["id"], name="w", fts_query="q")
    rowid = await repo_msg.insert(chat_id=1, message_id=1, text_raw="t", text_norm="t")
    await repo_me.create(watch_id=wid, message_rowid=rowid)
    pending = await repo_me.list_pending()
    assert len(pending) == 1
    assert pending[0]["watch_id"] == wid
    assert pending[0]["owner_chat_id"] == 555
    await repo_me.mark_notified(pending[0]["id"])
    assert await repo_me.list_pending() == []

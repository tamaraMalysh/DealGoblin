import pytest

from dealgoblin.storage.db import init_db


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.sqlite3")


@pytest.fixture
async def db(db_path):
    conn = await init_db(db_path)
    yield conn
    await conn.close()


async def test_schema_tables_exist(db):
    async with db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ) as cur:
        tables = [row[0] for row in await cur.fetchall()]
    assert "sources" in tables
    assert "messages" in tables
    assert "watches" in tables
    assert "match_events" in tables
    assert "messages_fts" in tables


async def test_fts_sync_on_insert(db):
    await db.execute(
        "INSERT INTO messages (chat_id, message_id, text_norm) VALUES (1, 1, 'vintage lamp')"
    )
    await db.commit()
    async with db.execute(
        "SELECT rowid FROM messages_fts WHERE messages_fts MATCH 'lamp'"
    ) as cur:
        rows = await cur.fetchall()
    assert len(rows) == 1


async def test_message_dedupe(db):
    await db.execute(
        "INSERT INTO messages (chat_id, message_id, text_norm) VALUES (1, 1, 'first')"
    )
    await db.commit()
    with pytest.raises(Exception):
        await db.execute(
            "INSERT INTO messages (chat_id, message_id, text_norm) VALUES (1, 1, 'duplicate')"
        )


async def test_match_event_dedupe(db):
    await db.execute("INSERT INTO watches (name, fts_query) VALUES ('w', 'test')")
    await db.execute(
        "INSERT INTO messages (chat_id, message_id, text_norm) VALUES (1, 1, 'test')"
    )
    await db.commit()
    await db.execute("INSERT INTO match_events (watch_id, message_rowid) VALUES (1, 1)")
    await db.commit()
    with pytest.raises(Exception):
        await db.execute("INSERT INTO match_events (watch_id, message_rowid) VALUES (1, 1)")

import sqlite3
from pathlib import Path

import pytest

import dealgoblin.storage.db as storage_db
from dealgoblin.ingest.normalize import normalize_text
from dealgoblin.storage.db import init_db
from dealgoblin.storage.repo import (
    BotUserRepo,
    MatchEventRepo,
    MessageRepo,
    SearchSessionRepo,
    SourceRepo,
    WatchRepo,
)


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
    assert "search_sessions" in tables
    assert "watches" in tables
    assert "bot_users" in tables
    assert "match_events" in tables
    assert "messages_fts" in tables
    assert "runtime_meta" in tables


async def test_init_db_sets_busy_timeout_and_wal(db_path):
    conn = await init_db(db_path, busy_timeout_ms=2222)

    async with conn.execute("PRAGMA busy_timeout") as cur:
        busy_timeout_row = await cur.fetchone()
    assert int(busy_timeout_row[0]) == 2222

    async with conn.execute("PRAGMA journal_mode") as cur:
        journal_row = await cur.fetchone()
    assert str(journal_row[0]).lower() == "wal"

    await conn.close()


async def test_init_db_recovers_from_non_sqlite_file(db_path):
    db_file = Path(db_path)
    original_payload = b"not-a-sqlite-file"
    db_file.write_bytes(original_payload)

    conn = await init_db(db_path)
    async with conn.execute("SELECT name FROM sqlite_master WHERE type='table'") as cur:
        table_names = {row[0] for row in await cur.fetchall()}
    await conn.close()

    assert "messages" in table_names
    backups = [
        path
        for path in db_file.parent.glob(f"{db_file.name}.corrupt-*")
        if not path.name.endswith("-wal") and not path.name.endswith("-shm")
    ]
    assert len(backups) == 1
    assert backups[0].read_bytes() == original_payload


async def test_init_db_moves_wal_and_shm_sidecars_on_corruption(db_path, monkeypatch):
    db_file = Path(db_path)
    wal_file = db_file.with_name(f"{db_file.name}-wal")
    shm_file = db_file.with_name(f"{db_file.name}-shm")
    db_file.write_bytes(b"corrupted-main")
    wal_file.write_bytes(b"corrupted-wal")
    shm_file.write_bytes(b"corrupted-shm")

    calls = 0
    original_init_once = storage_db._init_db_once

    async def _fake_init_once(path: str, busy_timeout_ms: int):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise sqlite3.DatabaseError("database disk image is malformed")
        return await original_init_once(path, busy_timeout_ms)

    monkeypatch.setattr(storage_db, "_init_db_once", _fake_init_once)

    conn = await init_db(db_path)
    await conn.close()

    assert calls == 2
    assert not wal_file.exists()
    assert not shm_file.exists()
    backup_names = {path.name for path in db_file.parent.glob(f"{db_file.name}.corrupt-*")}
    assert any(not name.endswith("-wal") and not name.endswith("-shm") for name in backup_names)
    assert any(name.endswith("-wal") for name in backup_names)
    assert any(name.endswith("-shm") for name in backup_names)


async def test_init_db_integrity_probe_rejects_quick_check_failure(db_path, monkeypatch):
    calls = 0

    async def _fake_assert_integrity_ok(_conn):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise sqlite3.DatabaseError("database corrupt: forced quick_check failure")

    monkeypatch.setattr(storage_db, "_assert_integrity_ok", _fake_assert_integrity_ok)

    db_file = Path(db_path)
    conn = await init_db(db_path)
    await conn.close()

    backups = [path for path in db_file.parent.glob(f"{db_file.name}.corrupt-*")]
    assert calls == 2
    assert len(backups) == 1


async def test_init_db_adds_dedupe_columns_and_indexes_to_legacy_messages(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE messages ("
        "rowid INTEGER PRIMARY KEY, "
        "chat_id INTEGER NOT NULL, "
        "message_id INTEGER NOT NULL, "
        "text_raw TEXT, "
        "text_norm TEXT, "
        "link TEXT, "
        "posted_at TEXT, "
        "ingested_at TEXT NOT NULL DEFAULT (datetime('now')), "
        "UNIQUE(chat_id, message_id)"
        ")"
    )
    conn.commit()
    conn.close()

    upgraded = await init_db(db_path)

    async with upgraded.execute("PRAGMA table_info(messages)") as cur:
        column_names = {row[1] for row in await cur.fetchall()}
    assert "author_id" in column_names
    assert "author_name_norm" in column_names
    assert "dedupe_key" in column_names

    async with upgraded.execute("PRAGMA index_list(messages)") as cur:
        message_indexes = {row[1] for row in await cur.fetchall()}
    assert "idx_messages_dedupe_key" in message_indexes

    async with upgraded.execute("PRAGMA index_list(match_events)") as cur:
        match_event_indexes = {row[1] for row in await cur.fetchall()}
    assert "idx_match_events_watch_created_at" in match_event_indexes

    await upgraded.close()


async def test_init_db_adds_source_columns_and_backfills_from_sources(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE sources ("
        "id INTEGER PRIMARY KEY, "
        "chat_id INTEGER UNIQUE NOT NULL, "
        "username TEXT, "
        "title TEXT, "
        "added_at TEXT NOT NULL DEFAULT (datetime('now'))"
        ")"
    )
    conn.execute(
        "CREATE TABLE messages ("
        "rowid INTEGER PRIMARY KEY, "
        "chat_id INTEGER NOT NULL, "
        "message_id INTEGER NOT NULL, "
        "text_raw TEXT, "
        "text_norm TEXT, "
        "link TEXT, "
        "posted_at TEXT, "
        "ingested_at TEXT NOT NULL DEFAULT (datetime('now')), "
        "UNIQUE(chat_id, message_id)"
        ")"
    )
    conn.execute(
        "INSERT INTO sources (chat_id, username, title) VALUES (-1001, 'chan', 'Channel Title')"
    )
    conn.execute(
        "INSERT INTO messages (chat_id, message_id, text_raw, text_norm) "
        "VALUES (-1001, 10, 'Vintage lamp', 'vintage lamp')"
    )
    conn.commit()
    conn.close()

    upgraded = await init_db(db_path)

    async with upgraded.execute("PRAGMA table_info(messages)") as cur:
        column_names = {row[1] for row in await cur.fetchall()}
    assert "source_username" in column_names
    assert "source_title" in column_names

    async with upgraded.execute(
        "SELECT source_username, source_title "
        "FROM messages WHERE chat_id = -1001 AND message_id = 10"
    ) as cur:
        row = await cur.fetchone()
    assert row == ("chan", "Channel Title")

    async with upgraded.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = 'search_sessions'"
    ) as cur:
        search_sessions = await cur.fetchone()
    assert search_sessions is not None

    await upgraded.close()


async def test_init_db_reindexes_text_norm_once_when_meta_missing(db_path):
    conn = await init_db(db_path)
    await conn.execute(
        "INSERT INTO messages (chat_id, message_id, text_raw, text_norm) VALUES (?, ?, ?, ?)",
        (1, 1, "стиральную машину", "стиральную машину"),
    )
    await conn.execute("DELETE FROM runtime_meta WHERE key = 'text_normalization_version'")
    await conn.commit()
    await conn.close()

    conn = await init_db(db_path)
    async with conn.execute(
        "SELECT text_norm FROM messages WHERE chat_id = 1 AND message_id = 1"
    ) as cur:
        row = await cur.fetchone()
    assert row[0] == normalize_text("стиральную машину")
    async with conn.execute(
        "SELECT value FROM runtime_meta WHERE key = 'text_normalization_version'"
    ) as cur:
        version_row = await cur.fetchone()
    assert version_row is not None

    await conn.execute(
        "UPDATE messages SET text_norm = ? WHERE chat_id = ? AND message_id = ?",
        ("стиральную машину", 1, 1),
    )
    await conn.commit()
    await conn.close()

    conn = await init_db(db_path)
    async with conn.execute(
        "SELECT text_norm FROM messages WHERE chat_id = 1 AND message_id = 1"
    ) as cur:
        row = await cur.fetchone()
    assert row[0] == "стиральную машину"
    await conn.close()


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


async def test_source_sync_authoritative_upserts_and_removes_stale(db):
    repo = SourceRepo(db)
    await repo.add(chat_id=100, username="old", title="Old")
    await repo.add(chat_id=200, username="keep", title="Keep")

    await repo.sync_authoritative(
        [
            {"chat_id": 200, "username": None, "title": "Updated"},
            {"chat_id": 300, "username": "new", "title": "New"},
        ]
    )

    sources = await repo.list_all()
    assert {row["chat_id"] for row in sources} == {200, 300}
    by_chat = {row["chat_id"]: row for row in sources}
    assert by_chat[200]["username"] == "keep"
    assert by_chat[200]["title"] == "Updated"
    assert by_chat[300]["username"] == "new"


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


async def test_message_insert_persists_dedupe_fields(db):
    repo = MessageRepo(db)
    rowid = await repo.insert(
        chat_id=1,
        message_id=11,
        text_raw="Vintage Lamp 500р",
        text_norm="vintage lamp 500р",
        author_id=123456,
        author_name_norm="seller name",
        dedupe_key="abc123",
    )
    assert rowid is not None
    row = await repo.get_by_rowid(rowid)
    assert row is not None
    assert row["author_id"] == 123456
    assert row["author_name_norm"] == "seller name"
    assert row["dedupe_key"] == "abc123"


async def test_message_insert_persists_source_metadata(db):
    repo = MessageRepo(db)
    rowid = await repo.insert(
        chat_id=-1001,
        message_id=12,
        text_raw="Vintage Lamp 500р",
        text_norm="vintage lamp 500р",
        source_username="chan",
        source_title="Channel Title",
    )
    assert rowid is not None

    row = await repo.get_by_rowid(rowid)
    assert row is not None
    assert row["source_username"] == "chan"
    assert row["source_title"] == "Channel Title"


async def test_message_insert_duplicate_returns_none(db):
    repo = MessageRepo(db)
    r1 = await repo.insert(chat_id=1, message_id=10, text_raw="a", text_norm="a")
    r2 = await repo.insert(chat_id=1, message_id=10, text_raw="b", text_norm="b")
    assert r1 is not None
    assert r2 is None


async def test_search_history_keeps_result_when_source_removed(db):
    msg_repo = MessageRepo(db)
    source_repo = SourceRepo(db)

    await source_repo.add(chat_id=-1001, username="chan", title="Channel Title")
    await msg_repo.insert(
        chat_id=-1001,
        message_id=10,
        text_raw="Vintage lamp",
        text_norm="vintage lamp",
        source_username="chan",
        source_title="Channel Title",
        link="https://t.me/chan/10",
    )
    await source_repo.remove(chat_id=-1001)

    results = await msg_repo.search_history('"vintage lamp"', snapshot_max_rowid=100, limit=10)
    assert len(results) == 1
    assert results[0]["source_name"] == "Channel Title"
    assert results[0]["link"] == "https://t.me/chan/10"


async def test_search_history_falls_back_to_source_table_for_legacy_rows(db):
    source_repo = SourceRepo(db)
    await source_repo.add(chat_id=-1002, username="legacy", title="Legacy Source")
    await db.execute(
        "INSERT INTO messages (chat_id, message_id, text_raw, text_norm, link) "
        "VALUES (?, ?, ?, ?, ?)",
        (-1002, 20, "Old table", "old table", "https://t.me/c/1002/20"),
    )
    await db.commit()

    results = await MessageRepo(db).search_history('"old table"', snapshot_max_rowid=100, limit=10)
    assert len(results) == 1
    assert results[0]["source_name"] == "Legacy Source"


async def test_search_history_respects_snapshot_max_rowid(db):
    repo = MessageRepo(db)
    first = await repo.insert(chat_id=1, message_id=1, text_raw="lamp", text_norm="lamp")
    assert first is not None
    snapshot_max_rowid = first
    second = await repo.insert(chat_id=1, message_id=2, text_raw="lamp", text_norm="lamp")
    assert second is not None

    results = await repo.search_history("lamp", snapshot_max_rowid=snapshot_max_rowid, limit=10)
    assert [row["message_id"] for row in results] == [1]


async def test_search_session_repo_creates_fetches_and_prunes_old_sessions(db):
    user = await BotUserRepo(db).ensure(chat_id=777, tg_user_id=777)
    repo = SearchSessionRepo(db)

    await db.execute(
        "INSERT INTO search_sessions "
        "(user_id, raw_query, fts_query, snapshot_max_rowid, created_at) "
        "VALUES (?, ?, ?, ?, datetime('now', '-8 days'))",
        (user["id"], "old", "old", 1),
    )
    await db.commit()

    search_id = await repo.create(
        user_id=user["id"],
        raw_query="lamp",
        fts_query="lamp",
        snapshot_max_rowid=5,
    )

    row = await repo.get_for_user(search_id=search_id, user_id=user["id"])
    assert row is not None
    assert row["raw_query"] == "lamp"

    async with db.execute("SELECT COUNT(*) FROM search_sessions WHERE raw_query = 'old'") as cur:
        old_count = await cur.fetchone()
    assert old_count[0] == 0


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

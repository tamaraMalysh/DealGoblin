import pytest

from dealgoblin.match.fts_query import build_fts_query
from dealgoblin.match.matcher import evaluate_message
from dealgoblin.storage.db import init_db
from dealgoblin.storage.repo import MessageRepo, WatchRepo


def test_simple_include():
    assert build_fts_query(include=["lamp", "vintage"]) == "lamp AND vintage"


def test_include_and_exclude():
    assert build_fts_query(include=["lamp"], exclude=["broken"]) == "lamp NOT broken"


def test_multiple_exclude():
    q = build_fts_query(include=["lamp"], exclude=["broken", "cracked"])
    assert q == "lamp NOT broken NOT cracked"


def test_empty_include_returns_none():
    assert build_fts_query(include=[]) is None


# --- Matcher tests ---


@pytest.fixture
async def db(tmp_path):
    conn = await init_db(str(tmp_path / "test.sqlite3"))
    yield conn
    await conn.close()


async def test_matcher_creates_match_event(db):
    msg_repo = MessageRepo(db)
    watch_repo = WatchRepo(db)
    rowid = await msg_repo.insert(
        chat_id=1,
        message_id=1,
        text_raw="Vintage lamp 500р",
        text_norm="vintage lamp 500р",
    )
    await watch_repo.add(name="lamps", fts_query="lamp")
    events = await evaluate_message(db, rowid, "vintage lamp 500р")
    assert len(events) == 1


async def test_matcher_no_match(db):
    msg_repo = MessageRepo(db)
    watch_repo = WatchRepo(db)
    rowid = await msg_repo.insert(
        chat_id=1,
        message_id=1,
        text_raw="sofa",
        text_norm="sofa",
    )
    await watch_repo.add(name="lamps", fts_query="lamp")
    events = await evaluate_message(db, rowid, "sofa")
    assert len(events) == 0


async def test_matcher_skips_disabled_watch(db):
    msg_repo = MessageRepo(db)
    watch_repo = WatchRepo(db)
    rowid = await msg_repo.insert(
        chat_id=1,
        message_id=1,
        text_raw="lamp",
        text_norm="lamp",
    )
    wid = await watch_repo.add(name="lamps", fts_query="lamp")
    await watch_repo.set_enabled(wid, False)
    events = await evaluate_message(db, rowid, "lamp")
    assert len(events) == 0

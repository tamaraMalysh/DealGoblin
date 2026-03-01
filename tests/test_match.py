import pytest

from dealgoblin.ingest.normalize import normalize_text
from dealgoblin.match.fts_query import build_fts_query, build_phrase_fts_query
from dealgoblin.match.matcher import evaluate_message
from dealgoblin.storage.db import init_db
from dealgoblin.storage.repo import BotUserRepo, MessageRepo, WatchRepo


def test_simple_include():
    assert build_fts_query(include=["lamp", "vintage"]) == '"lamp* vintage*"'


def test_include_and_exclude():
    assert build_fts_query(include=["lamp"], exclude=["broken"]) == '"lamp*" NOT broken*'


def test_multiple_exclude():
    q = build_fts_query(include=["lamp"], exclude=["broken", "cracked"])
    assert q == '"lamp*" NOT broken* NOT cracked*'


def test_build_fts_query_lemmatizes_cyrillic_tokens():
    q = build_fts_query(include=["стиральную", "машину"], exclude=["samsung"])
    assert q == '"стиральный* машина*" NOT samsung*'


def test_empty_include_returns_none():
    assert build_fts_query(include=[]) is None


def test_phrase_builder_with_minus_words():
    q = build_phrase_fts_query("стиральная машина -lg -samsung")
    assert q == '"стиральный* машина*" NOT lg NOT samsung*'


def test_phrase_builder_empty_input_returns_none():
    assert build_phrase_fts_query('"-" !!!') is None


# --- Matcher tests ---


@pytest.fixture
async def db(tmp_path):
    conn = await init_db(str(tmp_path / "test.sqlite3"))
    yield conn
    await conn.close()


async def test_matcher_creates_match_event(db):
    msg_repo = MessageRepo(db)
    watch_repo = WatchRepo(db)
    user = await BotUserRepo(db).ensure(chat_id=1, tg_user_id=1)
    rowid = await msg_repo.insert(
        chat_id=1,
        message_id=1,
        text_raw="Vintage lamp 500р",
        text_norm="vintage lamp 500р",
    )
    await watch_repo.add(user_id=user["id"], name="lamps", fts_query="lamp")
    events = await evaluate_message(db, rowid, "vintage lamp 500р")
    assert len(events) == 1


async def test_matcher_no_match(db):
    msg_repo = MessageRepo(db)
    watch_repo = WatchRepo(db)
    user = await BotUserRepo(db).ensure(chat_id=2, tg_user_id=2)
    rowid = await msg_repo.insert(
        chat_id=1,
        message_id=1,
        text_raw="sofa",
        text_norm="sofa",
    )
    await watch_repo.add(user_id=user["id"], name="lamps", fts_query="lamp")
    events = await evaluate_message(db, rowid, "sofa")
    assert len(events) == 0


async def test_matcher_skips_disabled_watch(db):
    msg_repo = MessageRepo(db)
    watch_repo = WatchRepo(db)
    user = await BotUserRepo(db).ensure(chat_id=3, tg_user_id=3)
    rowid = await msg_repo.insert(
        chat_id=1,
        message_id=1,
        text_raw="lamp",
        text_norm="lamp",
    )
    wid = await watch_repo.add(user_id=user["id"], name="lamps", fts_query="lamp")
    await watch_repo.set_enabled(wid, False)
    events = await evaluate_message(db, rowid, "lamp")
    assert len(events) == 0


async def test_phrase_query_order_and_adjacency(db):
    msg_repo = MessageRepo(db)
    watch_repo = WatchRepo(db)
    user = await BotUserRepo(db).ensure(chat_id=4, tg_user_id=4)
    bad_order = await msg_repo.insert(
        chat_id=1,
        message_id=10,
        text_raw="машина стиральная",
        text_norm=normalize_text("машина стиральная"),
    )
    with_insert = await msg_repo.insert(
        chat_id=1,
        message_id=11,
        text_raw="стиральная узкая машина",
        text_norm=normalize_text("стиральная узкая машина"),
    )
    inflected = await msg_repo.insert(
        chat_id=1,
        message_id=12,
        text_raw="стиральную машину",
        text_norm=normalize_text("стиральную машину"),
    )

    fts = build_phrase_fts_query("стиральная машина")
    await watch_repo.add(user_id=user["id"], name="washer", fts_query=fts)

    assert await evaluate_message(db, bad_order, "машина стиральная") == []
    assert await evaluate_message(db, with_insert, "стиральная узкая машина") == []
    assert len(await evaluate_message(db, inflected, "стиральную машину")) == 1


async def test_phrase_query_minus_words(db):
    msg_repo = MessageRepo(db)
    watch_repo = WatchRepo(db)
    user = await BotUserRepo(db).ensure(chat_id=5, tg_user_id=5)

    blocked = await msg_repo.insert(
        chat_id=1,
        message_id=20,
        text_raw="стиральную машину samsung",
        text_norm=normalize_text("стиральную машину samsung"),
    )
    allowed = await msg_repo.insert(
        chat_id=1,
        message_id=21,
        text_raw="стиральную машину bosch",
        text_norm=normalize_text("стиральную машину bosch"),
    )

    fts = build_phrase_fts_query("стиральная машина -samsung")
    await watch_repo.add(user_id=user["id"], name="washer", fts_query=fts)

    assert await evaluate_message(db, blocked, "стиральную машину samsung") == []
    assert len(await evaluate_message(db, allowed, "стиральную машину bosch")) == 1

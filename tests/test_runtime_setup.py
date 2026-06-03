from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from telethon import utils as tl_utils
from telethon.tl.types import PeerChannel, PeerChat, PeerUser

from dealgoblin.ingest.collector import Collector
from dealgoblin.ingest.source_sync import sync_sources_from_env
from dealgoblin.storage.db import init_db
from dealgoblin.storage.repo import MessageRepo, SourceRepo
from dealgoblin.telethon_auth import ensure_user_session
from dealgoblin.tools.resolve_source import (
    extract_addlist_chat_ids,
    normalize_source_arg,
    parse_source_arg,
)


class _FakeTelethon:
    def __init__(self):
        self.handlers: list[tuple[object, object]] = []
        self._entities: dict[int, SimpleNamespace] = {}
        self._messages: dict[int, list[SimpleNamespace]] = {}

    def add_event_handler(self, callback, event_type):
        self.handlers.append((callback, event_type))

    async def get_entity(self, chat_id: int):
        entity = self._entities.get(chat_id)
        if entity is None:
            raise ValueError(f"Unknown chat_id: {chat_id}")
        return entity

    async def iter_messages(self, chat, limit: int):
        for message in self._messages.get(chat.chat_id, [])[:limit]:
            yield message


@pytest.fixture
async def db(tmp_path):
    conn = await init_db(str(tmp_path / "test.sqlite3"))
    yield conn
    await conn.close()


async def test_ensure_user_session_rejects_bot():
    client = SimpleNamespace(get_me=lambda: None)

    async def _bot_me():
        return SimpleNamespace(bot=True)

    client.get_me = _bot_me
    with pytest.raises(RuntimeError, match="user-authenticated"):
        await ensure_user_session(client)  # type: ignore[arg-type]


async def test_ensure_user_session_accepts_user():
    async def _user_me():
        return SimpleNamespace(bot=False)

    client = SimpleNamespace(get_me=_user_me)
    await ensure_user_session(client)  # type: ignore[arg-type]


async def test_sync_sources_from_env_updates_authoritative_set(db):
    repo = SourceRepo(db)
    await repo.add(chat_id=-1001, username="old", title="Old")
    await repo.add(chat_id=-1002, username="stale", title="Stale")

    client = _FakeTelethon()
    client._entities[-1001] = SimpleNamespace(username="u1", title="Title 1")
    client._entities[-1003] = SimpleNamespace(username="u3", title="Title 3")

    await sync_sources_from_env(client=client, source_repo=repo, chat_ids=[-1001, -1003])
    rows = await repo.list_all()
    assert {row["chat_id"] for row in rows} == {-1001, -1003}


async def test_collector_start_runs_backfill_and_dedupes(db):
    repo = SourceRepo(db)
    await repo.add(chat_id=-1001, username="chan", title="Channel")

    client = _FakeTelethon()
    client._entities[-1001] = SimpleNamespace(chat_id=-1001, username="chan")
    client._messages[-1001] = [
        SimpleNamespace(id=1, text="lamp", date=datetime(2026, 1, 1)),
        SimpleNamespace(id=1, text="lamp", date=datetime(2026, 1, 1)),
        SimpleNamespace(id=2, text=None, date=datetime(2026, 1, 1)),
        SimpleNamespace(id=3, text="table", date=datetime(2026, 1, 1)),
    ]
    ingested: list[tuple[int, str]] = []

    async def _on_ingest(rowid: int, text_norm: str):
        ingested.append((rowid, text_norm))

    collector = Collector(client=client, db=db, on_ingest=_on_ingest)
    await collector.start(backfill_limit=10)

    assert len(client.handlers) == 1
    assert len(ingested) == 2
    count = await MessageRepo(db).count_all()
    assert count == 2
    rows = await MessageRepo(db).list_recent(limit=10)
    assert {row["source_username"] for row in rows} == {"chan"}


def test_normalize_source_arg():
    assert normalize_source_arg("@baraholka_tbi") == "@baraholka_tbi"
    assert normalize_source_arg("https://t.me/baraholka_tbi") == "@baraholka_tbi"


def test_parse_source_arg_accepts_addlist():
    assert parse_source_arg("https://t.me/addlist/3q5RS6gv2pk2YzQy") == (
        "addlist",
        "3q5RS6gv2pk2YzQy",
    )


def test_normalize_source_arg_rejects_invalid():
    with pytest.raises(ValueError):
        parse_source_arg("https://t.me/addlist/")
    with pytest.raises(ValueError):
        parse_source_arg("not-a-link")


def test_extract_addlist_chat_ids_chatlist_invite_path():
    invite_result = SimpleNamespace(
        chats=[PeerChat(chat_id=321)],
        peers=[
            PeerChannel(channel_id=123),
            PeerUser(user_id=9),
            PeerChat(chat_id=555),
            PeerChannel(channel_id=123),
        ],
    )

    expected = sorted(
        {
            tl_utils.get_peer_id(PeerChat(chat_id=321)),
            tl_utils.get_peer_id(PeerChat(chat_id=555)),
            tl_utils.get_peer_id(PeerChannel(channel_id=123)),
        }
    )
    assert extract_addlist_chat_ids(invite_result) == expected


def test_extract_addlist_chat_ids_chatlist_invite_already_path():
    invite_result = SimpleNamespace(
        chats=[PeerChat(chat_id=17)],
        missing_peers=[PeerChannel(channel_id=777), PeerUser(user_id=8)],
        already_peers=[PeerChat(chat_id=17), PeerChat(chat_id=99)],
    )

    expected = sorted(
        {
            tl_utils.get_peer_id(PeerChat(chat_id=17)),
            tl_utils.get_peer_id(PeerChat(chat_id=99)),
            tl_utils.get_peer_id(PeerChannel(channel_id=777)),
        }
    )
    assert extract_addlist_chat_ids(invite_result) == expected

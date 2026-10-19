import sqlite3
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramUnauthorizedError,
)
from aiogram.methods import SendMessage

from dealgoblin.bot.notifier import Notifier
from dealgoblin.storage.db import init_db
from dealgoblin.storage.repo import BotUserRepo, MatchEventRepo, MessageRepo, WatchRepo


class _FakeBot:
    async def send_message(self, *_args, **_kwargs):
        return None


@pytest.fixture
async def queued_notifications(tmp_path):
    db = await init_db(str(tmp_path / "test.sqlite3"))
    try:
        watch_ids = {}
        for chat_id in (100, 200):
            user = await BotUserRepo(db).ensure(chat_id=chat_id, tg_user_id=chat_id)
            watch_ids[chat_id] = await WatchRepo(db).add(
                user_id=user["id"], name="lamps", fts_query="lamp"
            )
        event_ids = []
        for message_id, chat_id in enumerate((100, 200, 100), start=1):
            rowid = await MessageRepo(db).insert(
                chat_id=10, message_id=message_id, text_raw="lamp", text_norm="lamp"
            )
            event_ids.append(
                await MatchEventRepo(db).create(watch_id=watch_ids[chat_id], message_rowid=rowid)
            )
        yield db, event_ids
    finally:
        await db.close()


async def test_forbidden_recipient_does_not_block_queue(queued_notifications):
    db, _ = queued_notifications
    attempts = []
    delivered = []

    async def send_message(chat_id, text):
        attempts.append(chat_id)
        if chat_id == 100:
            raise TelegramForbiddenError(
                method=SendMessage(chat_id=chat_id, text=text),
                message="Forbidden: bot was blocked by the user",
            )
        delivered.append(chat_id)

    bot = _FakeBot()
    bot.send_message = AsyncMock(side_effect=send_message)
    notifier = Notifier(bot=bot, db=db)

    await notifier._poll()
    assert delivered == [200]
    assert await MatchEventRepo(db).list_pending() == []
    await notifier._poll()
    assert attempts == [100, 200, 100]
    assert len(await WatchRepo(db).list_enabled()) == 2

    # A new match can still be delivered if the user later unblocks the bot.
    watch = (await WatchRepo(db).list_all())[0]
    rowid = await MessageRepo(db).insert(
        chat_id=10, message_id=4, text_raw="lamp", text_norm="lamp"
    )
    await MatchEventRepo(db).create(watch_id=watch["id"], message_rowid=rowid)
    bot.send_message.side_effect = None
    await notifier._poll()
    assert bot.send_message.call_args.args[0] == 100
    assert await MatchEventRepo(db).list_pending() == []


@pytest.mark.parametrize(
    "error",
    [
        TelegramNetworkError(method=SendMessage(chat_id=100, text="lamp"), message="timeout"),
        TelegramRetryAfter(
            method=SendMessage(chat_id=100, text="lamp"), message="flood control", retry_after=5
        ),
        TelegramUnauthorizedError(
            method=SendMessage(chat_id=100, text="lamp"), message="Unauthorized"
        ),
    ],
)
async def test_other_send_errors_keep_notifications_pending(queued_notifications, error):
    db, event_ids = queued_notifications
    bot = _FakeBot()
    bot.send_message = AsyncMock(side_effect=error)
    notifier = Notifier(bot=bot, db=db)

    await notifier._poll()
    bot.send_message.assert_awaited_once()
    assert [event["id"] for event in await MatchEventRepo(db).list_pending()] == event_ids

    bot.send_message.reset_mock(side_effect=True)
    await notifier._poll()
    assert [call.args[0] for call in bot.send_message.call_args_list] == [100, 200, 100]
    assert await MatchEventRepo(db).list_pending() == []


async def test_notifier_reraises_corruption_error():
    notifier = Notifier(bot=_FakeBot(), db=object(), poll_interval=0.0)

    async def _poll() -> None:
        raise sqlite3.DatabaseError("database disk image is malformed")

    notifier._poll = _poll  # type: ignore[method-assign]

    try:
        await notifier.start()
    except sqlite3.DatabaseError as exc:
        assert "malformed" in str(exc).lower()
    else:
        raise AssertionError("Expected DatabaseError to be re-raised")


async def test_notifier_keeps_swallowing_non_corruption_errors():
    notifier = Notifier(bot=_FakeBot(), db=object(), poll_interval=0.0)
    calls = 0

    async def _poll() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("transient notifier error")
        notifier._running = False

    notifier._poll = _poll  # type: ignore[method-assign]

    await notifier.start()
    assert calls == 2

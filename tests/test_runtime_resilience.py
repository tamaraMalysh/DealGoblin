from __future__ import annotations

import asyncio
from contextlib import suppress
from types import SimpleNamespace
from typing import ClassVar

import pytest
from aiogram.types import BotCommandScopeAllPrivateChats, MenuButtonCommands

from dealgoblin import __main__ as runtime
from dealgoblin.config import Settings


def _make_settings(**overrides) -> Settings:
    values = {
        "telegram_api_id": 1,
        "telegram_api_hash": "h",
        "bot_token": "token:xxx",
        "owner_chat_id": 42,
        "source_chat_ids": [],
        "bot_healthcheck_interval_seconds": 60.0,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture
def patched_runtime(monkeypatch):
    state = SimpleNamespace()

    class FakeDB:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

    class FakeSession:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

    class FakeBot:
        last_instance = None
        healthcheck_failures_before_success = 0

        def __init__(self, token: str):
            self.token = token
            self.calls = 0
            self.session = FakeSession()
            self.set_my_commands_calls: list[dict[str, object]] = []
            self.set_chat_menu_button_calls: list[dict[str, object]] = []
            type(self).last_instance = self

        async def get_me(self):
            self.calls += 1
            if self.calls <= type(self).healthcheck_failures_before_success:
                raise RuntimeError("healthcheck failure")
            return {"id": 1}

        async def send_message(self, *_args, **_kwargs):
            return None

        async def set_my_commands(
            self,
            commands,
            scope=None,
            language_code=None,
            request_timeout=None,
        ):
            self.set_my_commands_calls.append(
                {
                    "commands": commands,
                    "scope": scope,
                    "language_code": language_code,
                    "request_timeout": request_timeout,
                }
            )
            return True

        async def set_chat_menu_button(self, chat_id=None, menu_button=None, request_timeout=None):
            self.set_chat_menu_button_calls.append(
                {
                    "chat_id": chat_id,
                    "menu_button": menu_button,
                    "request_timeout": request_timeout,
                }
            )
            return True

    class FakeDispatcher:
        polling_exception = None
        start_polling_calls: ClassVar[list[dict[str, object]]] = []
        stop_polling_calls = 0

        def __init__(self):
            self.workflow_data = {}

        def include_router(self, _router):
            return None

        def __setitem__(self, key, value):
            self.workflow_data[key] = value

        async def start_polling(self, _bot, handle_signals=False, close_bot_session=True):
            type(self).start_polling_calls.append(
                {
                    "handle_signals": handle_signals,
                    "close_bot_session": close_bot_session,
                }
            )
            exc = type(self).polling_exception
            if exc is not None:
                raise exc
            await asyncio.Event().wait()

        async def stop_polling(self):
            type(self).stop_polling_calls += 1
            return None

    class FakeTelethon:
        disconnect_exception = None
        last_instance = None
        last_kwargs: ClassVar[dict[str, object]] = {}

        def __init__(self, *_args, **kwargs):
            type(self).last_instance = self
            type(self).last_kwargs = kwargs
            self.disconnected = asyncio.get_running_loop().create_future()
            self.disconnect_called = False
            exc = type(self).disconnect_exception
            if exc is not None:
                self.disconnected.set_exception(exc)

        async def start(self):
            return None

        async def disconnect(self):
            self.disconnect_called = True
            if not self.disconnected.done():
                self.disconnected.set_result(None)

    class FakeSourceRepo:
        def __init__(self, db):
            self.db = db

    class FakeMessageRepo:
        def __init__(self, db):
            self.db = db

        async def get_by_rowid(self, _rowid):
            return None

    class FakeCollector:
        def __init__(self, client, db, on_ingest):
            self.client = client
            self.db = db
            self.on_ingest = on_ingest

        async def start(self, backfill_limit: int = 100):
            del backfill_limit
            return None

    class FakeNotifier:
        def __init__(self, bot, db):
            self.bot = bot
            self.db = db
            self.stopped = False

        async def start(self):
            await asyncio.Event().wait()

        async def stop(self):
            self.stopped = True

    async def fake_init_db(_path: str, busy_timeout_ms: int = 15000):
        del busy_timeout_ms
        db = FakeDB()
        state.db = db
        return db

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(runtime, "init_db", fake_init_db)
    monkeypatch.setattr(runtime, "ensure_user_session", _noop)
    monkeypatch.setattr(runtime, "sync_sources_from_env", _noop)
    monkeypatch.setattr(runtime, "evaluate_message", _noop)
    monkeypatch.setattr(runtime, "Bot", FakeBot)
    monkeypatch.setattr(runtime, "Dispatcher", FakeDispatcher)
    monkeypatch.setattr(runtime, "TelegramClient", FakeTelethon)
    monkeypatch.setattr(runtime, "SourceRepo", FakeSourceRepo)
    monkeypatch.setattr(runtime, "MessageRepo", FakeMessageRepo)
    monkeypatch.setattr(runtime, "Collector", FakeCollector)
    monkeypatch.setattr(runtime, "Notifier", FakeNotifier)

    state.fake_bot_cls = FakeBot
    state.fake_dispatcher_cls = FakeDispatcher
    state.fake_telethon_cls = FakeTelethon
    return state


async def test_run_once_restarts_on_telethon_disconnect_error(patched_runtime):
    patched_runtime.fake_telethon_cls.disconnect_exception = ConnectionError("dns failure")
    settings = _make_settings(telethon_connection_retries=-1, telethon_retry_delay_seconds=2.5)
    dp = runtime.Dispatcher()

    with pytest.raises(runtime.RuntimeRestartError, match="telethon-disconnected") as exc_info:
        await runtime._run_once(settings=settings, stop_event=asyncio.Event(), dp=dp)

    assert isinstance(exc_info.value.__cause__, ConnectionError)
    assert patched_runtime.fake_telethon_cls.last_kwargs["connection_retries"] == -1
    assert patched_runtime.fake_telethon_cls.last_kwargs["retry_delay"] == 2.5
    assert patched_runtime.fake_telethon_cls.last_kwargs["auto_reconnect"] is False
    assert patched_runtime.fake_telethon_cls.last_instance.disconnect_called is True
    assert patched_runtime.fake_bot_cls.last_instance.session.closed is True
    assert patched_runtime.db.closed is True


async def test_run_once_restarts_on_polling_failure(patched_runtime):
    patched_runtime.fake_dispatcher_cls.polling_exception = RuntimeError("polling exploded")
    settings = _make_settings()
    dp = runtime.Dispatcher()

    with pytest.raises(runtime.RuntimeRestartError, match="polling") as exc_info:
        await runtime._run_once(settings=settings, stop_event=asyncio.Event(), dp=dp)

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    start_call = patched_runtime.fake_dispatcher_cls.start_polling_calls[0]
    assert start_call["close_bot_session"] is False
    assert start_call["handle_signals"] is False
    assert patched_runtime.fake_telethon_cls.last_instance.disconnect_called is True
    assert patched_runtime.fake_bot_cls.last_instance.session.closed is True
    assert patched_runtime.db.closed is True


async def test_run_once_configures_private_menu_button_and_commands(patched_runtime):
    patched_runtime.fake_dispatcher_cls.polling_exception = RuntimeError("polling exploded")
    settings = _make_settings()
    dp = runtime.Dispatcher()

    with pytest.raises(runtime.RuntimeRestartError, match="polling"):
        await runtime._run_once(settings=settings, stop_event=asyncio.Event(), dp=dp)

    bot = patched_runtime.fake_bot_cls.last_instance
    assert bot is not None
    assert len(bot.set_my_commands_calls) == 1
    assert len(bot.set_chat_menu_button_calls) == 1

    command_call = bot.set_my_commands_calls[0]
    commands = command_call["commands"]
    assert len(commands) == 1
    assert commands[0].command == "menu"
    assert commands[0].description == "Menu"
    assert isinstance(command_call["scope"], BotCommandScopeAllPrivateChats)

    menu_call = bot.set_chat_menu_button_calls[0]
    assert menu_call["chat_id"] is None
    assert isinstance(menu_call["menu_button"], MenuButtonCommands)


async def test_run_supervised_retries_with_capped_backoff(monkeypatch):
    settings = _make_settings(
        runtime_restart_base_delay_seconds=3.0,
        runtime_restart_max_delay_seconds=5.0,
    )
    attempts = {"count": 0}
    sleep_delays: list[float] = []

    class FakeDispatcher:
        def include_router(self, _router):
            return None

    async def fake_run_once(settings: Settings, stop_event: asyncio.Event, dp) -> bool:
        del settings, stop_event, dp
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("transient failure")
        return True

    async def fake_sleep(delay: float):
        sleep_delays.append(delay)

    class FakeLock:
        released = False

        def release(self):
            self.released = True

    fake_lock = FakeLock()

    monkeypatch.setattr(runtime, "Settings", lambda: settings)
    monkeypatch.setattr(runtime, "_install_signal_handlers", lambda _stop_event: None)
    monkeypatch.setattr(runtime, "Dispatcher", FakeDispatcher)
    monkeypatch.setattr(runtime, "acquire_runtime_lock", lambda _path: fake_lock)
    monkeypatch.setattr(runtime, "_run_once", fake_run_once)
    monkeypatch.setattr(runtime.asyncio, "sleep", fake_sleep)

    await runtime.run_supervised()

    assert attempts["count"] == 3
    assert sleep_delays == [3.0, 5.0]
    assert fake_lock.released is True


async def test_run_supervised_stops_without_restart_sleep(monkeypatch):
    settings = _make_settings()
    attempts = {"count": 0}

    class FakeDispatcher:
        def include_router(self, _router):
            return None

    async def fake_run_once(settings: Settings, stop_event: asyncio.Event, dp) -> bool:
        del settings, stop_event, dp
        attempts["count"] += 1
        return True

    async def fake_sleep(_delay: float):
        raise AssertionError("sleep should not be called when shutdown is intentional")

    class FakeLock:
        released = False

        def release(self):
            self.released = True

    fake_lock = FakeLock()

    monkeypatch.setattr(runtime, "Settings", lambda: settings)
    monkeypatch.setattr(runtime, "_install_signal_handlers", lambda _stop_event: None)
    monkeypatch.setattr(runtime, "Dispatcher", FakeDispatcher)
    monkeypatch.setattr(runtime, "acquire_runtime_lock", lambda _path: fake_lock)
    monkeypatch.setattr(runtime, "_run_once", fake_run_once)
    monkeypatch.setattr(runtime.asyncio, "sleep", fake_sleep)

    await runtime.run_supervised()

    assert attempts["count"] == 1
    assert fake_lock.released is True


async def test_run_supervised_attaches_router_once_across_retries(monkeypatch):
    settings = _make_settings(
        runtime_restart_base_delay_seconds=1.0,
        runtime_restart_max_delay_seconds=10.0,
    )
    attempts = {"count": 0}
    seen_dp_ids: list[int] = []

    class FakeDispatcher:
        instances_created = 0
        include_router_calls = 0

        def __init__(self):
            type(self).instances_created += 1

        def include_router(self, _router):
            type(self).include_router_calls += 1

    async def fake_run_once(settings: Settings, stop_event: asyncio.Event, dp) -> bool:
        del settings, stop_event
        attempts["count"] += 1
        seen_dp_ids.append(id(dp))
        if attempts["count"] < 3:
            raise RuntimeError("transient failure")
        return True

    async def fake_sleep(_delay: float):
        return None

    class FakeLock:
        released = False

        def release(self):
            self.released = True

    fake_lock = FakeLock()

    monkeypatch.setattr(runtime, "Settings", lambda: settings)
    monkeypatch.setattr(runtime, "_install_signal_handlers", lambda _stop_event: None)
    monkeypatch.setattr(runtime, "Dispatcher", FakeDispatcher)
    monkeypatch.setattr(runtime, "acquire_runtime_lock", lambda _path: fake_lock)
    monkeypatch.setattr(runtime, "_run_once", fake_run_once)
    monkeypatch.setattr(runtime.asyncio, "sleep", fake_sleep)

    await runtime.run_supervised()

    assert attempts["count"] == 3
    assert FakeDispatcher.instances_created == 1
    assert FakeDispatcher.include_router_calls == 1
    assert len(set(seen_dp_ids)) == 1
    assert fake_lock.released is True


async def test_shutdown_polling_calls_stop_before_cancel_fallback(monkeypatch):
    calls: list[str] = []
    cancel_targets: list[str] = []
    wait_for_counter = {"count": 0}

    class FakeDispatcher:
        async def stop_polling(self):
            calls.append("stop")
            return None

    async def fake_wait_for(awaitable, timeout):
        del timeout
        wait_for_counter["count"] += 1
        if wait_for_counter["count"] == 1:
            return await awaitable
        raise TimeoutError

    async def fake_cancel_and_wait(task):
        cancel_targets.append(task.get_name())
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    polling_task = asyncio.create_task(asyncio.Event().wait(), name="polling")
    monkeypatch.setattr(runtime.asyncio, "wait_for", fake_wait_for)
    monkeypatch.setattr(runtime, "_cancel_and_wait", fake_cancel_and_wait)

    await runtime._shutdown_polling(FakeDispatcher(), polling_task, timeout_seconds=0.1)

    assert calls == ["stop"]
    assert cancel_targets == ["polling"]


async def test_run_supervised_exits_when_runtime_lock_is_held(monkeypatch):
    settings = _make_settings()
    run_once_calls = {"count": 0}

    class FakeDispatcher:
        def include_router(self, _router):
            return None

    async def fake_run_once(settings: Settings, stop_event: asyncio.Event, dp) -> bool:
        del settings, stop_event, dp
        run_once_calls["count"] += 1
        return True

    def fake_acquire_runtime_lock(_path: str):
        raise runtime.RuntimeInstanceLockedError("lock held")

    monkeypatch.setattr(runtime, "Settings", lambda: settings)
    monkeypatch.setattr(runtime, "_install_signal_handlers", lambda _stop_event: None)
    monkeypatch.setattr(runtime, "Dispatcher", FakeDispatcher)
    monkeypatch.setattr(runtime, "_run_once", fake_run_once)
    monkeypatch.setattr(runtime, "acquire_runtime_lock", fake_acquire_runtime_lock)

    with pytest.raises(runtime.RuntimeInstanceLockedError, match="lock held"):
        await runtime.run_supervised()

    assert run_once_calls["count"] == 0

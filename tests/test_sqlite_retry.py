import sqlite3

import pytest

from dealgoblin.storage import sqlite_retry


async def test_sqlite_retry_succeeds_after_transient_lock(monkeypatch):
    delays: list[float] = []
    attempts = 0
    rollback_calls = 0

    async def _fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    async def _on_retry() -> None:
        nonlocal rollback_calls
        rollback_calls += 1

    async def _operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise sqlite3.OperationalError("database is locked")
        return "ok"

    monkeypatch.setattr(sqlite_retry.asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(sqlite_retry.random, "uniform", lambda _a, _b: 0.0)

    result = await sqlite_retry.run_with_sqlite_lock_retry(
        _operation,
        operation_name="test.transient",
        on_retry=_on_retry,
    )

    assert result == "ok"
    assert attempts == 3
    assert rollback_calls == 2
    assert delays == [0.05, 0.1]


async def test_sqlite_retry_exhausts_and_raises(monkeypatch):
    delays: list[float] = []
    attempts = 0
    rollback_calls = 0

    async def _fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    async def _on_retry() -> None:
        nonlocal rollback_calls
        rollback_calls += 1

    async def _operation() -> None:
        nonlocal attempts
        attempts += 1
        raise sqlite3.OperationalError("database table is locked")

    monkeypatch.setattr(sqlite_retry.asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(sqlite_retry.random, "uniform", lambda _a, _b: 0.0)

    with pytest.raises(sqlite3.OperationalError, match="locked"):
        await sqlite_retry.run_with_sqlite_lock_retry(
            _operation,
            operation_name="test.exhausted",
            on_retry=_on_retry,
        )

    assert attempts == sqlite_retry.MAX_ATTEMPTS
    assert rollback_calls == sqlite_retry.MAX_ATTEMPTS - 1
    assert delays == [0.05, 0.1, 0.2, 0.4]


async def test_sqlite_retry_does_not_retry_unrelated_operational_error(monkeypatch):
    attempts = 0
    rollback_calls = 0

    async def _on_retry() -> None:
        nonlocal rollback_calls
        rollback_calls += 1

    async def _operation() -> None:
        nonlocal attempts
        attempts += 1
        raise sqlite3.OperationalError("no such table: missing")

    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        await sqlite_retry.run_with_sqlite_lock_retry(
            _operation,
            operation_name="test.non_lock_error",
            on_retry=_on_retry,
        )

    assert attempts == 1
    assert rollback_calls == 0

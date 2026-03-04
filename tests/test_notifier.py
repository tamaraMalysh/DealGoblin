import sqlite3

from dealgoblin.bot.notifier import Notifier


class _FakeBot:
    async def send_message(self, *_args, **_kwargs):
        return None


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

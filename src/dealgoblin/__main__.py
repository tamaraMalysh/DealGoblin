from __future__ import annotations

import asyncio
import logging
import signal
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, MenuButtonCommands
from telethon import TelegramClient

from dealgoblin.bot.handlers import router
from dealgoblin.bot.notifier import Notifier
from dealgoblin.config import Settings
from dealgoblin.ingest.collector import Collector
from dealgoblin.ingest.source_sync import sync_sources_from_env
from dealgoblin.match.matcher import evaluate_message
from dealgoblin.storage.db import init_db
from dealgoblin.storage.repo import MessageRepo, SourceRepo
from dealgoblin.telethon_auth import ensure_user_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
logging.getLogger("dealgoblin").setLevel(logging.DEBUG)


class RuntimeRestartError(RuntimeError):
    pass


class BotHealthcheckError(RuntimeError):
    pass


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    def _signal_handler() -> None:
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, _signal_handler)


async def _cancel_and_wait(task: asyncio.Task[object] | None) -> None:
    if task is None:
        return
    if not task.done():
        task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.debug(f"Task %r ended with an exception during shutdown {e}", task, exc_info=True)


async def _monitor_telethon_disconnected(client: TelegramClient) -> None:
    await client.disconnected


async def _bot_healthcheck_loop(
    bot: Bot,
    interval_seconds: float,
    failure_threshold: int,
) -> None:
    failures = 0
    while True:
        try:
            await bot.get_me()
            if failures:
                logger.info("Bot API healthcheck recovered after %d consecutive failures", failures)
                failures = 0
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            failures += 1
            logger.warning(
                "Bot API healthcheck failed (%d/%d)",
                failures,
                failure_threshold,
                exc_info=True,
            )
            if failures >= failure_threshold:
                raise BotHealthcheckError(
                    f"Bot healthcheck failed {failures} time(s) in a row"
                ) from exc
        await asyncio.sleep(interval_seconds)


async def _configure_bot_menu(bot: Bot) -> None:
    await bot.set_my_commands(
        commands=[BotCommand(command="menu", description="Menu")],
        scope=BotCommandScopeAllPrivateChats(),
    )
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())


async def _run_once(
    settings: Settings,
    stop_event: asyncio.Event,
    dp: Dispatcher,
) -> bool:
    db = None
    telethon = None
    bot = None
    notifier = None
    notifier_task = None
    polling_task = None
    telethon_disconnected_task = None
    healthcheck_task = None
    stop_wait_task = None

    try:
        db = await init_db(settings.db_path)

        telethon = TelegramClient(
            settings.session_path,
            settings.telegram_api_id,
            settings.telegram_api_hash,
            connection_retries=settings.telethon_connection_retries,
            retry_delay=settings.telethon_retry_delay_seconds,
            # Telethon's internal auto-reconnect can get stuck in a bad state
            # during shutdown/restart races; supervisor restarts recover cleanly.
            auto_reconnect=False,
        )
        await telethon.start()
        await ensure_user_session(telethon)

        source_repo = SourceRepo(db)
        await sync_sources_from_env(
            client=telethon,
            source_repo=source_repo,
            chat_ids=settings.source_chat_ids,
        )
        msg_repo = MessageRepo(db)

        bot = Bot(token=settings.bot_token)
        await _configure_bot_menu(bot)
        dp["db"] = db

        async def on_ingest(rowid: int, text_norm: str):
            await evaluate_message(db, rowid, text_norm)
            if not settings.forward_all_ingested:
                return

            msg = await msg_repo.get_by_rowid(rowid)
            if not msg:
                return
            snippet = (msg.get("text_raw") or "")[:3400]
            link = msg.get("link") or ""
            text = f"Source: {msg['chat_id']}\n\n{snippet}"
            if link:
                text = f"{text}\n\n{link}"
            try:
                await bot.send_message(settings.owner_chat_id, text)
            except Exception:
                logger.exception("Failed to forward ingested message rowid=%s", rowid)

        collector = Collector(client=telethon, db=db, on_ingest=on_ingest)
        await collector.start(backfill_limit=settings.source_backfill_limit)

        notifier = Notifier(bot=bot, db=db)
        notifier_task = asyncio.create_task(notifier.start(), name="notifier")
        polling_task = asyncio.create_task(
            dp.start_polling(bot, handle_signals=False),
            name="polling",
        )
        telethon_disconnected_task = asyncio.create_task(
            _monitor_telethon_disconnected(telethon),
            name="telethon-disconnected",
        )
        healthcheck_task = asyncio.create_task(
            _bot_healthcheck_loop(
                bot=bot,
                interval_seconds=settings.bot_healthcheck_interval_seconds,
                failure_threshold=settings.bot_healthcheck_failure_threshold,
            ),
            name="bot-healthcheck",
        )
        stop_wait_task = asyncio.create_task(stop_event.wait(), name="shutdown-wait")

        critical_tasks: set[asyncio.Task[object]] = {
            stop_wait_task,
            polling_task,
            notifier_task,
            telethon_disconnected_task,
            healthcheck_task,
        }
        done, _ = await asyncio.wait(critical_tasks, return_when=asyncio.FIRST_COMPLETED)

        if stop_wait_task in done:
            return True

        for task in done:
            if task is stop_wait_task:
                continue
            task_name = task.get_name()
            try:
                await task
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                raise RuntimeRestartError(f"Runtime task '{task_name}' failed") from exc
            raise RuntimeRestartError(f"Runtime task '{task_name}' stopped unexpectedly")

        raise RuntimeRestartError("Runtime loop exited unexpectedly")
    finally:
        logger.info("Shutting down runtime iteration...")
        if notifier is not None:
            await notifier.stop()
        await _cancel_and_wait(stop_wait_task)
        await _cancel_and_wait(healthcheck_task)
        await _cancel_and_wait(telethon_disconnected_task)
        await _cancel_and_wait(polling_task)
        await _cancel_and_wait(notifier_task)

        try:
            await asyncio.wait_for(dp.stop_polling(), timeout=5)
        except Exception as e:
            logger.debug("Polling stop raised during shutdown: %s", e)

        if telethon is not None:
            try:
                await telethon.disconnect()
            except Exception:
                logger.exception("Failed to disconnect Telethon cleanly")
        if db is not None:
            await db.close()
        if bot is not None:
            await bot.session.close()
        logger.info("Runtime iteration shutdown complete")


async def run_supervised() -> None:
    settings = Settings()
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)
    dp = Dispatcher()
    dp.include_router(router)

    restart_delay = settings.runtime_restart_base_delay_seconds
    while True:
        try:
            should_stop = await _run_once(
                settings=settings,
                stop_event=stop_event,
                dp=dp,
            )
            if should_stop:
                logger.info("Supervisor received stop signal; exiting")
                return
        except asyncio.CancelledError:
            raise
        except Exception:
            if stop_event.is_set():
                logger.info("Stop signal is set; exiting supervisor after runtime failure")
                return
            logger.exception(
                "Runtime failed; restarting in %.1f second(s)",
                restart_delay,
            )
            await asyncio.sleep(restart_delay)
            restart_delay = min(
                settings.runtime_restart_max_delay_seconds,
                restart_delay * 2,
            )


async def run() -> None:
    await run_supervised()


def main() -> None:
    try:
        asyncio.run(run_supervised())
    except KeyboardInterrupt:
        logger.info("Interrupted by user (Ctrl+C)")


if __name__ == "__main__":
    main()

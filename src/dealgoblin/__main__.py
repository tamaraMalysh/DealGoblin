from __future__ import annotations

import asyncio
import logging
import signal

from aiogram import Bot, Dispatcher
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


async def run():
    settings = Settings()
    db = await init_db(settings.db_path)

    # Telethon client
    telethon = TelegramClient(
        settings.session_path,
        settings.telegram_api_id,
        settings.telegram_api_hash,
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

    # aiogram bot
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    # Share state via dispatcher workflow data (injected as handler kwargs)
    dp["db"] = db

    # Matcher callback
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

    # Collector
    collector = Collector(client=telethon, db=db, on_ingest=on_ingest)
    await collector.start(backfill_limit=settings.source_backfill_limit)

    # Notifier
    notifier = Notifier(bot=bot, db=db)
    notifier_task = asyncio.create_task(notifier.start())

    # Graceful shutdown
    stop_event = asyncio.Event()

    def _signal_handler():
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    # Start polling (non-blocking)
    polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))

    try:
        stop_wait_task = asyncio.create_task(stop_event.wait())
        done, _ = await asyncio.wait(
            {stop_wait_task, polling_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if polling_task in done:
            # Surface polling errors instead of silently exiting.
            await polling_task
    finally:
        # Cleanup
        logger.info("Shutting down...")
        await notifier.stop()
        notifier_task.cancel()
        polling_task.cancel()
        try:
            await asyncio.wait_for(dp.stop_polling(), timeout=5)
        except (TimeoutError, Exception) as e:
            logger.error("Polling stop timed out, forcing shutdown: %s", e)
        await telethon.disconnect()
        await db.close()
        await bot.session.close()
        logger.info("Shutdown complete")


def main():
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user (Ctrl+C)")


if __name__ == "__main__":
    main()

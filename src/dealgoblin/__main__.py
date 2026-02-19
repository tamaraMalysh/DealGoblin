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
from dealgoblin.match.matcher import evaluate_message
from dealgoblin.storage.db import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run():
    settings = Settings()
    db = await init_db(settings.db_path)

    # Telethon client
    telethon = TelegramClient(
        settings.session_path, settings.telegram_api_id, settings.telegram_api_hash
    )
    await telethon.start()

    # aiogram bot
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    # Share state via dispatcher workflow data (injected as handler kwargs)
    dp["db"] = db
    dp["telethon"] = telethon

    # Matcher callback
    async def on_ingest(rowid: int, text_norm: str):
        await evaluate_message(db, rowid, text_norm)

    # Collector
    collector = Collector(client=telethon, db=db, on_ingest=on_ingest)
    await collector.start()

    # Notifier
    notifier = Notifier(bot=bot, db=db, owner_chat_id=settings.owner_chat_id)
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
    polling_task = asyncio.create_task(dp.start_polling(bot))

    await stop_event.wait()

    # Cleanup
    logger.info("Shutting down...")
    await notifier.stop()
    notifier_task.cancel()
    await dp.stop_polling()
    polling_task.cancel()
    await telethon.disconnect()
    await db.close()
    await bot.session.close()
    logger.info("Shutdown complete")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()

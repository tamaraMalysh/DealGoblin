from __future__ import annotations

import asyncio
import logging
import random
import sqlite3
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
BASE_DELAY_SECONDS = 0.05
MAX_DELAY_SECONDS = 1.0
JITTER_CAP_SECONDS = 0.05
JITTER_RATIO = 0.2


def _is_lock_error(exc: sqlite3.OperationalError) -> bool:
    message = str(exc).lower()
    return "locked" in message or "busy" in message


async def run_with_sqlite_lock_retry[T](
    operation: Callable[[], Awaitable[T]],
    *,
    operation_name: str,
    on_retry: Callable[[], Awaitable[None]] | None = None,
) -> T:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return await operation()
        except sqlite3.OperationalError as exc:
            if not _is_lock_error(exc):
                raise

            if attempt >= MAX_ATTEMPTS:
                logger.error(
                    "SQLite lock retries exhausted op=%s attempts=%d error=%s",
                    operation_name,
                    MAX_ATTEMPTS,
                    exc,
                )
                raise

            if on_retry is not None:
                try:
                    await on_retry()
                except Exception:
                    logger.debug(
                        "Rollback hook failed before SQLite retry op=%s",
                        operation_name,
                        exc_info=True,
                    )

            base_delay = min(MAX_DELAY_SECONDS, BASE_DELAY_SECONDS * (2 ** (attempt - 1)))
            jitter = random.uniform(0.0, min(JITTER_CAP_SECONDS, base_delay * JITTER_RATIO))
            sleep_seconds = base_delay + jitter
            logger.warning(
                "SQLite lock detected; retrying op=%s attempt=%d/%d delay=%.3fs error=%s",
                operation_name,
                attempt,
                MAX_ATTEMPTS,
                sleep_seconds,
                exc,
            )
            await asyncio.sleep(sleep_seconds)

    raise RuntimeError("unreachable")

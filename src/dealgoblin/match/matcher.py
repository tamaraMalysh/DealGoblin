from __future__ import annotations

import aiosqlite

from dealgoblin.match.price import extract_prices, price_matches_filter
from dealgoblin.storage.repo import MatchEventRepo, MessageRepo, WatchRepo


async def evaluate_message(
    db: aiosqlite.Connection,
    message_rowid: int,
    text_norm: str,
    duplicate_suppression_days: int = 14,
) -> list[int]:
    """Evaluate all enabled watches against a message. Returns list of created match_event IDs."""
    watch_repo = WatchRepo(db)
    me_repo = MatchEventRepo(db)
    msg_repo = MessageRepo(db)
    message = await msg_repo.get_by_rowid(message_rowid)
    dedupe_key = message.get("dedupe_key") if message else None
    watches = await watch_repo.list_enabled()
    created = []
    for watch in watches:
        async with db.execute(
            "SELECT rowid FROM messages_fts WHERE messages_fts MATCH ? AND rowid = ?",
            (watch["fts_query"], message_rowid),
        ) as cur:
            if not await cur.fetchone():
                continue
        if watch["price_min"] is not None or watch["price_max"] is not None:
            prices = extract_prices(text_norm)
            if not price_matches_filter(prices, watch["price_min"], watch["price_max"]):
                continue
        if dedupe_key and await me_repo.has_recent_duplicate(
            watch_id=watch["id"],
            dedupe_key=dedupe_key,
            duplicate_suppression_days=duplicate_suppression_days,
        ):
            continue
        event_id = await me_repo.create(watch_id=watch["id"], message_rowid=message_rowid)
        if event_id is not None:
            created.append(event_id)
    return created

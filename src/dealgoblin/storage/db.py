from pathlib import Path

import aiosqlite

from dealgoblin.storage.schema import SCHEMA_SQL


async def init_db(path: str) -> aiosqlite.Connection:
    # Ensure the parent directory exists so connecting doesn't fail on first run.
    db_path = Path(path)
    if db_path.parent:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(path)
    await conn.executescript(SCHEMA_SQL)
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    await conn.commit()
    return conn

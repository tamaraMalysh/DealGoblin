from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env"}

    telegram_api_id: int
    telegram_api_hash: str
    bot_token: str
    owner_chat_id: int
    db_path: str = str(Path("data") / "dealgoblin.sqlite3")
    session_path: str = str(Path("data") / "telethon.session")

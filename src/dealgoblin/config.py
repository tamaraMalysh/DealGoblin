from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    model_config = {"env_file": ".env"}

    telegram_api_id: int
    telegram_api_hash: str
    bot_token: str
    owner_chat_id: int
    db_path: str = str(Path("data") / "dealgoblin.sqlite3")
    session_path: str = str(Path("data") / "telethon.session")
    source_chat_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)
    source_backfill_limit: int = 100
    forward_all_ingested: bool = False

    @field_validator("source_chat_ids", mode="before")
    @classmethod
    def _parse_source_chat_ids(cls, value: object) -> list[int]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",") if part.strip()]
            try:
                return [int(part) for part in parts]
            except ValueError as exc:
                raise ValueError(
                    "SOURCE_CHAT_IDS must be a comma-separated list of integers"
                ) from exc
        if isinstance(value, list):
            try:
                return [int(item) for item in value]
            except ValueError as exc:
                raise ValueError("SOURCE_CHAT_IDS must contain integer values") from exc
        raise TypeError("SOURCE_CHAT_IDS must be a string or list of integers")

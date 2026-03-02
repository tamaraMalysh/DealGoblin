from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator
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
    telethon_connection_retries: int = -1
    telethon_retry_delay_seconds: float = 1.0
    runtime_restart_base_delay_seconds: float = 3.0
    runtime_restart_max_delay_seconds: float = 30.0
    bot_healthcheck_interval_seconds: float = 15.0
    bot_healthcheck_failure_threshold: int = 8
    duplicate_suppression_days: int = 14

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

    @field_validator(
        "telethon_retry_delay_seconds",
        "runtime_restart_base_delay_seconds",
        "runtime_restart_max_delay_seconds",
        "bot_healthcheck_interval_seconds",
    )
    @classmethod
    def _validate_positive_float(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("must be greater than 0")
        return value

    @field_validator("bot_healthcheck_failure_threshold")
    @classmethod
    def _validate_healthcheck_threshold(cls, value: int) -> int:
        if value < 1:
            raise ValueError("must be greater than or equal to 1")
        return value

    @field_validator("duplicate_suppression_days")
    @classmethod
    def _validate_duplicate_suppression_days(cls, value: int) -> int:
        if value < 1:
            raise ValueError("must be greater than or equal to 1")
        return value

    @model_validator(mode="after")
    def _validate_restart_backoff(self) -> "Settings":
        if self.runtime_restart_max_delay_seconds < self.runtime_restart_base_delay_seconds:
            raise ValueError(
                "RUNTIME_RESTART_MAX_DELAY_SECONDS must be greater than or equal to "
                "RUNTIME_RESTART_BASE_DELAY_SECONDS"
            )
        return self

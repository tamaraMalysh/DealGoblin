import pytest

from dealgoblin.config import Settings


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "123456")
    monkeypatch.setenv("TELEGRAM_API_HASH", "abcdef")
    monkeypatch.setenv("BOT_TOKEN", "token:xxx")
    monkeypatch.setenv("OWNER_CHAT_ID", "789")
    monkeypatch.setenv("SOURCE_CHAT_IDS", "-1001,-1002")
    monkeypatch.setenv("DB_BUSY_TIMEOUT_MS", "20000")
    monkeypatch.setenv("SOURCE_BACKFILL_LIMIT", "150")
    monkeypatch.setenv("FORWARD_ALL_INGESTED", "true")
    monkeypatch.setenv("TELETHON_CONNECTION_RETRIES", "7")
    monkeypatch.setenv("TELETHON_RETRY_DELAY_SECONDS", "2.5")
    monkeypatch.setenv("RUNTIME_RESTART_BASE_DELAY_SECONDS", "4.0")
    monkeypatch.setenv("RUNTIME_RESTART_MAX_DELAY_SECONDS", "20.0")
    monkeypatch.setenv("RUNTIME_LOCK_PATH", "/tmp/dealgoblin-runtime.lock")
    monkeypatch.setenv("BOT_HEALTHCHECK_INTERVAL_SECONDS", "6.0")
    monkeypatch.setenv("BOT_HEALTHCHECK_FAILURE_THRESHOLD", "3")
    monkeypatch.setenv("DUPLICATE_SUPPRESSION_DAYS", "21")
    s = Settings(_env_file=None)
    assert s.telegram_api_id == 123456
    assert s.telegram_api_hash == "abcdef"
    assert s.bot_token == "token:xxx"
    assert s.owner_chat_id == 789
    assert s.source_chat_ids == [-1001, -1002]
    assert s.db_busy_timeout_ms == 20000
    assert s.source_backfill_limit == 150
    assert s.forward_all_ingested is True
    assert s.telethon_connection_retries == 7
    assert s.telethon_retry_delay_seconds == 2.5
    assert s.runtime_restart_base_delay_seconds == 4.0
    assert s.runtime_restart_max_delay_seconds == 20.0
    assert s.runtime_lock_path == "/tmp/dealgoblin-runtime.lock"
    assert s.bot_healthcheck_interval_seconds == 6.0
    assert s.bot_healthcheck_failure_threshold == 3
    assert s.duplicate_suppression_days == 21


def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "1")
    monkeypatch.setenv("TELEGRAM_API_HASH", "h")
    monkeypatch.setenv("BOT_TOKEN", "t")
    monkeypatch.setenv("OWNER_CHAT_ID", "1")
    monkeypatch.delenv("SOURCE_CHAT_IDS", raising=False)
    monkeypatch.delenv("DB_BUSY_TIMEOUT_MS", raising=False)
    monkeypatch.delenv("SOURCE_BACKFILL_LIMIT", raising=False)
    monkeypatch.delenv("FORWARD_ALL_INGESTED", raising=False)
    monkeypatch.delenv("TELETHON_CONNECTION_RETRIES", raising=False)
    monkeypatch.delenv("TELETHON_RETRY_DELAY_SECONDS", raising=False)
    monkeypatch.delenv("RUNTIME_RESTART_BASE_DELAY_SECONDS", raising=False)
    monkeypatch.delenv("RUNTIME_RESTART_MAX_DELAY_SECONDS", raising=False)
    monkeypatch.delenv("RUNTIME_LOCK_PATH", raising=False)
    monkeypatch.delenv("BOT_HEALTHCHECK_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("BOT_HEALTHCHECK_FAILURE_THRESHOLD", raising=False)
    monkeypatch.delenv("DUPLICATE_SUPPRESSION_DAYS", raising=False)
    s = Settings(_env_file=None)
    assert s.db_path.endswith("dealgoblin.sqlite3")
    assert s.session_path.endswith("telethon.session")
    assert s.source_chat_ids == []
    assert s.db_busy_timeout_ms == 15000
    assert s.source_backfill_limit == 100
    assert s.forward_all_ingested is False
    assert s.telethon_connection_retries == -1
    assert s.telethon_retry_delay_seconds == 1.0
    assert s.runtime_restart_base_delay_seconds == 3.0
    assert s.runtime_restart_max_delay_seconds == 30.0
    assert s.runtime_lock_path.endswith("runtime.lock")
    assert s.bot_healthcheck_interval_seconds == 15.0
    assert s.bot_healthcheck_failure_threshold == 8
    assert s.duplicate_suppression_days == 14


def test_settings_invalid_source_chat_ids(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "1")
    monkeypatch.setenv("TELEGRAM_API_HASH", "h")
    monkeypatch.setenv("BOT_TOKEN", "t")
    monkeypatch.setenv("OWNER_CHAT_ID", "1")
    monkeypatch.setenv("SOURCE_CHAT_IDS", "-1001,abc")
    with pytest.raises(Exception, match="source_chat_ids"):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    ("env_name", "env_value", "match"),
    [
        ("TELETHON_RETRY_DELAY_SECONDS", "0", "telethon_retry_delay_seconds"),
        ("DB_BUSY_TIMEOUT_MS", "999", "db_busy_timeout_ms"),
        ("RUNTIME_RESTART_BASE_DELAY_SECONDS", "0", "runtime_restart_base_delay_seconds"),
        ("RUNTIME_RESTART_MAX_DELAY_SECONDS", "0", "runtime_restart_max_delay_seconds"),
        ("BOT_HEALTHCHECK_INTERVAL_SECONDS", "0", "bot_healthcheck_interval_seconds"),
        ("BOT_HEALTHCHECK_FAILURE_THRESHOLD", "0", "bot_healthcheck_failure_threshold"),
        ("DUPLICATE_SUPPRESSION_DAYS", "0", "duplicate_suppression_days"),
    ],
)
def test_settings_invalid_resilience_values(monkeypatch, env_name, env_value, match):
    monkeypatch.setenv("TELEGRAM_API_ID", "1")
    monkeypatch.setenv("TELEGRAM_API_HASH", "h")
    monkeypatch.setenv("BOT_TOKEN", "t")
    monkeypatch.setenv("OWNER_CHAT_ID", "1")
    monkeypatch.setenv(env_name, env_value)
    with pytest.raises(Exception, match=match):
        Settings(_env_file=None)


def test_settings_invalid_restart_backoff_range(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "1")
    monkeypatch.setenv("TELEGRAM_API_HASH", "h")
    monkeypatch.setenv("BOT_TOKEN", "t")
    monkeypatch.setenv("OWNER_CHAT_ID", "1")
    monkeypatch.setenv("RUNTIME_RESTART_BASE_DELAY_SECONDS", "10")
    monkeypatch.setenv("RUNTIME_RESTART_MAX_DELAY_SECONDS", "5")
    with pytest.raises(Exception, match="RUNTIME_RESTART_MAX_DELAY_SECONDS"):
        Settings(_env_file=None)

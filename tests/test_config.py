import pytest

from dealgoblin.config import Settings


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "123456")
    monkeypatch.setenv("TELEGRAM_API_HASH", "abcdef")
    monkeypatch.setenv("BOT_TOKEN", "token:xxx")
    monkeypatch.setenv("OWNER_CHAT_ID", "789")
    monkeypatch.setenv("SOURCE_CHAT_IDS", "-1001,-1002")
    monkeypatch.setenv("SOURCE_BACKFILL_LIMIT", "150")
    monkeypatch.setenv("FORWARD_ALL_INGESTED", "true")
    s = Settings(_env_file=None)
    assert s.telegram_api_id == 123456
    assert s.telegram_api_hash == "abcdef"
    assert s.bot_token == "token:xxx"
    assert s.owner_chat_id == 789
    assert s.source_chat_ids == [-1001, -1002]
    assert s.source_backfill_limit == 150
    assert s.forward_all_ingested is True


def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "1")
    monkeypatch.setenv("TELEGRAM_API_HASH", "h")
    monkeypatch.setenv("BOT_TOKEN", "t")
    monkeypatch.setenv("OWNER_CHAT_ID", "1")
    monkeypatch.delenv("SOURCE_CHAT_IDS", raising=False)
    monkeypatch.delenv("SOURCE_BACKFILL_LIMIT", raising=False)
    monkeypatch.delenv("FORWARD_ALL_INGESTED", raising=False)
    s = Settings(_env_file=None)
    assert s.db_path.endswith("dealgoblin.sqlite3")
    assert s.session_path.endswith("telethon.session")
    assert s.source_chat_ids == []
    assert s.source_backfill_limit == 100
    assert s.forward_all_ingested is False


def test_settings_invalid_source_chat_ids(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "1")
    monkeypatch.setenv("TELEGRAM_API_HASH", "h")
    monkeypatch.setenv("BOT_TOKEN", "t")
    monkeypatch.setenv("OWNER_CHAT_ID", "1")
    monkeypatch.setenv("SOURCE_CHAT_IDS", "-1001,abc")
    with pytest.raises(Exception, match="source_chat_ids"):
        Settings(_env_file=None)

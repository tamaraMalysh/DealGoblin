from dealgoblin.config import Settings


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "123456")
    monkeypatch.setenv("TELEGRAM_API_HASH", "abcdef")
    monkeypatch.setenv("BOT_TOKEN", "token:xxx")
    monkeypatch.setenv("OWNER_CHAT_ID", "789")
    s = Settings()
    assert s.telegram_api_id == 123456
    assert s.telegram_api_hash == "abcdef"
    assert s.bot_token == "token:xxx"
    assert s.owner_chat_id == 789


def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "1")
    monkeypatch.setenv("TELEGRAM_API_HASH", "h")
    monkeypatch.setenv("BOT_TOKEN", "t")
    monkeypatch.setenv("OWNER_CHAT_ID", "1")
    s = Settings()
    assert s.db_path.endswith("dealgoblin.sqlite3")
    assert s.session_path.endswith("telethon.session")

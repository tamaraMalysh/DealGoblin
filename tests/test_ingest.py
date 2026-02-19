from dealgoblin.ingest.links import build_message_link
from dealgoblin.ingest.normalize import normalize_text


def test_link_with_username():
    assert build_message_link("fleamarket", 100, 42) == "https://t.me/fleamarket/42"


def test_link_without_username():
    # chat_id -1001234567890 → internal_id 1234567890
    assert build_message_link(None, -1001234567890, 42) == "https://t.me/c/1234567890/42"


def test_normalize_text():
    assert normalize_text("  Vintage  LAMP  500р  ") == "vintage lamp 500р"


def test_normalize_text_none():
    assert normalize_text(None) is None

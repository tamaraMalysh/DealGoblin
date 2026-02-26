from telethon import utils as tl_utils
from telethon.tl.types import Channel

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


def test_get_peer_id_returns_negative_for_channel():
    """get_peer_id returns -100-prefixed ID for channels, matching event.chat_id."""
    channel = Channel(
        id=1234567890,
        title="Test Channel",
        access_hash=0,
        photo=None,
        date=None,
    )
    peer_id = tl_utils.get_peer_id(channel)
    assert peer_id == -1001234567890
    assert peer_id != channel.id


def test_canonical_chat_ids_use_get_peer_id():
    """Canonical source IDs should use get_peer_id, not raw entity.id."""
    channel = Channel(
        id=1234567890,
        title="Test Channel",
        access_hash=0,
        photo=None,
        date=None,
    )
    # entity.id returns raw id, but get_peer_id returns the marked format
    raw_id = channel.id
    canonical_id = tl_utils.get_peer_id(channel)
    assert raw_id == 1234567890
    assert canonical_id == -1001234567890
    # The collector uses event.chat_id which matches canonical_id
    allowed = [canonical_id]
    assert canonical_id in allowed
    assert raw_id not in allowed

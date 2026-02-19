from dealgoblin.bot.helpers import format_search_results, format_source_list, parse_source_arg


def test_parse_source_username():
    assert parse_source_arg("@fleamarket") == "@fleamarket"


def test_parse_source_tme_link():
    assert parse_source_arg("https://t.me/fleamarket") == "@fleamarket"


def test_parse_source_invalid():
    assert parse_source_arg("not a source") is None


def test_format_source_list_empty():
    assert "No sources" in format_source_list([])


def test_format_source_list():
    sources = [{"id": 1, "chat_id": 100, "username": "flea", "title": "Flea Market"}]
    text = format_source_list(sources)
    assert "flea" in text
    assert "1" in text


def test_format_search_results_empty():
    assert "No results" in format_search_results([])


def test_format_search_results():
    results = [{"text_raw": "Vintage lamp 500р", "link": "https://t.me/flea/10"}]
    text = format_search_results(results)
    assert "lamp" in text.lower()
    assert "t.me" in text

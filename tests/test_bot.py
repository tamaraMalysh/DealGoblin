from dealgoblin.bot.helpers import format_search_results, format_source_list
from dealgoblin.bot.ui import help_support_text


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


def test_help_support_text_contains_contact_link():
    text = help_support_text()
    assert "https://t.me/siberianErmine" in text
    assert "пока в разработке" not in text

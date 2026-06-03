from dealgoblin.bot.helpers import format_search_results, format_source_list
from dealgoblin.bot.ui import help_support_text, main_menu_markup, search_results_markup
from dealgoblin.search.service import SearchResultItem, SearchResultPage


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
    results = [
        {
            "text_raw": "Vintage lamp 500р",
            "link": "https://t.me/flea/10",
            "source_name": "Flea Channel",
        }
    ]
    text = format_search_results(results)
    assert "lamp" in text.lower()
    assert "t.me" in text
    assert "flea channel" in text.lower()


def test_help_support_text_contains_contact_link():
    text = help_support_text()
    assert "https://t.me/siberianErmine" in text
    assert "пока в разработке" not in text


def test_main_menu_markup_contains_search_button():
    markup = main_menu_markup()
    button_texts = [button.text for row in markup.inline_keyboard for button in row]
    assert "Поиск" in button_texts


def test_search_results_markup_shows_pagination_and_new_search():
    page = SearchResultPage(
        search_id=3,
        raw_query="lamp",
        page=2,
        total=11,
        page_size=5,
        items=[
            SearchResultItem(
                rowid=1,
                chat_id=-1001,
                message_id=10,
                text_raw="Vintage lamp 500р",
                link="https://t.me/flea/10",
                posted_at=None,
                source_name="Flea Channel",
            )
        ],
    )

    markup = search_results_markup(page)
    button_texts = [button.text for row in markup.inline_keyboard for button in row]
    assert "◀️" in button_texts
    assert "▶️" in button_texts
    assert "Новый поиск" in button_texts

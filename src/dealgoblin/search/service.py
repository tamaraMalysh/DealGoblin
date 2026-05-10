from __future__ import annotations

from dataclasses import dataclass

import aiosqlite

from dealgoblin.match.fts_query import build_phrase_fts_query
from dealgoblin.storage.repo import MessageRepo, SearchSessionRepo

SEARCH_PAGE_SIZE = 5


class InvalidSearchQueryError(ValueError):
    pass


class SearchAccessError(PermissionError):
    pass


@dataclass(slots=True)
class SearchResultItem:
    rowid: int
    chat_id: int
    message_id: int
    text_raw: str | None
    link: str | None
    posted_at: str | None
    source_name: str


@dataclass(slots=True)
class SearchResultPage:
    search_id: int
    raw_query: str
    page: int
    total: int
    page_size: int
    items: list[SearchResultItem]

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page * self.page_size < self.total


class HistorySearchService:
    def __init__(self, db: aiosqlite.Connection, page_size: int = SEARCH_PAGE_SIZE):
        self._db = db
        self._page_size = page_size
        self._messages = MessageRepo(db)
        self._sessions = SearchSessionRepo(db)

    async def start_search(self, user: dict, raw_query: str) -> SearchResultPage:
        self._assert_user_can_search(user)
        fts_query = build_phrase_fts_query(raw_query)
        if not fts_query:
            raise InvalidSearchQueryError("Search query did not contain usable terms")

        snapshot_max_rowid = await self._messages.get_max_rowid()
        search_id = await self._sessions.create(
            user_id=int(user["id"]),
            raw_query=raw_query.strip(),
            fts_query=fts_query,
            snapshot_max_rowid=snapshot_max_rowid,
        )
        return await self.get_page(user=user, search_id=search_id, page=1)

    async def get_page(self, user: dict, search_id: int, page: int) -> SearchResultPage:
        self._assert_user_can_search(user)
        if page < 1:
            raise ValueError("page must be >= 1")

        session = await self._sessions.get_for_user(search_id=search_id, user_id=int(user["id"]))
        if session is None:
            raise SearchAccessError("Search session not found for this user")

        offset = (page - 1) * self._page_size
        rows = await self._messages.search_history(
            fts_query=str(session["fts_query"]),
            snapshot_max_rowid=int(session["snapshot_max_rowid"]),
            limit=self._page_size,
            offset=offset,
        )
        total = await self._messages.count_history_search(
            fts_query=str(session["fts_query"]),
            snapshot_max_rowid=int(session["snapshot_max_rowid"]),
        )
        items = [
            SearchResultItem(
                rowid=int(row["rowid"]),
                chat_id=int(row["chat_id"]),
                message_id=int(row["message_id"]),
                text_raw=row.get("text_raw"),
                link=row.get("link"),
                posted_at=row.get("posted_at"),
                source_name=str(row["source_name"]),
            )
            for row in rows
        ]
        return SearchResultPage(
            search_id=int(session["id"]),
            raw_query=str(session["raw_query"]),
            page=page,
            total=total,
            page_size=self._page_size,
            items=items,
        )

    def _assert_user_can_search(self, user: dict) -> None:
        if "id" not in user:
            raise SearchAccessError("Search requires a persisted bot user")

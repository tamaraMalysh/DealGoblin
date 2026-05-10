from __future__ import annotations

from dataclasses import dataclass

from dealgoblin.ingest.normalize import normalize_token


@dataclass(slots=True)
class ParsedSearchQuery:
    include_tokens: list[str]
    exclude_tokens: list[str]


def _normalize_token(token: str) -> str:
    return normalize_token(token)


def _as_prefix_token(token: str) -> str:
    if len(token) < 3:
        return token
    return f"{token}*"


def parse_search_input(raw: str) -> ParsedSearchQuery:
    include_tokens: list[str] = []
    exclude_tokens: list[str] = []
    for raw_token in raw.split():
        is_exclude = raw_token.startswith("-") and len(raw_token) > 1
        normalized = _normalize_token(raw_token[1:] if is_exclude else raw_token)
        if not normalized:
            continue
        if is_exclude:
            exclude_tokens.append(normalized)
        else:
            include_tokens.append(normalized)
    return ParsedSearchQuery(include_tokens=include_tokens, exclude_tokens=exclude_tokens)


def parse_watch_input(raw: str) -> ParsedSearchQuery:
    return parse_search_input(raw)


def build_phrase_fts_query(raw: str) -> str | None:
    parsed = parse_search_input(raw)
    if not parsed.include_tokens:
        return None
    phrase = " ".join(_as_prefix_token(token) for token in parsed.include_tokens)
    query = f'"{phrase}"'
    for token in parsed.exclude_tokens:
        query += f" NOT {_as_prefix_token(token)}"
    return query


def build_fts_query(include: list[str], exclude: list[str] | None = None) -> str | None:
    normalized_include = [_normalize_token(token) for token in include]
    include = [token for token in normalized_include if token]
    if not include:
        return None
    query = f'"{" ".join(_as_prefix_token(token) for token in include)}"'
    for term in exclude or []:
        term = _normalize_token(term)
        if term:
            query += f" NOT {_as_prefix_token(term)}"
    return query

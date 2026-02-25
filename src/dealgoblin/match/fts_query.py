from __future__ import annotations

import re
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9]+", re.IGNORECASE)


@dataclass(slots=True)
class ParsedWatchQuery:
    include_tokens: list[str]
    exclude_tokens: list[str]


def _normalize_token(token: str) -> str:
    match = _TOKEN_RE.search(token.lower())
    if not match:
        return ""
    cleaned = match.group(0).replace('"', "").replace(":", "").replace("*", "")
    return cleaned


def _as_prefix_token(token: str) -> str:
    if len(token) < 3:
        return token
    return f"{token}*"


def parse_watch_input(raw: str) -> ParsedWatchQuery:
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
    return ParsedWatchQuery(include_tokens=include_tokens, exclude_tokens=exclude_tokens)


def build_phrase_fts_query(raw: str) -> str | None:
    parsed = parse_watch_input(raw)
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

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

try:
    from pymorphy3 import MorphAnalyzer
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    MorphAnalyzer = None  # type: ignore[assignment,misc]

_TOKEN_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё]+", re.IGNORECASE)
_CYRILLIC_ONLY_RE = re.compile(r"^[А-Яа-яЁё]+$")

TEXT_NORMALIZATION_VERSION = "2"


@lru_cache(maxsize=1)
def _get_morph_analyzer() -> Any | None:
    if MorphAnalyzer is None:
        return None
    return MorphAnalyzer()


def _normalize_clean_token(cleaned: str) -> str:
    if not cleaned:
        return ""
    if not _CYRILLIC_ONLY_RE.fullmatch(cleaned):
        return cleaned

    analyzer = _get_morph_analyzer()
    if analyzer is None:
        return cleaned

    parsed = analyzer.parse(cleaned)
    if not parsed:
        return cleaned
    return parsed[0].normal_form


def normalize_token(token: str) -> str:
    match = _TOKEN_RE.search(token.lower())
    if not match:
        return ""
    return _normalize_clean_token(match.group(0))


def normalize_text(text: str | None) -> str | None:
    if text is None:
        return None

    normalized_tokens: list[str] = []
    for match in _TOKEN_RE.finditer(text.lower()):
        normalized = _normalize_clean_token(match.group(0))
        if normalized:
            normalized_tokens.append(normalized)
    return " ".join(normalized_tokens)

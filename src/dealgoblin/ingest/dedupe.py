from __future__ import annotations

import hashlib
import re

_SPACE_RE = re.compile(r"\s+")


def normalize_author_name(post_author: str | None) -> str | None:
    if post_author is None:
        return None
    normalized = _SPACE_RE.sub(" ", post_author.casefold().strip())
    return normalized or None


def build_dedupe_key(
    text_norm: str | None,
    author_id: int | None,
    author_name_norm: str | None,
) -> str | None:
    if not text_norm:
        return None

    if author_id is not None:
        author_key = f"id:{author_id}"
    elif author_name_norm:
        author_key = f"name:{author_name_norm}"
    else:
        return None

    digest = hashlib.sha256(f"{author_key}|text:{text_norm}".encode())
    return digest.hexdigest()

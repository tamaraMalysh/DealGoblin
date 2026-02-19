import re


def normalize_text(text: str | None) -> str | None:
    if text is None:
        return None
    return re.sub(r"\s+", " ", text.lower()).strip()

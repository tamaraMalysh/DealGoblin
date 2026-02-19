"""Price extraction and filtering — stub, to be implemented later."""

from __future__ import annotations


def extract_prices(text: str) -> list[float]:
    return []


def price_matches_filter(
    prices: list[float],
    price_min: float | None,
    price_max: float | None,
) -> bool:
    return True

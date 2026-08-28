"""Small shared helpers for the tool modules."""

from __future__ import annotations

from typing import Any


def first(result: dict[str, Any], *keys: str) -> Any:
    """Value of the first key present, else the only value in a single-key result.

    Query commands answer with an underscore-prefixed key (`{"_volume": 50}`), but
    the exact name varies between commands, so callers list the candidates.
    """
    for key in keys:
        if key in result:
            return result[key]
    values = list(result.values())
    if len(values) == 1:
        return values[0]
    return None

from __future__ import annotations


def shorten_middle(text: str, width: int = 80) -> str:
    """Shorten a long string keeping both ends."""
    if len(text) <= width:
        return text
    keep = (width - 3) // 2
    return text[:keep] + "..." + text[-keep:]


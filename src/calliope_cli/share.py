from __future__ import annotations

from pathlib import Path


def get_share_dir() -> Path:
    """Return the per-user data directory for Calliope."""
    share_dir = Path.home() / ".calliope"
    share_dir.mkdir(parents=True, exist_ok=True)
    return share_dir


from pathlib import Path

INIT = (Path(__file__).parent / "init.md").read_text(encoding="utf-8")

__all__ = ["INIT"]


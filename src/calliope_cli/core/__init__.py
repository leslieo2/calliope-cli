from __future__ import annotations

from dataclasses import dataclass


class LLMNotSet(RuntimeError):
    """Raised when an LLM is required but missing."""


class LLMNotSupported(RuntimeError):
    """Raised when the current LLM lacks required capabilities."""

    def __init__(self, required: list[str]):
        super().__init__(f"LLM missing required capabilities: {', '.join(required)}")


@dataclass(frozen=True, slots=True, kw_only=True)
class StatusSnapshot:
    context_usage: float


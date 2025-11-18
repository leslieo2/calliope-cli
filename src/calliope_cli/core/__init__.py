from __future__ import annotations

from dataclasses import dataclass


class LLMNotSet(RuntimeError):
    """Raised when an LLM is required but missing."""


class LLMNotSupported(RuntimeError):
    """Raised when the current LLM lacks required capabilities."""

    def __init__(self, required: list[str]):
        super().__init__(f"LLM missing required capabilities: {', '.join(required)}")


class MaxStepsReached(RuntimeError):
    """Raised when the agent hits the per-run step limit."""

    def __init__(self, max_steps: int):
        super().__init__(f"Maximum steps per run reached: {max_steps}")


@dataclass(frozen=True, slots=True, kw_only=True)
class StatusSnapshot:
    context_usage: float

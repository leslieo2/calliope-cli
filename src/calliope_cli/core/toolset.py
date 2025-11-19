from __future__ import annotations

import inspect
from contextvars import ContextVar
from typing import get_type_hints, override

from kosong.message import ToolCall
from kosong.tooling import HandleResult, ToolReturnType
from kosong.tooling.simple import SimpleToolset

current_tool_call = ContextVar[ToolCall | None]("current_tool_call", default=None)


def get_current_tool_call_or_none() -> ToolCall | None:
    """Return the current tool call if set."""
    return current_tool_call.get()


class CustomToolset(SimpleToolset):
    """Tracks the current tool call while handling execution."""

    def __iadd__(self, tool):  # type: ignore[override]
        try:
            type_hints = get_type_hints(tool.__call__)
            return_annotation = type_hints.get(
                "return", inspect.signature(tool.__call__).return_annotation
            )
        except Exception:  # pragma: no cover - defensive
            return_annotation = inspect.signature(tool.__call__).return_annotation

        if return_annotation is not ToolReturnType:
            raise TypeError(
                f"Expected tool `{tool.name}` to return `ToolReturnType`, "
                f"but got `{return_annotation}`"
            )
        self._tool_dict[tool.name] = tool
        return self

    @override
    def handle(self, tool_call: ToolCall) -> HandleResult:
        token = current_tool_call.set(tool_call)
        try:
            return super().handle(tool_call)
        finally:
            current_tool_call.reset(token)

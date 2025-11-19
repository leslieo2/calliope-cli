from typing import override

from kosong.tooling import CallableTool2, ToolOk, ToolReturnType
from pydantic import BaseModel, Field


class Params(BaseModel):
    title: str = Field(description="Book or chapter title.")
    focus: str | None = Field(default=None, description="Optional focus or audience.")


class Outline(CallableTool2[Params]):
    name: str = "Outline"
    description: str = "Generate an outline for the book/section."
    params: type[Params] = Params

    @override
    async def __call__(self, params: Params) -> ToolReturnType:
        heading = params.title if not params.focus else f"{params.title} — {params.focus}"
        output = f"# Outline for {heading}\n\n- [Stub] Add sections here."
        return ToolOk(output=output)

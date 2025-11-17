from typing import override

from kosong.tooling import CallableTool2, ToolOk, ToolReturnType
from pydantic import BaseModel, Field


class Params(BaseModel):
    description: str = Field(description="Describe the sub-task to delegate.")


class Task(CallableTool2[Params]):
    name: str = "Task"
    description: str = (
        "Delegate a sub-task to a helper agent (stub). "
        "Use for decomposing work like extraction/synthesis."
    )
    params: type[Params] = Params

    @override
    async def __call__(self, params: Params) -> ToolReturnType:
        return ToolOk(output=f"[stub] Sub-agent would handle: {params.description}")


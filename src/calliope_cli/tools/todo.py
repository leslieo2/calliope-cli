from typing import override

from kosong.tooling import CallableTool2, ToolOk, ToolReturnType
from pydantic import BaseModel, Field


class Params(BaseModel):
    item: str = Field(description="Progress note for internal tracking.")
    status: str = Field(default="in_progress", description="Status: todo/in_progress/done")


class Todo(CallableTool2[Params]):
    name: str = "Todo"
    description: str = (
        "Internal progress log for Calliope (not exposed to users). "
        "Use to track chapter/status during long runs."
    )
    params: type[Params] = Params

    @override
    async def __call__(self, params: Params) -> ToolReturnType:
        return ToolOk(output=f"[todo: {params.status}] {params.item}")


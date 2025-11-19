from typing import override

from kosong.tooling import CallableTool2, ToolOk, ToolReturnType
from pydantic import BaseModel, Field


class Params(BaseModel):
    draft: str = Field(description="Existing draft or notes to refine.")
    style: str | None = Field(default=None, description="Optional target style or audience.")


class Rewrite(CallableTool2[Params]):
    name: str = "Rewrite"
    description: str = "Rewrite or synthesize a draft into a polished excerpt with citations."
    params: type[Params] = Params

    @override
    async def __call__(self, params: Params) -> ToolReturnType:
        header = "### Rewritten Draft"
        if params.style:
            header += f" ({params.style})"
        output = f"{header}\n\n[Stub] Refined version of:\n\n{params.draft}"
        return ToolOk(output=output)

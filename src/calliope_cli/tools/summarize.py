from typing import override

from kosong.tooling import CallableTool2, ToolOk, ToolReturnType
from pydantic import BaseModel, Field


class Params(BaseModel):
    section: str = Field(description="Section or chapter name.")
    sources: list[str] | None = Field(
        default=None, description="Optional supporting snippets or citations."
    )


class Summarize(CallableTool2[Params]):
    name: str = "Summarize"
    description: str = "Summarize a section using provided context or retrieved chunks."
    params: type[Params] = Params

    @override
    async def __call__(self, params: Params) -> ToolReturnType:
        citations = ""
        if params.sources:
            citations = "\n\nSources:\n" + "\n".join(f"- {src}" for src in params.sources)
        output = f"## Summary: {params.section}\n\n[Stub] Add summary here.{citations}"
        return ToolOk(output=output)


from typing import override

from kosong.tooling import CallableTool2, ToolOk, ToolReturnType
from pydantic import BaseModel, Field


class Params(BaseModel):
    query: str = Field(description="Query to search within indexed chunks.")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of results to return.")


class RAGSearch(CallableTool2[Params]):
    name: str = "RAGSearch"
    description: str = (
        "Search previously indexed content and return supporting chunks. "
        "Current implementation is a placeholder; extend with vector store later."
    )
    params: type[Params] = Params

    @override
    async def __call__(self, params: Params) -> ToolReturnType:
        return ToolOk(output=f"[stub] Retrieved {params.top_k} chunks for query: {params.query}")


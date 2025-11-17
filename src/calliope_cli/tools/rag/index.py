from typing import override

from kosong.tooling import CallableTool2, ToolOk, ToolReturnType
from pydantic import BaseModel, Field


class Params(BaseModel):
    path: str = Field(description="Path to a file or directory to index for RAG use.")
    chunk_size: int = Field(default=1500, ge=200, description="Chunk size in characters")
    chunk_overlap: int = Field(default=200, ge=0, description="Chunk overlap in characters")


class RAGIndex(CallableTool2[Params]):
    name: str = "RAGIndex"
    description: str = (
        "Index local text sources for retrieval. "
        "Current implementation is a placeholder; extend with vector store later."
    )
    params: type[Params] = Params

    @override
    async def __call__(self, params: Params) -> ToolReturnType:
        return ToolOk(
            output=(
                f"[stub] Indexed {params.path} with chunk_size={params.chunk_size}, "
                f"chunk_overlap={params.chunk_overlap}."
            )
        )


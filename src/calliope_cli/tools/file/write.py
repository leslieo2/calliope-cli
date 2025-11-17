from pathlib import Path
from typing import Any, override

from kosong.tooling import CallableTool2, ToolError, ToolOk, ToolReturnType
from pydantic import BaseModel, Field

from calliope_cli.core.runtime import BuiltinSystemPromptArgs


class Params(BaseModel):
    path: str = Field(description="Absolute path to the file to write")
    content: str = Field(description="Content to write (replaces existing content)")


class WriteFile(CallableTool2[Params]):
    name: str = "WriteFile"
    description: str = (
        "Write text to a file (overwrite). Provide an absolute path. "
        "Use for saving drafts or notes."
    )
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._work_dir = builtin_args.CALLIOPE_WORK_DIR

    @override
    async def __call__(self, params: Params) -> ToolReturnType:
        try:
            p = Path(params.path)
            if not p.is_absolute():
                return ToolError(
                    message="Please provide an absolute path.",
                    brief="Path must be absolute",
                )

            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(params.content)

            return ToolOk(
                output=f"Wrote {len(params.content)} characters to {params.path}",
                message="Write succeeded",
            )
        except Exception as exc:  # pragma: no cover - defensive
            return ToolError(
                message=f"Failed to write {params.path}. Error: {exc}",
                brief="Failed to write file",
            )


from pathlib import Path
from typing import Any, override

from kosong.tooling import CallableTool2, ToolError, ToolOk, ToolReturnType
from pydantic import BaseModel, Field

from calliope_cli.core.runtime import BuiltinSystemPromptArgs

MAX_LINES = 1000
MAX_BYTES = 100 << 10  # 100KB


class Params(BaseModel):
    path: str = Field(description="Absolute path to the file to read")
    line_offset: int = Field(default=1, ge=1, description="Line number to start reading from")
    n_lines: int = Field(default=MAX_LINES, ge=1, description="Number of lines to read")


class ReadFile(CallableTool2[Params]):
    name: str = "ReadFile"
    description: str = (
        "Read a text file with safe limits. Provide an absolute path. "
        f"Max {MAX_LINES} lines and {MAX_BYTES // 1024}KB per call."
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
            if not p.exists():
                return ToolError(message=f"`{params.path}` does not exist.", brief="File not found")
            if not p.is_file():
                return ToolError(message=f"`{params.path}` is not a file.", brief="Invalid path")

            lines: list[str] = []
            n_bytes = 0
            with open(p, encoding="utf-8", errors="replace") as f:
                for line_no, line in enumerate(f, start=1):
                    if line_no < params.line_offset:
                        continue
                    lines.append(line)
                    n_bytes += len(line.encode("utf-8"))
                    if len(lines) >= params.n_lines or len(lines) >= MAX_LINES:
                        break
                    if n_bytes >= MAX_BYTES:
                        break

            if not lines:
                return ToolOk(output="", message="No lines read from file.")

            lines_with_no = [
                f"{line_num:6d}\t{line}"
                for line_num, line in zip(
                    range(params.line_offset, params.line_offset + len(lines)),
                    lines,
                    strict=True,
                )
            ]
            summary = (
                f"{len(lines)} lines read from {params.path} starting at line {params.line_offset}."
            )
            return ToolOk(output="".join(lines_with_no), message=summary)
        except Exception as exc:  # pragma: no cover - defensive
            return ToolError(
                message=f"Failed to read {params.path}. Error: {exc}",
                brief="Failed to read file",
            )

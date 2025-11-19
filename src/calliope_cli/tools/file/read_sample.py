from __future__ import annotations

import random
from collections import deque
from pathlib import Path
from typing import Any, Literal, override

from kosong.tooling import CallableTool2, ToolError, ToolOk, ToolReturnType
from pydantic import BaseModel, Field

from calliope_cli.core.runtime import BuiltinSystemPromptArgs
from calliope_cli.tools.utils import load_desc

MAX_LINES = 500


class Params(BaseModel):
    path: str = Field(description="Absolute path to the file to sample")
    position: Literal["head", "middle", "tail", "random"] = Field(
        default="head",
        description="Where to sample: head, middle, tail, or random window",
    )
    lines: int = Field(
        default=50,
        ge=1,
        le=MAX_LINES,
        description="Number of lines to read (capped for safety)",
    )


class ReadSample(CallableTool2[Params]):
    name: str = "ReadSample"
    description: str = load_desc(
        Path(__file__).parent / "read_sample.md",
        {"MAX_LINES": str(MAX_LINES)},
    )
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._work_dir = builtin_args.CALLIOPE_WORK_DIR

    @override
    async def __call__(self, params: Params) -> ToolReturnType:
        path = Path(params.path)
        if not path.is_absolute():
            return ToolError(message="Path must be absolute.", brief="Invalid path")
        if not path.exists():
            return ToolError(message=f"`{params.path}` does not exist.", brief="File not found")
        if not path.is_file():
            return ToolError(message=f"`{params.path}` is not a file.", brief="Invalid path")

        try:
            match params.position:
                case "head":
                    start_line, lines = self._read_head(path, params.lines)
                case "tail":
                    start_line, lines = self._read_tail(path, params.lines)
                case "middle":
                    start_line, lines = self._read_middle(path, params.lines)
                case "random":
                    start_line, lines = self._read_random(path, params.lines)
                case _:
                    return ToolError(message=f"Unsupported position: {params.position}")

            if not lines:
                return ToolOk(output="", message="No lines read from file.")

            numbered = [
                f"{line_no:6d}\t{line}"
                for line_no, line in zip(
                    range(start_line, start_line + len(lines)), lines, strict=True
                )
            ]
            summary = (
                f"Read {len(lines)} lines from {params.position} starting at line {start_line}."
            )
            return ToolOk(output="".join(numbered), message=summary)
        except Exception as exc:  # pragma: no cover - defensive
            return ToolError(
                message=f"Failed to read sample from {params.path}. Error: {exc}",
                brief="Failed to read sample",
            )

    def _read_head(self, path: Path, n: int) -> tuple[int, list[str]]:
        lines: list[str] = []
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                lines.append(line)
                if len(lines) >= n:
                    break
        return 1, lines

    def _read_tail(self, path: Path, n: int) -> tuple[int, list[str]]:
        tail = deque(maxlen=n)
        _total = 0
        with open(path, encoding="utf-8", errors="replace") as f:
            for _total, line in enumerate(f, start=1):
                tail.append(line)
        start_line = max(1, _total - len(tail) + 1)
        return start_line, list(tail)

    def _read_middle(self, path: Path, n: int) -> tuple[int, list[str]]:
        total = self._count_lines(path)
        if total == 0:
            return 1, []
        start_line = max(1, total // 2 - n // 2 + (total % 2))
        return start_line, self._read_window(path, start_line, n)

    def _read_random(self, path: Path, n: int) -> tuple[int, list[str]]:
        total = self._count_lines(path)
        if total == 0:
            return 1, []
        max_start = max(1, total - n + 1)
        start_line = random.randint(1, max_start)
        return start_line, self._read_window(path, start_line, n)

    def _count_lines(self, path: Path) -> int:
        _total = 0
        with open(path, encoding="utf-8", errors="replace") as f:
            for _total, _ in enumerate(f, start=1):
                pass
        return _total

    def _read_window(self, path: Path, start_line: int, n: int) -> list[str]:
        lines: list[str] = []
        with open(path, encoding="utf-8", errors="replace") as f:
            for line_no, line in enumerate(f, start=1):
                if line_no < start_line:
                    continue
                lines.append(line)
                if len(lines) >= n:
                    break
        return lines

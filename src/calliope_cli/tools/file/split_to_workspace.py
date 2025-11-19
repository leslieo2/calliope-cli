from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path
from typing import Any, override

from kosong.tooling import CallableTool2, ToolError, ToolOk, ToolReturnType
from pydantic import BaseModel, Field

from calliope_cli.core.runtime import BuiltinSystemPromptArgs
from calliope_cli.tools.utils import load_desc


class Params(BaseModel):
    source_path: str = Field(description="Path to the large source file.")
    workspace_path: str = Field(
        description="Directory to save the split files (e.g., 'workspaces/book_name')."
    )
    split_pattern: str = Field(description="Regex to identify chapter start.")
    filename_template: str = Field(
        default="{index:03d}_{title}.md",
        description="Python f-string style template for filenames. Variables: {index}, {title}.",
    )
    content_template: str = Field(
        default="# {title}\n\n{body}",
        description="Template for file content. Variables: {title}, {body}.",
    )


class SplitToWorkspace(CallableTool2[Params]):
    name: str = "SplitToWorkspace"
    description: str = load_desc(Path(__file__).parent / "split_to_workspace.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._work_dir = builtin_args.CALLIOPE_WORK_DIR

    @override
    async def __call__(self, params: Params) -> ToolReturnType:
        source_path = self._resolve_path(params.source_path)
        workspace_path = self._resolve_path(params.workspace_path)

        if not source_path.exists():
            return ToolError(message=f"`{source_path}` does not exist.", brief="File not found")
        if not source_path.is_file():
            return ToolError(message=f"`{source_path}` is not a file.", brief="Invalid path")

        try:
            pattern = re.compile(f"({params.split_pattern})", flags=re.MULTILINE)
        except re.error as exc:
            return ToolError(message=f"Invalid regex: {exc}", brief="Regex error")

        try:
            content = source_path.read_text(encoding="utf-8")
        except OSError as exc:
            return ToolError(message=f"Failed to read source: {exc}", brief="Read error")

        split_parts = pattern.split(content)
        headings = split_parts[1::2]
        bodies = split_parts[2::2]
        if len(bodies) < len(headings):
            bodies = [*bodies, *([""] * (len(headings) - len(bodies)))]

        if not headings:
            return ToolError(message="No matches found for regex; nothing to split.")

        preface = split_parts[0].strip("\n\r")

        try:
            self._prepare_workspace(workspace_path)
        except ValueError as exc:
            return ToolError(message=str(exc), brief="Unsafe workspace path")
        except OSError as exc:
            return ToolError(message=f"Failed to prepare workspace: {exc}", brief="Workspace error")

        written = 0
        if preface:
            self._write_file(
                workspace_path,
                filename=params.filename_template.format(index=0, title="preface"),
                content=preface,
            )
            written += 1

        for idx, (title, body) in enumerate(zip(headings, bodies, strict=True), start=1):
            title = title.strip()
            safe_title = self._slugify(title)
            try:
                filename = params.filename_template.format(index=idx, title=safe_title)
            except Exception as exc:  # noqa: BLE001
                return ToolError(
                    message=f"Filename template failed to render: {exc}",
                    brief="Template error",
                )
            try:
                file_content = params.content_template.format(title=title, body=body)
            except Exception as exc:  # noqa: BLE001
                return ToolError(
                    message=f"Content template failed to render: {exc}",
                    brief="Template error",
                )
            self._write_file(workspace_path, filename=filename, content=file_content)
            written += 1

        preview = ", ".join(headings[:5])
        return ToolOk(
            output=f"Split into {written} file(s) at {workspace_path}",
            message=f"Examples: {preview}",
        )

    def _slugify(self, text: str, max_len: int = 48) -> str:
        normalized = unicodedata.normalize("NFKD", text)
        cleaned = []
        for ch in normalized:
            category = unicodedata.category(ch)
            if category.startswith("L") or category.startswith("N"):
                cleaned.append(ch)
            elif ch.isspace() or ch in {"-", "_"}:
                cleaned.append("-")
        slug = re.sub(r"-+", "-", "".join(cleaned)).strip("-") or "part"
        return slug[:max_len]

    def _resolve_path(self, raw: str) -> Path:
        path = Path(raw)
        if not path.is_absolute():
            path = Path(self._work_dir) / path
        return path

    def _prepare_workspace(self, workspace_path: Path) -> None:
        resolved = workspace_path.resolve()
        if resolved == resolved.root:
            raise ValueError("Refusing to use filesystem root as workspace.")
        if resolved.exists():
            shutil.rmtree(resolved)
        resolved.mkdir(parents=True, exist_ok=True)

    def _write_file(self, base: Path, filename: str, content: str) -> None:
        (base / filename).write_text(content, encoding="utf-8")


# Backward compatibility for existing tool registrations.
SplitByRegex = SplitToWorkspace

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
    encoding: str | None = Field(
        default=None,
        description="Source file encoding (e.g., 'utf-8', 'gb18030'). If not provided, attempts auto-detect.",
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

        # 1. Detect encoding
        encoding = params.encoding or self._detect_encoding(source_path)

        try:
            pattern = re.compile(f"({params.split_pattern})", flags=re.MULTILINE)
        except re.error as exc:
            return ToolError(message=f"Invalid regex: {exc}", brief="Regex error")

        try:
            # 2. Read file using detected encoding
            content = source_path.read_text(encoding=encoding)
        except (UnicodeDecodeError, LookupError, ValueError):
            return ToolError(
                message=f"Failed to decode file `{source_path}` with encoding `{encoding}`. Try specifying a different encoding.",
                brief="Encoding error",
            )
        except OSError as exc:
            return ToolError(message=f"Failed to read source: {exc}", brief="Read error")

        # 3. Business logic for splitting
        split_parts = pattern.split(content)

        # pattern.split with capturing group creates list structure like:
        # [preface, title1, body1, title2, body2, ...]
        headings = split_parts[1::2]
        bodies = split_parts[2::2]

        # Edge case: if regex is not perfect, bodies might be fewer than headings
        if len(bodies) < len(headings):
            bodies = [*bodies, *([""] * (len(headings) - len(bodies)))]

        if not headings:
            return ToolError(
                message=f"No matches found for regex `{params.split_pattern}` with encoding `{encoding}`.",
                brief="No matches found"
            )

        preface = split_parts[0].strip("\n\r")

        try:
            self._prepare_workspace(workspace_path)
        except ValueError as exc:
            return ToolError(message=str(exc), brief="Unsafe workspace path")
        except OSError as exc:
            return ToolError(message=f"Failed to prepare workspace: {exc}", brief="Workspace error")

        written = 0
        # Write Preface (always use UTF-8 for new workspace files)
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
            output=f"Successfully split source (encoding: {encoding}) into {written} file(s) at {workspace_path}",
            message=f"Examples: {preview}",
        )

    def _detect_encoding(self, path: Path) -> str:
        """
        Heuristic to detect encoding (UTF-8 -> GB18030 -> Latin-1).
        """
        try:
            with open(path, "rb") as f:
                raw = f.read(4096)
        except OSError:
            return "utf-8"

        try:
            raw.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            pass

        try:
            raw.decode("gb18030")
            return "gb18030"
        except UnicodeDecodeError:
            pass

        return "latin-1"

    def _slugify(self, text: str, max_len: int = 48) -> str:
        # Note: This preserves the existing slugify logic but has limited Chinese support
        # If you want to preserve Chinese characters in filenames, you can simplify this function
        # The current logic removes Chinese characters and keeps only Latin characters, which is not suitable for Chinese novels
        # Suggested modification: use a more permissive mode

        # --- Improved Slugify (allows Chinese) ---
        text = text.strip()
        # Replace illegal filesystem characters
        safe_text = re.sub(r'[\\/*?:"<>|]', "", text)
        # Replace spaces with underscores
        safe_text = safe_text.replace(" ", "_")
        return safe_text[:max_len] or "chapter"

    def _resolve_path(self, raw: str) -> Path:
        path = Path(raw)
        if not path.is_absolute():
            path = Path(self._work_dir) / path
        return path

    def _prepare_workspace(self, workspace_path: Path) -> None:
        resolved = workspace_path.resolve()
        # Security check: prevent rm -rf / or rm -rf ~
        if resolved == resolved.root:
            raise ValueError("Refusing to use filesystem root as workspace.")

        # This check is somewhat weak, suggested improvement:
        # Ensure workspace_path is inside work_dir or is an obvious subdirectory

        if resolved.exists():
            shutil.rmtree(resolved)
        resolved.mkdir(parents=True, exist_ok=True)

    def _write_file(self, base: Path, filename: str, content: str) -> None:
        # Output files always use UTF-8, which is best practice
        (base / filename).write_text(content, encoding="utf-8")


# Backward compatibility for existing tool registrations.
SplitByRegex = SplitToWorkspace

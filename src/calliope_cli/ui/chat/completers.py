from __future__ import annotations

import os
import re
import time
from pathlib import Path

from prompt_toolkit.completion import Completion, Completer, FuzzyCompleter, WordCompleter
from prompt_toolkit.document import Document

from calliope_cli.ui.chat.metacmd import get_meta_commands


class MetaCommandCompleter(Completer):
    """Autocomplete slash commands using the meta-command registry."""

    def get_completions(self, document, complete_event):  # type: ignore[override]
        text = document.text_before_cursor

        if document.text_after_cursor.strip():
            return

        last_space = text.rfind(" ")
        token = text[last_space + 1 :]
        prefix = text[: last_space + 1] if last_space != -1 else ""

        if prefix.strip() or not token.startswith("/"):
            return

        typed = token[1:]
        typed_lower = typed.lower()

        for cmd in sorted(get_meta_commands(), key=lambda c: c.name):
            names = [cmd.name, *cmd.aliases]
            if typed == "" or any(name.lower().startswith(typed_lower) for name in names):
                yield Completion(
                    text=f"/{cmd.name}",
                    start_position=-len(token),
                    display=cmd.slash_name(),
                    display_meta=cmd.description,
                )


class FileMentionCompleter(Completer):
    """Provide fuzzy `@` path completion within the current working directory."""

    _FRAGMENT_PATTERN = re.compile(r"[^\s@]+")
    _TRIGGER_GUARDS = frozenset((".", "-", "_", "`", "'", '"', ":", "@", "#", "~"))
    _IGNORED_NAMES = frozenset(
        (
            ".DS_Store",
            ".git",
            ".hg",
            ".svn",
            "__pycache__",
            "node_modules",
            "dist",
            "build",
            "coverage",
            ".ruff_cache",
            ".pytest_cache",
            "venv",
            ".venv",
            "tmp",
        )
    )
    _IGNORED_PATTERN_PARTS: tuple[str, ...] = (
        r".*_cache$",
        r".*-cache$",
        r".*\.egg-info$",
        r".*\.dist-info$",
        r".*\.py[co]$",
        r".*\.class$",
        r".*\.sw[po]$",
        r".*~$",
        r".*\.(?:tmp|bak)$",
    )
    _IGNORED_PATTERNS = re.compile(
        "|".join(f"(?:{part})" for part in _IGNORED_PATTERN_PARTS),
        re.IGNORECASE,
    )

    def __init__(self, root: Path, *, refresh_interval: float = 2.0, limit: int = 1000) -> None:
        self._root = root
        self._refresh_interval = refresh_interval
        self._limit = limit
        self._cache_time = 0.0
        self._cached_paths: list[str] = []
        self._top_cache_time = 0.0
        self._top_cached_paths: list[str] = []
        self._fragment_hint: str | None = None

        self._word_completer = WordCompleter(
            self._get_paths,
            WORD=False,
            pattern=self._FRAGMENT_PATTERN,
        )
        self._fuzzy = FuzzyCompleter(
            self._word_completer,
            WORD=False,
            pattern=r"^[^\s@]*",
        )

    @classmethod
    def _is_ignored(cls, name: str) -> bool:
        if not name:
            return True
        if name in cls._IGNORED_NAMES:
            return True
        return bool(cls._IGNORED_PATTERNS.fullmatch(name))

    def _get_paths(self) -> list[str]:
        fragment = self._fragment_hint or ""
        if "/" not in fragment and len(fragment) < 3:
            return self._get_top_level_paths()
        return self._get_deep_paths()

    def _get_top_level_paths(self) -> list[str]:
        now = time.monotonic()
        if now - self._top_cache_time <= self._refresh_interval:
            return self._top_cached_paths

        entries: list[str] = []
        try:
            for entry in sorted(self._root.iterdir(), key=lambda p: p.name):
                name = entry.name
                if self._is_ignored(name):
                    continue
                entries.append(f"{name}/" if entry.is_dir() else name)
                if len(entries) >= self._limit:
                    break
        except OSError:
            return self._top_cached_paths

        self._top_cached_paths = entries
        self._top_cache_time = now
        return self._top_cached_paths

    def _get_deep_paths(self) -> list[str]:
        now = time.monotonic()
        if now - self._cache_time <= self._refresh_interval:
            return self._cached_paths

        paths: list[str] = []
        try:
            for current_root, dirs, files in os.walk(self._root):
                relative_root = Path(current_root).relative_to(self._root)

                dirs[:] = sorted(d for d in dirs if not self._is_ignored(d))

                if relative_root.parts and any(self._is_ignored(part) for part in relative_root.parts):
                    dirs[:] = []
                    continue

                if relative_root.parts:
                    paths.append(relative_root.as_posix() + "/")
                    if len(paths) >= self._limit:
                        break

                for file_name in sorted(files):
                    if self._is_ignored(file_name):
                        continue
                    relative = (relative_root / file_name).as_posix()
                    if not relative:
                        continue
                    paths.append(relative)
                    if len(paths) >= self._limit:
                        break

                if len(paths) >= self._limit:
                    break
        except OSError:
            return self._cached_paths

        self._cached_paths = paths
        self._cache_time = now
        return self._cached_paths

    @staticmethod
    def _extract_fragment(text: str) -> str | None:
        index = text.rfind("@")
        if index == -1:
            return None

        if index > 0:
            prev = text[index - 1]
            if prev.isalnum() or prev in FileMentionCompleter._TRIGGER_GUARDS:
                return None

        fragment = text[index + 1 :]
        if not fragment:
            return ""

        if any(ch.isspace() for ch in fragment):
            return None

        return fragment

    def _is_completed_file(self, fragment: str) -> bool:
        candidate = fragment.rstrip("/")
        if not candidate:
            return False
        try:
            return (self._root / candidate).is_file()
        except OSError:
            return False

    def get_completions(self, document, complete_event):  # type: ignore[override]
        fragment = self._extract_fragment(document.text_before_cursor)
        if fragment is None:
            return
        if self._is_completed_file(fragment):
            return

        mention_doc = Document(text=fragment, cursor_position=len(fragment))
        self._fragment_hint = fragment
        try:
            candidates = list(self._fuzzy.get_completions(mention_doc, complete_event))

            frag_lower = fragment.lower()

            def _rank(completion: Completion) -> tuple[int]:
                path = completion.text
                base = path.rstrip("/").split("/")[-1].lower()
                if base.startswith(frag_lower):
                    cat = 0
                elif frag_lower in base:
                    cat = 1
                else:
                    cat = 2
                return (cat,)

            candidates.sort(key=_rank)
            yield from candidates
        finally:
            self._fragment_hint = None

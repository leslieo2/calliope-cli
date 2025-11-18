from __future__ import annotations

import inspect
import shlex
import tempfile
from pathlib import Path
from typing import Any

from kosong.message import Message
from kosong.tooling import ToolError, ToolOk
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import merge_completers
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from calliope_cli.core.calliopecore import CalliopeCore
from calliope_cli.core.context import Context
from calliope_cli.utils.message import message_stringify
from calliope_cli.ui.chat.completers import FileMentionCompleter, MetaCommandCompleter
from calliope_cli.ui.chat.metacmd import get_meta_command, get_meta_commands, meta_command

console = Console()


class ChatApp:
    """Lightweight chat UI (no shell/ACP)."""

    def __init__(self, soul: CalliopeCore, welcome_info: list[tuple[str, str]] | None = None):
        self._soul = soul
        self._welcome_info = welcome_info or []
        self._session = PromptSession(
            completer=merge_completers(
                [MetaCommandCompleter(), FileMentionCompleter(Path.cwd())],
                deduplicate=True,
            ),
            complete_while_typing=True,
        )

    async def run(self, command: str | None = None) -> bool:
        """Run chat mode. If command is provided, run once; otherwise start loop."""
        if self._welcome_info:
            _render_welcome(self._welcome_info)
        if command:
            command = command.strip()
            if command.startswith("/"):
                return await self._handle_meta(command)
            result = await self._soul.run(command)
            _render_response(result.message.content)
            return True

        console.print("[italic]Type your message or slash command. Use /help for commands, /exit to quit.[/]")
        try:
            while True:
                try:
                    text = (await self._session.prompt_async("> ")).strip()
                except KeyboardInterrupt:
                    console.print("[yellow]^C[/] to exit; type /exit to quit.")
                    continue
                if not text:
                    continue
                if text.lower() in {"/exit", "/quit", "exit", "quit"}:
                    return True
                if text.startswith("/"):
                    await self._handle_meta(text)
                    continue
                result = await self._soul.run(text)
                _render_response(result.message.content)
        except EOFError:
            console.print()
            return True
        return True

    async def _handle_meta(self, command: str) -> bool:
        """Parse and dispatch slash commands via registry."""
        tokens = shlex.split(command)
        if not tokens:
            console.print("[red]Empty command[/]")
            return False

        cmd = tokens[0].lstrip("/").lower()
        args = tokens[1:]

        meta = get_meta_command(cmd)
        if meta is None:
            console.print(f"[red]Unknown command: /{cmd}[/]")
            _render_help()
            return False

        result = meta.func(self, args)
        if inspect.isawaitable(result):
            result = await result
        return True if result is None else bool(result)

    async def _call_tool(self, tool_name: str, *, core: CalliopeCore | None = None, **kwargs: Any) -> bool:
        target_core = core or self._soul
        tool = next((t for t in target_core.toolset.tools if t.name == tool_name), None)
        if tool is None:
            console.print(f"[red]Tool not available: {tool_name}[/]")
            return False
        try:
            params = tool.params(**{k: v for k, v in kwargs.items() if v is not None})
        except Exception as exc:  # pragma: no cover - defensive
            console.print(f"[red]Invalid arguments for {tool_name}: {exc}[/]")
            return False

        result = await tool(params)
        if isinstance(result, ToolError):
            console.print(f"[red]{result.brief or 'Tool error'}[/]\n{result.message}")
            if result.output:
                console.print(result.output)
            return False

        if isinstance(result, ToolOk):
            if result.message:
                console.print(result.message)
            if result.output:
                _render_response(result.output)
            return True

        console.print(f"[yellow]Tool returned unexpected result: {result}[/]")
        return False

    async def _call_tool_in_temp_context(self, tool_name: str, **kwargs: Any) -> bool:
        """Run tool using a temporary context so chat history stays clean."""

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_core = CalliopeCore(
                self._soul._agent,
                self._soul._runtime,
                context=Context(file_backend=Path(temp_dir) / "context.jsonl"),
            )
            return await self._call_tool(tool_name, core=temp_core, **kwargs)


def _render_welcome(rows: list[tuple[str, str]]) -> None:
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column("field", style="cyan", no_wrap=True)
    table.add_column("value")
    for name, value in rows:
        table.add_row(name, value)
    console.print(table)


def _render_response(content: Any) -> None:
    text: str
    match content:
        case str(raw):
            text = raw
        case _:
            text = message_stringify(Message(role="assistant", content=content))
    console.print(Markdown(text))


def _render_help() -> None:
    console.print(
        Markdown(
            """
**Slash commands**
1. `/help` — show this help
2. `/index <path> [--chunk N --overlap M]` — build RAG index (stub)
3. `/search "query" [--top K]` — search indexed content (stub)
4. `/outline "title" [--focus audience]` — generate outline (stub)
5. `/summarize "section"` — summarize a section (stub)
6. `/rewrite "draft" [--style tone]` — rewrite/merge draft (stub)
Use `/help-all` to list commands with aliases.
"""
        )
    )


@meta_command(aliases=["?"])
def help(app: ChatApp, args: list[str]):
    """Show available slash commands."""
    _render_help()
    return True


@meta_command
async def index(app: ChatApp, args: list[str]):
    """Build RAG index (stub)."""
    if not args:
        console.print("[red]Usage: /index <path> [--chunk 1500 --overlap 200][/]")
        return False
    return await app._call_tool_in_temp_context(
        "RAGIndex",
        path=args[0],
        chunk_size=_get_int_arg(args, "--chunk", 1500),
        chunk_overlap=_get_int_arg(args, "--overlap", 200),
    )


@meta_command
async def search(app: ChatApp, args: list[str]):
    """Search indexed content (stub)."""
    if not args:
        console.print("[red]Usage: /search \"query\" [--top 5][/]")
        return False
    return await app._call_tool_in_temp_context(
        "RAGSearch",
        query=" ".join(a for a in args if not a.startswith("--")),
        top_k=_get_int_arg(args, "--top", 5),
    )


@meta_command
async def outline(app: ChatApp, args: list[str]):
    """Generate outline (stub)."""
    if not args:
        console.print("[red]Usage: /outline \"title\" [--focus audience][/]")
        return False
    focus = _get_str_arg(args, "--focus")
    return await app._call_tool_in_temp_context("Outline", title=" ".join(args), focus=focus)


@meta_command
async def summarize(app: ChatApp, args: list[str]):
    """Summarize a section (stub)."""
    if not args:
        console.print("[red]Usage: /summarize \"section\"[/]")
        return False
    return await app._call_tool_in_temp_context("Summarize", section=" ".join(args), sources=None)


@meta_command
async def rewrite(app: ChatApp, args: list[str]):
    """Rewrite or merge a draft (stub)."""
    if not args:
        console.print("[red]Usage: /rewrite \"draft\" [--style tone][/]")
        return False
    style = _get_str_arg(args, "--style")
    draft = " ".join(a for a in args if not a.startswith("--"))
    return await app._call_tool_in_temp_context("Rewrite", draft=draft, style=style)


@meta_command(name="help-all")
def list_meta_commands(app: ChatApp, args: list[str]):
    """List meta commands with aliases."""
    table = Table(show_header=True, header_style="cyan", box=None, pad_edge=False)
    table.add_column("Command", no_wrap=True)
    table.add_column("Description")
    for cmd in get_meta_commands():
        names = ", ".join(f"/{n}" for n in cmd.all_names())
        table.add_row(names, cmd.description or "")
    console.print(table)
    return True


def _get_int_arg(args: list[str], flag: str, default: int) -> int:
    if flag not in args:
        return default
    try:
        idx = args.index(flag)
        return int(args[idx + 1])
    except Exception:
        return default


def _get_str_arg(args: list[str], flag: str) -> str | None:
    if flag not in args:
        return None
    try:
        idx = args.index(flag)
        return args[idx + 1]
    except Exception:
        return None

from __future__ import annotations

import shlex
from typing import Any

from kosong.message import Message
from kosong.tooling import ToolError, ToolOk
from prompt_toolkit import PromptSession
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from calliope_cli.core.calliopecore import CalliopeCore
from calliope_cli.utils.message import message_stringify

console = Console()


class ChatApp:
    """Lightweight chat UI (no shell/ACP)."""

    def __init__(self, soul: CalliopeCore, welcome_info: list[tuple[str, str]] | None = None):
        self._soul = soul
        self._welcome_info = welcome_info or []
        self._session = PromptSession()

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
        """Parse and dispatch simple slash commands."""
        tokens = shlex.split(command)
        if not tokens:
            console.print("[red]Empty command[/]")
            return False

        cmd = tokens[0].lower()
        args = tokens[1:]

        match cmd:
            case "/help":
                _render_help()
                return True
            case "/index":
                if not args:
                    console.print("[red]Usage: /index <path> [--chunk 1500 --overlap 200][/]")
                    return False
                return await self._call_tool(
                    "RAGIndex",
                    path=args[0],
                    chunk_size=_get_int_arg(args, "--chunk", 1500),
                    chunk_overlap=_get_int_arg(args, "--overlap", 200),
                )
            case "/search":
                if not args:
                    console.print("[red]Usage: /search \"query\" [--top 5][/]")
                    return False
                return await self._call_tool(
                    "RAGSearch",
                    query=" ".join(a for a in args if not a.startswith("--")),
                    top_k=_get_int_arg(args, "--top", 5),
                )
            case "/outline":
                if not args:
                    console.print("[red]Usage: /outline \"title\" [--focus audience][/]")
                    return False
                focus = _get_str_arg(args, "--focus")
                return await self._call_tool("Outline", title=" ".join(args), focus=focus)
            case "/summarize":
                if not args:
                    console.print("[red]Usage: /summarize \"section\"[/]")
                    return False
                return await self._call_tool("Summarize", section=" ".join(args), sources=None)
            case "/rewrite":
                if not args:
                    console.print("[red]Usage: /rewrite \"draft\" [--style tone][/]")
                    return False
                style = _get_str_arg(args, "--style")
                draft = " ".join(a for a in args if not a.startswith("--"))
                return await self._call_tool("Rewrite", draft=draft, style=style)
            case _:
                console.print(f"[red]Unknown command: {cmd}[/]")
                _render_help()
                return False

    async def _call_tool(self, tool_name: str, **kwargs: Any) -> bool:
        tool = next((t for t in self._soul.toolset.tools if t.name == tool_name), None)
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
- `/help` — show this help
- `/index <path> [--chunk N --overlap M]` — build RAG index (stub)
- `/search "query" [--top K]` — search indexed content (stub)
- `/outline "title" [--focus audience]` — generate outline (stub)
- `/summarize "section"` — summarize a section (stub)
- `/rewrite "draft" [--style tone]` — rewrite/merge draft (stub)
"""
        )
    )


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

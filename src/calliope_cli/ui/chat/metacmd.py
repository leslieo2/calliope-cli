from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from calliope_cli.ui.chat.app import ChatApp


type MetaCmdFunc = Callable[["ChatApp", list[str]], Awaitable[bool | None] | bool | None]


@dataclass(frozen=True, slots=True)
class MetaCommand:
    name: str
    description: str
    func: MetaCmdFunc
    aliases: list[str]

    def all_names(self) -> list[str]:
        return [self.name, *self.aliases]


_meta_commands: dict[str, MetaCommand] = {}
_meta_command_aliases: dict[str, MetaCommand] = {}


def get_meta_command(name: str) -> MetaCommand | None:
    return _meta_command_aliases.get(name)


def get_meta_commands() -> list[MetaCommand]:
    return list(_meta_commands.values())


@overload
def meta_command(func: MetaCmdFunc, /) -> MetaCmdFunc: ...


@overload
def meta_command(*, name: str | None = None, aliases: Sequence[str] | None = None) -> Callable[[MetaCmdFunc], MetaCmdFunc]: ...


def meta_command(func: MetaCmdFunc | None = None, *, name: str | None = None, aliases: Sequence[str] | None = None):
    """Decorator to register a meta command with optional name/aliases."""

    def _register(f: MetaCmdFunc):
        primary = name or f.__name__
        alias_list = list(aliases) if aliases else []

        cmd = MetaCommand(name=primary, description=(f.__doc__ or "").strip(), func=f, aliases=alias_list)
        _meta_commands[primary] = cmd
        _meta_command_aliases[primary] = cmd
        for alias in alias_list:
            _meta_command_aliases[alias] = cmd
        return f

    if func is not None:
        return _register(func)
    return _register

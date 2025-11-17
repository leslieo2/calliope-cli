from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, Literal

import typer

from calliope_cli.constant import VERSION

cli = typer.Typer(
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Calliope, your writing/拆书 CLI agent.",
)

UIMode = Literal["chat", "print"]
InputFormat = Literal["text", "stream-json"]
OutputFormat = Literal["text", "stream-json"]


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"calliope, version {VERSION}")
        raise typer.Exit()


@cli.command()
def calliope(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Show version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", help="Print verbose information. Default: no."),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option("--debug", help="Log debug information. Default: no."),
    ] = False,
    agent_file: Annotated[
        Path | None,
        typer.Option(
            "--agent-file",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Custom agent specification file. Default: builtin default agent.",
        ),
    ] = None,
    model_name: Annotated[
        str | None,
        typer.Option("--model", "-m", help="LLM model to use. Default: config file."),
    ] = None,
    work_dir: Annotated[
        Path | None,
        typer.Option(
            "--work-dir",
            "-w",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            writable=True,
            help="Working directory for the agent. Default: current directory.",
        ),
    ] = None,
    continue_: Annotated[
        bool,
        typer.Option(
            "--continue",
            "-C",
            help="Continue the previous session for the working directory. Default: no.",
        ),
    ] = False,
    command: Annotated[
        str | None,
        typer.Option(
            "--command",
            "-c",
            "--query",
            "-q",
            help="User query to the agent. Default: prompt interactively.",
        ),
    ] = None,
    print_mode: Annotated[
        bool,
        typer.Option("--print", help="Run in print mode (non-interactive)."),
    ] = False,
    input_format: Annotated[
        InputFormat | None,
        typer.Option(
            "--input-format",
            help="Input format to use. Must be used with `--print`. Default: text.",
        ),
    ] = None,
    output_format: Annotated[
        OutputFormat | None,
        typer.Option(
            "--output-format",
            help="Output format to use. Must be used with `--print`. Default: text.",
        ),
    ] = None,
    thinking: Annotated[
        bool | None,
        typer.Option("--thinking", help="Enable thinking mode if supported."),
    ] = None,
):
    del version

    from calliope_cli.app import CalliopeCLI, enable_logging
    from calliope_cli.metadata import WorkDirMeta, load_metadata, save_metadata
    from calliope_cli.session import Session
    from calliope_cli.utils.logging import logger

    def _noop_echo(*args: Any, **kwargs: Any):
        pass

    ui: UIMode = "print" if print_mode else "chat"

    echo: Callable[..., None] = typer.echo if verbose else _noop_echo
    enable_logging(debug)

    work_dir = (work_dir or Path.cwd()).absolute()
    if continue_:
        session = Session.continue_(work_dir)
        if session is None:
            raise typer.BadParameter(
                "No previous session found for the working directory",
                param_hint="--continue",
            )
        echo(f"✓ Continuing previous session: {session.id}")
    else:
        session = Session.create(work_dir)
        echo(f"✓ Created new session: {session.id}")
    echo(f"✓ Session history file: {session.history_file}")

    if command is not None:
        command = command.strip()
        if not command:
            raise typer.BadParameter("Command cannot be empty", param_hint="--command")

    if input_format is not None and ui != "print":
        raise typer.BadParameter("Input format is only supported for print UI", param_hint="--input-format")
    if output_format is not None and ui != "print":
        raise typer.BadParameter("Output format is only supported for print UI", param_hint="--output-format")

    async def _run() -> bool:
        if thinking is None:
            metadata = load_metadata()
            thinking_mode = metadata.thinking
        else:
            thinking_mode = thinking

        instance = await CalliopeCLI.create(
            session,
            model_name=model_name,
            thinking=thinking_mode,
            agent_file=agent_file,
        )
        match ui:
            case "chat":
                succeeded = await instance.run_chat_mode(command)
            case "print":
                if command is None:
                    raise typer.BadParameter("`--print` requires --command", param_hint="--command")
                succeeded = await instance.run_print_mode(
                    command,
                    input_format=input_format or "text",
                    output_format=output_format or "text",
                )

        if succeeded:
            metadata = load_metadata()
            work_dir_meta = next(
                (wd for wd in metadata.work_dirs if wd.path == str(session.work_dir)),
                None,
            )
            if work_dir_meta is None:
                logger.warning(
                    "Work dir metadata missing when marking last session, recreating: {work_dir}",
                    work_dir=session.work_dir,
                )
                work_dir_meta = WorkDirMeta(path=str(session.work_dir))
                metadata.work_dirs.append(work_dir_meta)

            work_dir_meta.last_session_id = session.id
            metadata.thinking = thinking_mode or False
            save_metadata(metadata)

        return succeeded

    succeeded = asyncio.run(_run())
    if not succeeded:
        sys.exit(1)


if __name__ == "__main__":
    if "calliope_cli.cli" not in sys.modules:
        sys.modules["calliope_cli.cli"] = sys.modules[__name__]

    sys.exit(cli())


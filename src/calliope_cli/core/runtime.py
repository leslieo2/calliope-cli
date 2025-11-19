from __future__ import annotations

import asyncio
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from calliope_cli.config import Config
from calliope_cli.llm import LLM
from calliope_cli.session import Session
from calliope_cli.utils.logging import logger


@dataclass(frozen=True, slots=True, kw_only=True)
class BuiltinSystemPromptArgs:
    """Builtin system prompt arguments available to templates."""

    CALLIOPE_NOW: str
    CALLIOPE_WORK_DIR: Path
    CALLIOPE_WORK_DIR_LS: str
    CALLIOPE_AGENTS_MD: str


def load_agents_md(work_dir: Path) -> str | None:
    paths = [work_dir / "AGENTS.md", work_dir / "agents.md"]
    for path in paths:
        if path.is_file():
            logger.info("Loaded agents.md: {path}", path=path)
            return path.read_text(encoding="utf-8").strip()
    logger.info("No AGENTS.md found in {work_dir}", work_dir=work_dir)
    return None


def _list_work_dir(work_dir: Path) -> str:
    if sys.platform == "win32":
        ls = subprocess.run(
            ["cmd", "/c", "dir", work_dir],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    else:
        ls = subprocess.run(
            ["ls", "-la", work_dir],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    return ls.stdout.strip()


@dataclass(frozen=True, slots=True, kw_only=True)
class Runtime:
    config: Config
    llm: LLM | None
    session: Session
    builtin_args: BuiltinSystemPromptArgs

    @staticmethod
    async def create(
        config: Config,
        llm: LLM | None,
        session: Session,
    ) -> Runtime:
        ls_output, agents_md = await asyncio.gather(
            asyncio.to_thread(_list_work_dir, session.work_dir),
            asyncio.to_thread(load_agents_md, session.work_dir),
        )

        return Runtime(
            config=config,
            llm=llm,
            session=session,
            builtin_args=BuiltinSystemPromptArgs(
                CALLIOPE_NOW=datetime.now().astimezone().isoformat(),
                CALLIOPE_WORK_DIR=session.work_dir,
                CALLIOPE_WORK_DIR_LS=ls_output,
                CALLIOPE_AGENTS_MD=agents_md or "",
            ),
        )

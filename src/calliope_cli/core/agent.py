from __future__ import annotations

import importlib
import inspect
import string
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from kosong.tooling import CallableTool, CallableTool2, Toolset

from calliope_cli.agentspec import ResolvedAgentSpec, load_agent_spec
from calliope_cli.config import Config
from calliope_cli.core.runtime import BuiltinSystemPromptArgs, Runtime
from calliope_cli.core.toolset import CustomToolset
from calliope_cli.session import Session
from calliope_cli.tools import SkipThisTool
from calliope_cli.utils.logging import logger


@dataclass(frozen=True, slots=True, kw_only=True)
class Agent:
    name: str
    system_prompt: str
    toolset: Toolset


async def load_agent(
    agent_file: Path,
    runtime: Runtime,
) -> Agent:
    logger.info("Loading agent: {agent_file}", agent_file=agent_file)
    agent_spec = load_agent_spec(agent_file)

    system_prompt = _load_system_prompt(
        agent_spec.system_prompt_path,
        agent_spec.system_prompt_args,
        runtime.builtin_args,
    )

    tool_deps = {
        ResolvedAgentSpec: agent_spec,
        Runtime: runtime,
        Config: runtime.config,
        BuiltinSystemPromptArgs: runtime.builtin_args,
        Session: runtime.session,
    }
    tools = agent_spec.tools
    if agent_spec.exclude_tools:
        logger.debug("Excluding tools: {tools}", tools=agent_spec.exclude_tools)
        tools = [tool for tool in tools if tool not in agent_spec.exclude_tools]
    toolset = CustomToolset()
    bad_tools = _load_tools(toolset, tools, tool_deps)
    if bad_tools:
        raise ValueError(f"Invalid tools: {bad_tools}")

    return Agent(
        name=agent_spec.name,
        system_prompt=system_prompt,
        toolset=toolset,
    )


def _load_system_prompt(
    path: Path, args: dict[str, str], builtin_args: BuiltinSystemPromptArgs
) -> str:
    logger.info("Loading system prompt: {path}", path=path)
    system_prompt = path.read_text(encoding="utf-8").strip()
    logger.debug(
        "Substituting system prompt with builtin args: {builtin_args}, spec args: {spec_args}",
        builtin_args=builtin_args,
        spec_args=args,
    )
    return string.Template(system_prompt).substitute(asdict(builtin_args), **args)


type ToolType = CallableTool | CallableTool2[Any]


def _load_tools(
    toolset: CustomToolset,
    tool_paths: list[str],
    dependencies: dict[type[Any], Any],
) -> list[str]:
    bad_tools: list[str] = []
    for tool_path in tool_paths:
        try:
            tool = _load_tool(tool_path, dependencies)
        except SkipThisTool:
            logger.info("Skipping tool: {tool_path}", tool_path=tool_path)
            continue
        if tool:
            toolset += tool
        else:
            bad_tools.append(tool_path)
    logger.info("Loaded tools: {tools}", tools=[tool.name for tool in toolset.tools])
    if bad_tools:
        logger.error("Bad tools: {bad_tools}", bad_tools=bad_tools)
    return bad_tools


def _load_tool(tool_path: str, dependencies: dict[type[Any], Any]) -> ToolType | None:
    logger.debug("Loading tool: {tool_path}", tool_path=tool_path)
    module_name, class_name = tool_path.rsplit(":", 1)
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        return None
    cls = getattr(module, class_name, None)
    if cls is None:
        return None
    args: list[type[Any]] = []
    for param in inspect.signature(cls).parameters.values():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            break
        if param.annotation not in dependencies:
            raise ValueError(f"Tool dependency not found: {param.annotation}")
        args.append(dependencies[param.annotation])
    return cls(*args)


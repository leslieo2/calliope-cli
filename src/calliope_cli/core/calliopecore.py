from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import kosong
from kosong import StepResult
from kosong.message import Message
from kosong.tooling import ToolResult

from calliope_cli.core import LLMNotSet, StatusSnapshot
from calliope_cli.core.agent import Agent
from calliope_cli.core.context import Context
from calliope_cli.core.message import tool_result_to_message
from calliope_cli.core.runtime import Runtime
from calliope_cli.utils.logging import logger


@dataclass(slots=True)
class CalliopeRunResult:
    """The result of a Calliope core run."""

    step_result: StepResult
    tool_results: list[ToolResult]

    @property
    def message(self) -> Message:
        return self.step_result.message

    @property
    def usage(self):
        return self.step_result.usage


class CalliopeCore:
    """Minimal loop to drive Calliope tools/LLM."""

    def __init__(self, agent: Agent, runtime: Runtime, *, context: Context):
        self._agent = agent
        self._runtime = runtime
        self._context = context

    @property
    def name(self) -> str:
        return self._agent.name

    @property
    def model_name(self) -> str:
        return self._runtime.llm.chat_provider.model_name if self._runtime.llm else ""

    @property
    def toolset(self):
        return self._agent.toolset

    @property
    def status(self) -> StatusSnapshot:
        return StatusSnapshot(context_usage=self._context_usage)

    @property
    def _context_usage(self) -> float:
        if self._runtime.llm is not None and self._runtime.llm.max_context_size:
            return self._context.token_count / self._runtime.llm.max_context_size
        return 0.0

    async def run(self, user_input: str):
        if self._runtime.llm is None:
            raise LLMNotSet()

        user_message = Message(role="user", content=user_input)
        await self._context.append_message(user_message)

        result = await kosong.step(
            chat_provider=self._runtime.llm.chat_provider,
            system_prompt=self._agent.system_prompt,
            toolset=self._agent.toolset,
            history=list(self._context.history),
        )

        tool_results = await result.tool_results()
        await self._handle_tool_results(tool_results)
        await self._context.append_message(result.message)
        if result.usage:
            await self._context.update_token_count(result.usage.input)

        return CalliopeRunResult(step_result=result, tool_results=tool_results)

    async def _handle_tool_results(self, tool_results: Iterable):
        for tool_result in tool_results:
            message = tool_result_to_message(tool_result)
            logger.debug(
                "Appending tool result message: {tool_call_id}",
                tool_call_id=tool_result.tool_call_id,
            )
            await self._context.append_message(message)

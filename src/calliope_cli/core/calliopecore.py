from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from functools import partial

import kosong
from kosong import StepResult
from kosong.chat_provider import (
    APIConnectionError,
    APIEmptyResponseError,
    APIStatusError,
    APITimeoutError,
)
from kosong.message import Message
from kosong.tooling import ToolResult
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from calliope_cli.core import LLMNotSet, MaxStepsReached, StatusSnapshot
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

        last_step: StepResult | None = None
        last_tool_results: list[ToolResult] = []
        step = 1

        while True:
            step_result, tool_results = await self._step()
            last_step = step_result
            last_tool_results = tool_results

            await self._context.append_message(step_result.message)
            if step_result.usage:
                await self._context.update_token_count(step_result.usage.input)

            # Maintain natural ordering: model message first, then tool results
            await self._handle_tool_results(tool_results)

            if not step_result.tool_calls:
                break

            step += 1
            if step > self._runtime.config.loop_control.max_steps_per_run:
                raise MaxStepsReached(self._runtime.config.loop_control.max_steps_per_run)

        assert last_step is not None  # for type checkers
        return CalliopeRunResult(step_result=last_step, tool_results=last_tool_results)

    async def _step(self) -> tuple[StepResult, list[ToolResult]]:
        """Run a single LLM step with retries and return the result plus tool outputs."""
        assert self._runtime.llm is not None

        @retry(
            retry=retry_if_exception(self._is_retryable_error),
            before_sleep=partial(self._retry_log, "step"),
            wait=wait_exponential_jitter(initial=0.3, max=5, jitter=0.5),
            stop=stop_after_attempt(self._runtime.config.loop_control.max_retries_per_step),
            reraise=True,
        )
        async def _run_step() -> StepResult:
            return await kosong.step(
                chat_provider=self._runtime.llm.chat_provider,
                system_prompt=self._agent.system_prompt,
                toolset=self._agent.toolset,
                history=list(self._context.history),
            )

        result = await _run_step()
        tool_results = await result.tool_results()
        return result, tool_results

    async def _handle_tool_results(self, tool_results: Iterable):
        for tool_result in tool_results:
            message = tool_result_to_message(tool_result)
            logger.debug(
                "Appending tool result message: {tool_call_id}",
                tool_call_id=tool_result.tool_call_id,
            )
            await self._context.append_message(message)

    @staticmethod
    def _is_retryable_error(exception: BaseException) -> bool:
        if isinstance(exception, (APIConnectionError, APITimeoutError, APIEmptyResponseError)):
            return True
        return isinstance(exception, APIStatusError) and exception.status_code in (
            429,
            500,
            502,
            503,
        )

    @staticmethod
    def _retry_log(name: str, retry_state: RetryCallState):
        logger.info(
            "Retrying {name} for the {n} time. Waiting {sleep} seconds.",
            name=name,
            n=retry_state.attempt_number,
            sleep=(
                retry_state.next_action.sleep if retry_state.next_action is not None else "unknown"
            ),
        )

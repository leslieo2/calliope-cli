from __future__ import annotations

import contextlib
import os
import warnings
from collections.abc import Generator
from pathlib import Path
from typing import Literal

import typer
from kosong.message import Message
from pydantic import SecretStr

from calliope_cli.agentspec import DEFAULT_AGENT_FILE
from calliope_cli.config import LLMModel, LLMProvider, load_config
from calliope_cli.core.agent import load_agent
from calliope_cli.core.calliopecore import CalliopeCore
from calliope_cli.core.context import Context
from calliope_cli.core.message import tool_result_to_message
from calliope_cli.core.runtime import Runtime
from calliope_cli.llm import augment_provider_with_env_vars, create_llm
from calliope_cli.session import Session
from calliope_cli.share import get_share_dir
from calliope_cli.ui.chat import ChatApp
from calliope_cli.ui.print import render_markdown
from calliope_cli.utils.logging import StreamToLogger, logger
from calliope_cli.utils.message import message_extract_text


def enable_logging(debug: bool = False) -> None:
    if debug:
        logger.enable("kosong")
    logger.add(
        get_share_dir() / "logs" / "calliope.log",
        level="TRACE" if debug else "INFO",
        rotation="06:00",
        retention="10 days",
    )


class CalliopeCLI:
    @staticmethod
    async def create(
        session: Session,
        *,
        config_file: Path | None = None,
        model_name: str | None = None,
        thinking: bool = False,
        agent_file: Path | None = None,
    ) -> CalliopeCLI:
        config = load_config(config_file)
        logger.info("Loaded config: {config}", config=config)

        model: LLMModel | None = None
        provider: LLMProvider | None = None

        if not model_name and config.default_model:
            model = config.models[config.default_model]
            provider = config.providers[model.provider]
        if model_name and model_name in config.models:
            model = config.models[model_name]
            provider = config.providers[model.provider]

        if not model:
            model = LLMModel(provider="", model="", max_context_size=100_000)
            provider = LLMProvider(type="kimi", base_url="", api_key=SecretStr(""))

        assert provider is not None
        assert model is not None
        env_overrides = augment_provider_with_env_vars(provider, model)

        if not provider.base_url or not model.model:
            llm = None
        else:
            logger.info("Using LLM provider: {provider}", provider=provider)
            logger.info("Using LLM model: {model}", model=model)
            llm = create_llm(provider, model, session_id=session.id)

        runtime = await Runtime.create(config, llm, session)

        if agent_file is None:
            agent_file = DEFAULT_AGENT_FILE
        agent = await load_agent(agent_file, runtime)

        context = Context(session.history_file)
        await context.restore()

        soul = CalliopeCore(agent, runtime, context=context)
        if thinking:
            logger.warning("Thinking mode requested but not implemented; ignoring.")
        return CalliopeCLI(soul, runtime, env_overrides)

    def __init__(
        self,
        _soul: CalliopeCore,
        _runtime: Runtime,
        _env_overrides: dict[str, str],
    ) -> None:
        self._soul = _soul
        self._runtime = _runtime
        self._env_overrides = _env_overrides

    @property
    def soul(self) -> CalliopeCore:
        return self._soul

    @property
    def session(self) -> Session:
        return self._runtime.session

    @contextlib.contextmanager
    def _app_env(self) -> Generator[None]:
        original_cwd = Path.cwd()
        os.chdir(self._runtime.session.work_dir)
        try:
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            with contextlib.redirect_stderr(StreamToLogger()):
                yield
        finally:
            os.chdir(original_cwd)

    async def run_chat_mode(self, command: str | None = None) -> bool:
        welcome_info = [
            ("Directory", str(self._runtime.session.work_dir)),
            ("Session", self._runtime.session.id),
        ]
        if base_url := self._env_overrides.get("KIMI_BASE_URL"):
            welcome_info.append(("API URL", f"{base_url} (from KIMI_BASE_URL)"))
        if self._env_overrides.get("KIMI_API_KEY"):
            welcome_info.append(("API Key", "****** (from KIMI_API_KEY)"))
        if not self._runtime.llm:
            welcome_info.append(("Model", "not set, configure in config.json"))
        elif "KIMI_MODEL_NAME" in self._env_overrides:
            welcome_info.append(
                ("Model", f"{self._soul.model_name} (from KIMI_MODEL_NAME)")
            )
        else:
            welcome_info.append(("Model", self._soul.model_name))

        with self._app_env():
            app = ChatApp(self._soul, welcome_info=welcome_info)
            return await app.run(command)

    async def run_print_mode(
        self,
        command: str,
        *,
        input_format: Literal["text", "stream-json"] | None = None,
        output_format: Literal["text", "stream-json"] | None = None,
    ):
        with self._app_env():
            prompt: str
            if input_format == "stream-json":
                message = Message.model_validate_json(command)
                if message.role != "user":
                    raise typer.BadParameter("Input stream must contain user messages only")
                prompt = message_extract_text(message)
            else:
                prompt = command

            result = await self._soul.run(prompt)
            if output_format == "stream-json":
                print(result.message.model_dump_json(exclude_none=True))
                for tool_result in result.tool_results:
                    msg = tool_result_to_message(tool_result)
                    print(msg.model_dump_json(exclude_none=True))
                return True

            content = result.message.content
            if isinstance(content, str):
                render_markdown(content)
            else:
                render_markdown(str(content))
            return True

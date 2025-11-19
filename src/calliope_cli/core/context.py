from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import aiofiles
import aiofiles.os
from kosong.message import Message

from calliope_cli.core.message import system
from calliope_cli.utils.logging import logger
from calliope_cli.utils.path import next_available_rotation


class Context:
    def __init__(self, file_backend: Path):
        self._file_backend = file_backend
        self._history: list[Message] = []
        self._token_count: int = 0
        self._next_checkpoint_id: int = 0

    async def restore(self) -> bool:
        logger.debug(
            "Restoring context from file: {file_backend}",
            file_backend=self._file_backend,
        )
        if self._history:
            raise RuntimeError("The context storage is already modified")
        if not self._file_backend.exists():
            logger.debug("No context file found, skipping restoration")
            return False
        if self._file_backend.stat().st_size == 0:
            logger.debug("Empty context file, skipping restoration")
            return False

        async with aiofiles.open(self._file_backend, encoding="utf-8") as f:
            async for line in f:
                if not line.strip():
                    continue
                line_json = json.loads(line)
                if line_json["role"] == "_usage":
                    self._token_count = line_json["token_count"]
                    continue
                if line_json["role"] == "_checkpoint":
                    self._next_checkpoint_id = line_json["id"] + 1
                    continue
                message = Message.model_validate(line_json)
                self._history.append(message)

        return True

    @property
    def history(self) -> Sequence[Message]:
        return self._history

    @property
    def token_count(self) -> int:
        return self._token_count

    @property
    def n_checkpoints(self) -> int:
        return self._next_checkpoint_id

    async def checkpoint(self, add_user_message: bool):
        checkpoint_id = self._next_checkpoint_id
        self._next_checkpoint_id += 1
        logger.debug("Checkpointing, ID: {id}", id=checkpoint_id)

        async with aiofiles.open(self._file_backend, "a", encoding="utf-8") as f:
            await f.write(json.dumps({"role": "_checkpoint", "id": checkpoint_id}) + "\n")
        if add_user_message:
            await self.append_message(
                Message(role="user", content=[system(f"CHECKPOINT {checkpoint_id}")])
            )

    async def revert_to(self, checkpoint_id: int):
        logger.debug("Reverting checkpoint, ID: {id}", id=checkpoint_id)
        if checkpoint_id >= self._next_checkpoint_id:
            raise ValueError(f"Checkpoint {checkpoint_id} does not exist")

        rotated_file_path = await next_available_rotation(self._file_backend)
        if rotated_file_path is None:
            raise RuntimeError("No available rotation path found")
        await aiofiles.os.replace(self._file_backend, rotated_file_path)

        self._history.clear()
        self._token_count = 0
        self._next_checkpoint_id = 0
        async with (
            aiofiles.open(rotated_file_path, encoding="utf-8") as old_file,
            aiofiles.open(self._file_backend, "w", encoding="utf-8") as new_file,
        ):
            async for line in old_file:
                if not line.strip():
                    continue

                line_json = json.loads(line)
                if line_json["role"] == "_checkpoint" and line_json["id"] == checkpoint_id:
                    break

                await new_file.write(line)
                if line_json["role"] == "_usage":
                    self._token_count = line_json["token_count"]
                elif line_json["role"] == "_checkpoint":
                    self._next_checkpoint_id = line_json["id"] + 1
                else:
                    message = Message.model_validate(line_json)
                    self._history.append(message)

    async def append_message(self, message: Message | Sequence[Message]):
        logger.debug("Appending message(s) to context: {message}", message=message)
        messages = message if isinstance(message, Sequence) else [message]
        self._history.extend(messages)

        async with aiofiles.open(self._file_backend, "a", encoding="utf-8") as f:
            for msg in messages:
                await f.write(msg.model_dump_json(exclude_none=True) + "\n")

    async def update_token_count(self, token_count: int):
        logger.debug("Updating token count in context: {token_count}", token_count=token_count)
        self._token_count = token_count

        async with aiofiles.open(self._file_backend, "a", encoding="utf-8") as f:
            await f.write(json.dumps({"role": "_usage", "token_count": token_count}) + "\n")

from __future__ import annotations

import json
from hashlib import md5
from pathlib import Path

from pydantic import BaseModel, Field

from calliope_cli.share import get_share_dir
from calliope_cli.utils.logging import logger


def get_metadata_file() -> Path:
    return get_share_dir() / "calliope.json"


class WorkDirMeta(BaseModel):
    """Metadata for a work directory."""

    path: str
    last_session_id: str | None = None

    @property
    def sessions_dir(self) -> Path:
        path = get_share_dir() / "sessions" / md5(self.path.encode(encoding="utf-8")).hexdigest()
        path.mkdir(parents=True, exist_ok=True)
        return path


class Metadata(BaseModel):
    """Calliope metadata structure."""

    work_dirs: list[WorkDirMeta] = Field(default_factory=list[WorkDirMeta])
    thinking: bool = False


def load_metadata() -> Metadata:
    metadata_file = get_metadata_file()
    logger.debug("Loading metadata from file: {file}", file=metadata_file)
    if not metadata_file.exists():
        logger.debug("No metadata file found, creating empty metadata")
        return Metadata()
    with open(metadata_file, encoding="utf-8") as f:
        data = json.load(f)
        return Metadata(**data)


def save_metadata(metadata: Metadata):
    metadata_file = get_metadata_file()
    logger.debug("Saving metadata to file: {file}", file=metadata_file)
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata.model_dump(), f, indent=2, ensure_ascii=False)

"""Application configuration.

Precedence (highest to lowest): CLI > environment variables > config file >
defaults. Implemented as an explicit manual merge instead of relying on a
settings library's internal precedence order, so the precedence is
guaranteed and easy to test.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel

ENV_PREFIX = "VIDCONTEXT_"


class AppConfig(BaseModel):
    runs_dir: Path = Path("runs")
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    transcription_language: str = "auto"
    transcriber: str = "mock"
    max_duration_seconds: float = 4 * 3600  # 4 hours
    max_file_size_bytes: int = 2 * 1024**3  # 2 GiB
    force: bool = False
    resume: bool = True
    verbose: bool = False
    use_mocks: bool = False


# Explicit env-var-name -> field map, so we never have to guess names.
_ENV_FIELD_MAP: dict[str, str] = {
    "RUNS_DIR": "runs_dir",
    "FFMPEG_PATH": "ffmpeg_path",
    "FFPROBE_PATH": "ffprobe_path",
    "TRANSCRIPTION_LANGUAGE": "transcription_language",
    "TRANSCRIBER": "transcriber",
    "MAX_DURATION_SECONDS": "max_duration_seconds",
    "MAX_FILE_SIZE_BYTES": "max_file_size_bytes",
    "VERBOSE": "verbose",
}

_BOOL_FIELDS = {"force", "resume", "verbose", "use_mocks"}
_INT_FIELDS = {"max_file_size_bytes"}
_FLOAT_FIELDS = {"max_duration_seconds"}


def _coerce(field: str, raw: str) -> Any:
    if field in _BOOL_FIELDS:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    if field in _INT_FIELDS:
        return int(raw)
    if field in _FLOAT_FIELDS:
        return float(raw)
    return raw


def _read_file_overrides(config_file: Path | None) -> dict[str, Any]:
    if config_file is None or not config_file.exists():
        return {}
    with config_file.open("rb") as fh:
        return tomllib.load(fh)


def _read_env_overrides(env: dict[str, str] | None = None) -> dict[str, Any]:
    source = os.environ if env is None else env
    overrides: dict[str, Any] = {}
    for env_suffix, field in _ENV_FIELD_MAP.items():
        key = f"{ENV_PREFIX}{env_suffix}"
        if key in source:
            overrides[field] = _coerce(field, source[key])
    return overrides


def load_config(
    config_file: Path | None = None,
    cli_overrides: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
) -> AppConfig:
    """Resolve the final configuration, applying the documented precedence."""
    merged: dict[str, Any] = {}
    merged.update(_read_file_overrides(config_file))
    merged.update(_read_env_overrides(env))
    merged.update({k: v for k, v in (cli_overrides or {}).items() if v is not None})
    return AppConfig(**merged)

"""Thin wrapper around ffmpeg/ffprobe.

Every command is built as an argument list (never a shell string) and run
with explicit error handling.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from vidcontext.exceptions import FFmpegError


def ensure_ffmpeg_available(ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe") -> None:
    if shutil.which(ffmpeg_path) is None:
        raise FFmpegError(f"ffmpeg not found on PATH (looked for: {ffmpeg_path!r})")
    if shutil.which(ffprobe_path) is None:
        raise FFmpegError(f"ffprobe not found on PATH (looked for: {ffprobe_path!r})")


def probe_duration_seconds(path: Path, ffprobe_path: str = "ffprobe") -> float:
    command = [
        ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        raise FFmpegError(f"ffprobe failed for {path}: {exc.stderr.strip()}") from exc
    except FileNotFoundError as exc:
        raise FFmpegError(f"ffprobe not found: {exc}") from exc

    try:
        payload = json.loads(result.stdout)
        return float(payload["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        raise FFmpegError(f"could not parse duration for {path}: {exc}") from exc


def extract_frame(
    source: Path, timestamp_seconds: float, destination: Path, ffmpeg_path: str = "ffmpeg"
) -> Path:
    """Extract a single frame at the given timestamp, as JPEG."""
    if timestamp_seconds < 0:
        raise FFmpegError(f"invalid negative timestamp: {timestamp_seconds}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg_path,
        "-y",
        "-ss",
        f"{timestamp_seconds:.3f}",
        "-i",
        str(source),
        "-frames:v",
        "1",
        str(destination),
    ]
    try:
        subprocess.run(command, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        raise FFmpegError(
            f"ffmpeg failed to extract frame at {timestamp_seconds}s from {source}: "
            f"{exc.stderr.strip()}"
        ) from exc
    if not destination.exists():
        raise FFmpegError(f"ffmpeg did not produce the expected frame at {destination}")
    return destination


def extract_audio_to_wav(source: Path, destination: Path, ffmpeg_path: str = "ffmpeg") -> Path:
    """Extract audio as WAV PCM mono 16kHz, the format recommended for ASR."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg_path,
        "-y",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(destination),
    ]
    try:
        subprocess.run(command, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        raise FFmpegError(
            f"ffmpeg failed to extract audio from {source}: {exc.stderr.strip()}"
        ) from exc
    return destination

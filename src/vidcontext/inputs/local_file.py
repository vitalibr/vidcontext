"""Classification of local files by extension."""

from __future__ import annotations

from pathlib import Path

from vidcontext.models import InputType

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}


def classify_local_file(path: Path) -> InputType | None:
    suffix = path.suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        return InputType.LOCAL_VIDEO
    if suffix in AUDIO_EXTENSIONS:
        return InputType.LOCAL_AUDIO
    return None

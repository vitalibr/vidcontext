"""Transcription contract. Callers don't know the concrete backend
(whisper.cpp, faster-whisper, YouTube subtitles, etc)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from vidcontext.models import Transcript


class Transcriber(Protocol):
    def transcribe(self, audio_path: Path, language_hint: str | None = None) -> Transcript: ...

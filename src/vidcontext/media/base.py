"""Contract for media access (metadata, subtitles, download)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from vidcontext.models import MediaMetadata, ResolvedInput


class TranscriptTrack(Protocol):
    """Describes an available subtitle track without loading its content."""

    language: str
    is_generated: bool


@dataclass
class SubtitleTrack:
    """Concrete implementation of TranscriptTrack."""

    language: str
    is_generated: bool


class MediaProvider(Protocol):
    def get_metadata(self, resolved: ResolvedInput) -> MediaMetadata: ...

    def list_transcripts(self, resolved: ResolvedInput) -> list[TranscriptTrack]: ...

    def download_subtitle(
        self, resolved: ResolvedInput, track: TranscriptTrack, destination: Path
    ) -> Path: ...

    def download_audio(self, resolved: ResolvedInput, destination: Path) -> Path: ...

    def download_video(self, resolved: ResolvedInput, destination: Path) -> Path: ...

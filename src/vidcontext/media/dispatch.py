"""Picks the concrete MediaProvider (YouTube or local file) from the
resolved InputType. Callers only see a single MediaProvider and don't need
to know the source is YouTube - YouTube is just one provider among others."""

from __future__ import annotations

from pathlib import Path

from vidcontext.media.base import MediaProvider, TranscriptTrack
from vidcontext.models import InputType, MediaMetadata, ResolvedInput


class CompositeMediaProvider:
    def __init__(self, youtube: MediaProvider, local: MediaProvider) -> None:
        self._youtube = youtube
        self._local = local

    def _provider_for(self, resolved: ResolvedInput) -> MediaProvider:
        return self._youtube if resolved.input_type is InputType.YOUTUBE else self._local

    def get_metadata(self, resolved: ResolvedInput) -> MediaMetadata:
        return self._provider_for(resolved).get_metadata(resolved)

    def list_transcripts(self, resolved: ResolvedInput) -> list[TranscriptTrack]:
        return self._provider_for(resolved).list_transcripts(resolved)

    def download_subtitle(
        self, resolved: ResolvedInput, track: TranscriptTrack, destination: Path
    ) -> Path:
        return self._provider_for(resolved).download_subtitle(resolved, track, destination)

    def download_audio(self, resolved: ResolvedInput, destination: Path) -> Path:
        return self._provider_for(resolved).download_audio(resolved, destination)

    def download_video(self, resolved: ResolvedInput, destination: Path) -> Path:
        return self._provider_for(resolved).download_video(resolved, destination)

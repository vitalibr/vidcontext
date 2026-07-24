"""Real MediaProvider for local files (video or audio).

Unlike MockMediaProvider (used only with --use-mocks), duration always
comes from ffprobe here: if ffprobe fails, the error propagates
(FFmpegError) instead of falling back to a made-up value.
"""

from __future__ import annotations

from pathlib import Path

from vidcontext.exceptions import MediaUnavailableError
from vidcontext.media.base import TranscriptTrack
from vidcontext.media.ffmpeg import extract_audio_to_wav, probe_duration_seconds
from vidcontext.models import InputType, MediaMetadata, ResolvedInput


class LocalFileMediaProvider:
    def get_metadata(self, resolved: ResolvedInput) -> MediaMetadata:
        from vidcontext.workspace import compute_source_id  # avoid a circular import up top

        assert resolved.local_path is not None
        duration = probe_duration_seconds(resolved.local_path)
        return MediaMetadata(
            source_id=compute_source_id(resolved),
            input_type=resolved.input_type,
            source_uri=resolved.source_uri,
            title=resolved.local_path.stem,
            duration_seconds=duration,
            has_video=resolved.input_type is InputType.LOCAL_VIDEO,
            has_audio=True,
        )

    def list_transcripts(self, resolved: ResolvedInput) -> list[TranscriptTrack]:
        return []  # local files have no YouTube-style subtitle tracks

    def download_subtitle(
        self, resolved: ResolvedInput, track: TranscriptTrack, destination: Path
    ) -> Path:
        raise MediaUnavailableError("local files have no YouTube subtitles")

    def download_audio(self, resolved: ResolvedInput, destination: Path) -> Path:
        assert resolved.local_path is not None
        if resolved.input_type is InputType.LOCAL_VIDEO:
            return extract_audio_to_wav(resolved.local_path, destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if resolved.local_path.resolve() != destination.resolve():
            destination.write_bytes(resolved.local_path.read_bytes())
        return destination

    def download_video(self, resolved: ResolvedInput, destination: Path) -> Path:
        assert resolved.local_path is not None
        if resolved.input_type is not InputType.LOCAL_VIDEO:
            raise MediaUnavailableError("source is audio-only, there is no video for frames")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if resolved.local_path.resolve() != destination.resolve():
            destination.write_bytes(resolved.local_path.read_bytes())
        return destination

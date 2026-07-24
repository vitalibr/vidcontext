"""Mock implementations of MediaProvider and Transcriber.

Useful for development and 100% offline testing (--use-mocks): they
produce fake but structurally valid data, without touching the network or
requiring real ffmpeg/yt-dlp.
"""

from __future__ import annotations

import wave
from pathlib import Path

from vidcontext.exceptions import FFmpegError, MediaUnavailableError
from vidcontext.media.base import TranscriptTrack
from vidcontext.media.ffmpeg import extract_audio_to_wav, probe_duration_seconds
from vidcontext.models import (
    InputType,
    MediaMetadata,
    ResolvedInput,
    Transcript,
    TranscriptSegment,
    TranscriptSource,
)

_MOCK_YOUTUBE_DURATION_SECONDS = 180.0
_MOCK_FALLBACK_DURATION_SECONDS = 60.0
_MOCK_YOUTUBE_AUDIO_SECONDS = 2.0


class MockMediaProvider:
    """A MediaProvider that never touches the network. For local files, it
    uses ffprobe when available to get a real duration; for YouTube, it
    fabricates plausible metadata."""

    def get_metadata(self, resolved: ResolvedInput) -> MediaMetadata:
        from vidcontext.workspace import compute_source_id  # avoid a circular import up top

        source_id = compute_source_id(resolved)

        if resolved.input_type is InputType.YOUTUBE:
            return MediaMetadata(
                source_id=source_id,
                input_type=resolved.input_type,
                source_uri=resolved.source_uri,
                title="Sample video (mock)",
                author="Sample author (mock)",
                description="Metadata fabricated by MockMediaProvider.",
                duration_seconds=_MOCK_YOUTUBE_DURATION_SECONDS,
                language_hint="en",
                chapters=[],
                has_video=True,
                has_audio=True,
            )

        assert resolved.local_path is not None
        try:
            duration = probe_duration_seconds(resolved.local_path)
        except FFmpegError:
            duration = _MOCK_FALLBACK_DURATION_SECONDS

        return MediaMetadata(
            source_id=source_id,
            input_type=resolved.input_type,
            source_uri=resolved.source_uri,
            title=resolved.local_path.stem,
            author=None,
            description=None,
            duration_seconds=duration,
            language_hint=None,
            chapters=[],
            has_video=resolved.input_type is InputType.LOCAL_VIDEO,
            has_audio=True,
        )

    def list_transcripts(self, resolved: ResolvedInput) -> list[TranscriptTrack]:
        return []

    def download_subtitle(
        self, resolved: ResolvedInput, track: TranscriptTrack, destination: Path
    ) -> Path:
        raise MediaUnavailableError(
            "MockMediaProvider exposes no subtitles (list_transcripts is empty)"
        )

    def download_audio(self, resolved: ResolvedInput, destination: Path) -> Path:
        if resolved.input_type is InputType.LOCAL_AUDIO:
            assert resolved.local_path is not None
            destination.parent.mkdir(parents=True, exist_ok=True)
            if resolved.local_path.resolve() != destination.resolve():
                destination.write_bytes(resolved.local_path.read_bytes())
            return destination

        if resolved.input_type is InputType.LOCAL_VIDEO:
            assert resolved.local_path is not None
            return extract_audio_to_wav(resolved.local_path, destination)

        return _write_silence_wav(destination, seconds=_MOCK_YOUTUBE_AUDIO_SECONDS)

    def download_video(self, resolved: ResolvedInput, destination: Path) -> Path:
        if resolved.input_type is InputType.LOCAL_VIDEO:
            assert resolved.local_path is not None
            destination.parent.mkdir(parents=True, exist_ok=True)
            if resolved.local_path.resolve() != destination.resolve():
                destination.write_bytes(resolved.local_path.read_bytes())
            return destination
        raise MediaUnavailableError("YouTube video download is not implemented in mock mode.")


def _write_silence_wav(destination: Path, seconds: float, sample_rate: int = 16000) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame_count = int(seconds * sample_rate)
    with wave.open(str(destination), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frame_count)
    return destination


class MockTranscriber:
    """Generates a synthetic transcript proportional to the audio's real
    duration, without running any ASR model."""

    def __init__(self, segment_duration_seconds: float = 8.0) -> None:
        self.segment_duration_seconds = segment_duration_seconds

    def transcribe(self, audio_path: Path, language_hint: str | None = None) -> Transcript:
        try:
            duration = probe_duration_seconds(audio_path)
        except FFmpegError:
            duration = _MOCK_FALLBACK_DURATION_SECONDS

        segments: list[TranscriptSegment] = []
        start = 0.0
        index = 0
        while start < duration:
            end = min(start + self.segment_duration_seconds, duration)
            segments.append(
                TranscriptSegment(
                    id=f"seg-{index:04d}",
                    start=start,
                    end=end,
                    text=f"[sample chunk {index + 1}, mock, {start:.1f}s-{end:.1f}s]",
                )
            )
            start = end
            index += 1

        if not segments:
            segments.append(
                TranscriptSegment(id="seg-0000", start=0.0, end=0.0, text="[empty audio, mock]")
            )

        return Transcript(
            language=language_hint or "en",
            source=TranscriptSource.MOCK,
            segments=segments,
            full_text=" ".join(seg.text for seg in segments),
        )

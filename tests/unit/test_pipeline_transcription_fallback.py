"""Tests the transcript fallback chain: subtitle -> youtube-transcript-api
-> local ASR. Uses simple provider doubles, no network, to isolate just
the decision logic."""

from pathlib import Path

import pytest

from vidcontext.config import AppConfig
from vidcontext.exceptions import SubtitleUnavailableError
from vidcontext.inputs.resolver import DefaultInputResolver
from vidcontext.media.base import SubtitleTrack, TranscriptTrack
from vidcontext.models import (
    InputType,
    MediaChapter,
    MediaMetadata,
    ResolvedInput,
    Transcript,
    TranscriptSegment,
    TranscriptSource,
)
from vidcontext.pipeline import Providers, VidContext
from vidcontext.visual.frame_extractor import FfmpegFrameExtractor

VIDEO_ID = "abc12345678"
VIDEO_URL = f"https://youtu.be/{VIDEO_ID}"

_METADATA = MediaMetadata(
    source_id=f"youtube-{VIDEO_ID}",
    input_type=InputType.YOUTUBE,
    source_uri=VIDEO_URL,
    duration_seconds=10.0,
    chapters=[MediaChapter(title="c", start=0.0, end=10.0)],
    has_video=True,
    has_audio=True,
)

_VTT_CONTENT = "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nsubtitle line\n"


class StubMediaProvider:
    """Test media provider: fixed metadata, no real video download."""

    def __init__(self, tracks: list[TranscriptTrack], subtitle_error: Exception | None = None):
        self.tracks = tracks
        self.subtitle_error = subtitle_error
        self.download_audio_calls = 0

    def get_metadata(self, resolved: ResolvedInput) -> MediaMetadata:
        return _METADATA

    def list_transcripts(self, resolved: ResolvedInput) -> list[TranscriptTrack]:
        return self.tracks

    def download_subtitle(self, resolved: ResolvedInput, track, destination: Path) -> Path:
        if self.subtitle_error:
            raise self.subtitle_error
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(_VTT_CONTENT)
        return destination

    def download_audio(self, resolved: ResolvedInput, destination: Path) -> Path:
        self.download_audio_calls += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"")
        return destination

    def download_video(self, resolved: ResolvedInput, destination: Path):
        raise NotImplementedError


class StubTranscriber:
    def __init__(self) -> None:
        self.calls = 0

    def transcribe(self, audio_path: Path, language_hint: str | None = None) -> Transcript:
        self.calls += 1
        return Transcript(
            language="en",
            source=TranscriptSource.LOCAL_ASR,
            segments=[TranscriptSegment(id="seg-0000", start=0.0, end=1.0, text="via asr")],
            full_text="via asr",
        )


@pytest.fixture(autouse=True)
def _no_transcript_api_network(monkeypatch: pytest.MonkeyPatch) -> None:
    # Make sure the youtube-transcript-api fallback never touches the
    # real network in these tests (don't depend on live YouTube).
    target = "vidcontext.pipeline.fetch_via_transcript_api"
    monkeypatch.setattr(target, lambda video_id, lang: None)


def _tool(
    tmp_path: Path, media_provider: StubMediaProvider, transcriber: StubTranscriber
) -> VidContext:
    config = AppConfig(runs_dir=tmp_path)
    providers = Providers(
        resolver=DefaultInputResolver(),
        media_provider=media_provider,
        transcriber=transcriber,
        frame_extractor=FfmpegFrameExtractor(),
    )
    return VidContext(config=config, providers=providers)


def test_manual_subtitle_is_preferred_over_asr(tmp_path: Path):
    media = StubMediaProvider(tracks=[SubtitleTrack(language="pt", is_generated=False)])
    transcriber = StubTranscriber()

    result = _tool(tmp_path, media, transcriber).run_transcript(VIDEO_URL)

    assert result.transcript.source is TranscriptSource.YOUTUBE_MANUAL
    assert transcriber.calls == 0
    assert media.download_audio_calls == 0


def test_falls_back_to_asr_when_no_tracks_available(tmp_path: Path):
    media = StubMediaProvider(tracks=[])
    transcriber = StubTranscriber()

    result = _tool(tmp_path, media, transcriber).run_transcript(VIDEO_URL)

    assert result.transcript.source is TranscriptSource.LOCAL_ASR
    assert transcriber.calls == 1
    assert media.download_audio_calls == 1


def test_falls_back_to_asr_when_subtitle_download_fails(tmp_path: Path):
    media = StubMediaProvider(
        tracks=[SubtitleTrack(language="pt", is_generated=False)],
        subtitle_error=SubtitleUnavailableError("failed"),
    )
    transcriber = StubTranscriber()

    result = _tool(tmp_path, media, transcriber).run_transcript(VIDEO_URL)

    assert result.transcript.source is TranscriptSource.LOCAL_ASR
    assert transcriber.calls == 1


def test_generated_track_used_when_no_manual_available(tmp_path: Path):
    media = StubMediaProvider(tracks=[SubtitleTrack(language="en", is_generated=True)])
    transcriber = StubTranscriber()

    result = _tool(tmp_path, media, transcriber).run_transcript(VIDEO_URL)

    assert result.transcript.source is TranscriptSource.YOUTUBE_GENERATED
    assert transcriber.calls == 0


def test_missing_media_unavailable_is_not_swallowed_by_pick_logic(tmp_path: Path):
    # regression: VidContextError raised during list_transcripts must not
    # propagate, it should just make the fallback move to the next link.
    class RaisingMediaProvider(StubMediaProvider):
        def list_transcripts(self, resolved: ResolvedInput) -> list[TranscriptTrack]:
            raise SubtitleUnavailableError("unavailable")

    media = RaisingMediaProvider(tracks=[])
    transcriber = StubTranscriber()

    result = _tool(tmp_path, media, transcriber).run_transcript(VIDEO_URL)

    assert result.transcript.source is TranscriptSource.LOCAL_ASR

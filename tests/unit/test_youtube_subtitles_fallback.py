"""Testa o fallback via youtube-transcript-api sem tocar a rede."""

from dataclasses import dataclass

import pytest

from vidcontext.models import TranscriptSource
from vidcontext.transcription import youtube_subtitles
from vidcontext.transcription.youtube_subtitles import fetch_via_transcript_api


@dataclass
class FakeSnippet:
    text: str
    start: float
    duration: float


class FakeApiSuccess:
    def fetch(self, video_id: str, languages: list[str]):
        return [
            FakeSnippet(text="ola", start=0.0, duration=1.5),
            FakeSnippet(text="mundo", start=1.5, duration=1.5),
        ]


class FakeApiFailure:
    def fetch(self, video_id: str, languages: list[str]):
        raise youtube_subtitles.YouTubeTranscriptApiException("indisponivel")


def test_fetch_via_transcript_api_builds_transcript(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(youtube_subtitles, "YouTubeTranscriptApi", FakeApiSuccess)

    transcript = fetch_via_transcript_api("abc12345678", "pt")

    assert transcript is not None
    assert transcript.source is TranscriptSource.YOUTUBE_GENERATED
    assert transcript.language == "pt"
    assert [s.text for s in transcript.segments] == ["ola", "mundo"]
    assert transcript.segments[0].end == 1.5


def test_fetch_via_transcript_api_returns_none_on_failure(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(youtube_subtitles, "YouTubeTranscriptApi", FakeApiFailure)

    assert fetch_via_transcript_api("abc12345678", "pt") is None

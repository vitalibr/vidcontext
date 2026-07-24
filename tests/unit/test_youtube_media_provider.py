"""Tests YouTubeMediaProvider without touching the network: yt-dlp is
always replaced by a fixed info dict (don't depend on live YouTube)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vidcontext.exceptions import SubtitleUnavailableError
from vidcontext.media.base import SubtitleTrack
from vidcontext.media.youtube import YouTubeMediaProvider
from vidcontext.models import InputType, ResolvedInput

FAKE_INFO = {
    "id": "abc12345678",
    "title": "Titulo de teste",
    "uploader": "Canal de Teste",
    "description": "Descricao de teste",
    "duration": 125.5,
    "language": "pt",
    "vcodec": "vp9",
    "acodec": "opus",
    "chapters": [
        {"title": "Intro", "start_time": 0.0, "end_time": 30.0},
        {"title": "Desenvolvimento", "start_time": 30.0, "end_time": 120.0},
    ],
    "subtitles": {
        "pt": [
            {"ext": "vtt", "url": "https://example.com/pt.vtt"},
            {"ext": "srv3", "url": "https://example.com/pt.srv3"},
        ],
    },
    "automatic_captions": {
        "en": [{"ext": "vtt", "url": "https://example.com/en-auto.vtt"}],
    },
}


@pytest.fixture
def resolved() -> ResolvedInput:
    return ResolvedInput(
        input_type=InputType.YOUTUBE,
        source_uri="https://youtu.be/abc12345678",
        youtube_video_id="abc12345678",
    )


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch, resolved: ResolvedInput) -> YouTubeMediaProvider:
    instance = YouTubeMediaProvider()
    monkeypatch.setattr(instance, "_extract_info", lambda r: FAKE_INFO)
    return instance


def test_get_metadata_maps_yt_dlp_fields(provider: YouTubeMediaProvider, resolved: ResolvedInput):
    metadata = provider.get_metadata(resolved)

    assert metadata.source_id == "youtube-abc12345678"
    assert metadata.title == "Titulo de teste"
    assert metadata.author == "Canal de Teste"
    assert metadata.duration_seconds == 125.5
    assert metadata.language_hint == "pt"
    assert metadata.has_video is True
    assert metadata.has_audio is True
    assert [c.title for c in metadata.chapters] == ["Intro", "Desenvolvimento"]


def test_list_transcripts_returns_manual_before_generated(
    provider: YouTubeMediaProvider, resolved: ResolvedInput
):
    tracks = provider.list_transcripts(resolved)

    assert len(tracks) == 2
    assert tracks[0].language == "pt"
    assert tracks[0].is_generated is False
    assert tracks[1].language == "en"
    assert tracks[1].is_generated is True


def test_download_subtitle_picks_vtt_entry_and_writes_bytes(
    provider: YouTubeMediaProvider,
    resolved: ResolvedInput,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    fake_response = MagicMock()
    fake_response.read.return_value = b"WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nola\n"
    fake_response.__enter__.return_value = fake_response
    fake_response.__exit__.return_value = False

    captured_urls = []

    def fake_urlopen(request, timeout=30):
        captured_urls.append(request.full_url)
        return fake_response

    monkeypatch.setattr("vidcontext.media.youtube.urllib.request.urlopen", fake_urlopen)

    destination = tmp_path / "subtitles.vtt"
    track = SubtitleTrack(language="pt", is_generated=False)
    result = provider.download_subtitle(resolved, track, destination)

    assert result == destination
    assert destination.read_bytes() == fake_response.read.return_value
    assert captured_urls == ["https://example.com/pt.vtt"]  # picked the vtt format, not srv3


def test_download_subtitle_raises_when_language_not_available(
    provider: YouTubeMediaProvider, resolved: ResolvedInput, tmp_path: Path
):
    track = SubtitleTrack(language="es", is_generated=False)
    with pytest.raises(SubtitleUnavailableError):
        provider.download_subtitle(resolved, track, tmp_path / "subtitles.vtt")

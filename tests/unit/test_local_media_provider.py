from pathlib import Path

import pytest

from vidcontext.exceptions import MediaUnavailableError
from vidcontext.media.local import LocalFileMediaProvider
from vidcontext.models import InputType, ResolvedInput

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def provider() -> LocalFileMediaProvider:
    return LocalFileMediaProvider()


def test_get_metadata_uses_real_ffprobe_duration(provider: LocalFileMediaProvider):
    audio = FIXTURES_DIR / "sample-audio.wav"
    resolved = ResolvedInput(
        input_type=InputType.LOCAL_AUDIO, source_uri=str(audio), local_path=audio
    )

    metadata = provider.get_metadata(resolved)

    assert metadata.has_video is False
    assert metadata.has_audio is True
    assert metadata.duration_seconds == pytest.approx(3.0, abs=0.2)
    assert metadata.title == "sample-audio"


def test_list_transcripts_is_always_empty(provider: LocalFileMediaProvider):
    audio = FIXTURES_DIR / "sample-audio.wav"
    resolved = ResolvedInput(
        input_type=InputType.LOCAL_AUDIO, source_uri=str(audio), local_path=audio
    )
    assert provider.list_transcripts(resolved) == []


def test_download_audio_returns_file_itself_for_local_audio(
    provider: LocalFileMediaProvider, tmp_path: Path
):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"fake wav bytes")
    resolved = ResolvedInput(
        input_type=InputType.LOCAL_AUDIO, source_uri=str(audio), local_path=audio
    )

    destination = tmp_path / "workspace" / "audio.wav"
    result = provider.download_audio(resolved, destination)

    assert result == destination
    assert destination.read_bytes() == b"fake wav bytes"


def test_download_video_raises_for_audio_only_source(
    provider: LocalFileMediaProvider, tmp_path: Path
):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"fake wav bytes")
    resolved = ResolvedInput(
        input_type=InputType.LOCAL_AUDIO, source_uri=str(audio), local_path=audio
    )

    with pytest.raises(MediaUnavailableError):
        provider.download_video(resolved, tmp_path / "video.mp4")

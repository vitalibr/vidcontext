from pathlib import Path

import pytest

from vidcontext.exceptions import (
    InvalidYouTubeUrlError,
    PlaylistNotSupportedError,
    SourceNotFoundError,
    UnsupportedInputError,
)
from vidcontext.inputs.resolver import DefaultInputResolver
from vidcontext.models import InputType


@pytest.fixture
def resolver() -> DefaultInputResolver:
    return DefaultInputResolver()


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ&feature=share",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://www.youtube.com/live/dQw4w9WgXcQ",
        "https://www.youtube.com/live/dQw4w9WgXcQ?feature=share",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
    ],
)
def test_youtube_urls_are_classified_with_video_id(resolver: DefaultInputResolver, url: str):
    resolved = resolver.resolve(url)
    assert resolved.input_type is InputType.YOUTUBE
    assert resolved.youtube_video_id == "dQw4w9WgXcQ"


def test_playlist_url_is_rejected(resolver: DefaultInputResolver):
    with pytest.raises(PlaylistNotSupportedError):
        resolver.resolve("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123")


def test_youtube_host_without_extractable_id_is_invalid(resolver: DefaultInputResolver):
    with pytest.raises(InvalidYouTubeUrlError):
        resolver.resolve("https://www.youtube.com/")


def test_non_youtube_url_is_unsupported(resolver: DefaultInputResolver):
    with pytest.raises(UnsupportedInputError):
        resolver.resolve("https://vimeo.com/12345")


def test_missing_local_file_raises_source_not_found(resolver: DefaultInputResolver, tmp_path: Path):
    missing = tmp_path / "missing.wav"
    with pytest.raises(SourceNotFoundError):
        resolver.resolve(str(missing))


def test_local_audio_file_is_classified(resolver: DefaultInputResolver, tmp_path: Path):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"fake wav content")
    resolved = resolver.resolve(str(audio))
    assert resolved.input_type is InputType.LOCAL_AUDIO
    assert resolved.local_path == audio.resolve()


def test_local_video_file_is_classified(resolver: DefaultInputResolver, tmp_path: Path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake mp4 content")
    resolved = resolver.resolve(str(video))
    assert resolved.input_type is InputType.LOCAL_VIDEO


def test_unsupported_extension_raises(resolver: DefaultInputResolver, tmp_path: Path):
    unknown = tmp_path / "document.pdf"
    unknown.write_bytes(b"not a media file")
    with pytest.raises(UnsupportedInputError):
        resolver.resolve(str(unknown))

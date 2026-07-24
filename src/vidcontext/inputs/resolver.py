"""Input Resolver: the first step.

Takes the raw string the user passed on the CLI and returns a classified
ResolvedInput, or raises an explicit domain exception.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from vidcontext.exceptions import (
    InvalidYouTubeUrlError,
    PlaylistNotSupportedError,
    SourceNotFoundError,
    UnsupportedInputError,
)
from vidcontext.inputs.local_file import classify_local_file
from vidcontext.inputs.youtube import extract_video_id, is_playlist_url, is_youtube_url
from vidcontext.models import InputType, ResolvedInput


class InputResolver(Protocol):
    def resolve(self, source: str) -> ResolvedInput: ...


class DefaultInputResolver:
    def resolve(self, source: str) -> ResolvedInput:
        stripped = source.strip()

        if is_youtube_url(stripped):
            if is_playlist_url(stripped):
                raise PlaylistNotSupportedError(f"Playlists are not supported: {stripped}")
            video_id = extract_video_id(stripped)
            if not video_id:
                raise InvalidYouTubeUrlError(f"Could not extract a video id from: {stripped}")
            return ResolvedInput(
                input_type=InputType.YOUTUBE,
                source_uri=stripped,
                youtube_video_id=video_id,
            )

        if stripped.startswith(("http://", "https://")):
            raise UnsupportedInputError(f"Only YouTube URLs are supported: {stripped}")

        path = Path(stripped).expanduser()
        if not path.is_file():
            raise SourceNotFoundError(f"File not found: {path}")

        input_type = classify_local_file(path)
        if input_type is None:
            raise UnsupportedInputError(f"Unsupported extension: {path.suffix or '(no extension)'}")

        return ResolvedInput(
            input_type=input_type,
            source_uri=str(path),
            local_path=path.resolve(),
        )

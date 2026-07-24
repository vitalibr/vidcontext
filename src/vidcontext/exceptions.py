"""Domain exceptions. The CLI catches VidContextError and prints a clean
message, without a traceback unless --verbose is used.
"""

from __future__ import annotations


class VidContextError(Exception):
    """Base of every vidcontext domain exception."""


class UnsupportedInputError(VidContextError):
    pass


class SourceNotFoundError(VidContextError):
    pass


class InvalidYouTubeUrlError(VidContextError):
    pass


class PlaylistNotSupportedError(VidContextError):
    pass


class MediaUnavailableError(VidContextError):
    pass


class SubtitleUnavailableError(VidContextError):
    pass


class DownloadError(VidContextError):
    pass


class FFmpegError(VidContextError):
    pass


class TranscriptionError(VidContextError):
    pass


class FrameExtractionError(VidContextError):
    pass


class InvalidArtifactError(VidContextError):
    pass


class MediaLimitExceededError(VidContextError):
    """Duration or file size above the configured limit."""

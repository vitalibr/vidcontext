"""YouTube URL recognition.

This module only parses URLs (no network access). Downloading and
fetching subtitles live in a dedicated MediaProvider.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}


def is_youtube_url(source: str) -> bool:
    try:
        parsed = urlparse(source)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() in _YOUTUBE_HOSTS


def is_playlist_url(source: str) -> bool:
    parsed = urlparse(source)
    query = parse_qs(parsed.query)
    return "list" in query


def extract_video_id(source: str) -> str | None:
    parsed = urlparse(source)
    host = parsed.netloc.lower()

    if host == "youtu.be":
        candidate = parsed.path.lstrip("/")
        return candidate if _VIDEO_ID_RE.match(candidate) else None

    query = parse_qs(parsed.query)
    if "v" in query and query["v"]:
        candidate = query["v"][0]
        return candidate if _VIDEO_ID_RE.match(candidate) else None

    for prefix in ("/shorts/", "/live/", "/embed/"):
        if parsed.path.startswith(prefix):
            candidate = parsed.path.removeprefix(prefix).split("/")[0]
            return candidate if _VIDEO_ID_RE.match(candidate) else None

    return None

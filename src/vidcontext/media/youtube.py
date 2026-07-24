"""Real MediaProvider for YouTube, using yt-dlp as a library.

Encapsulates the entire YouTube integration: the rest of the tool only
knows about MediaMetadata, TranscriptTrack, and MediaProvider - never
yt-dlp directly.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import Any, cast

import yt_dlp

from vidcontext.exceptions import DownloadError, MediaUnavailableError, SubtitleUnavailableError
from vidcontext.media.base import SubtitleTrack, TranscriptTrack
from vidcontext.models import InputType, MediaChapter, MediaMetadata, ResolvedInput

_USER_AGENT = "Mozilla/5.0 (compatible; vidcontext/0.1)"


def _ydl_opts(**overrides: Any) -> dict[str, Any]:
    opts: dict[str, Any] = {"quiet": True, "no_warnings": True, "skip_download": True}
    opts.update(overrides)
    return opts


class YouTubeMediaProvider:
    """Does not touch the network until the first method is called; the
    yt-dlp result is cached per URL so info extraction isn't repeated
    within the same run (get_metadata + list_transcripts +
    download_subtitle)."""

    def __init__(self) -> None:
        self._info_cache: dict[str, Any] = {}

    def _extract_info(self, resolved: ResolvedInput) -> Any:
        if resolved.source_uri in self._info_cache:
            return self._info_cache[resolved.source_uri]
        try:
            with yt_dlp.YoutubeDL(cast(Any, _ydl_opts())) as ydl:
                info = ydl.extract_info(resolved.source_uri, download=False)
        except yt_dlp.utils.DownloadError as exc:
            raise MediaUnavailableError(f"could not access {resolved.source_uri}: {exc}") from exc
        if info is None:
            raise MediaUnavailableError(f"yt-dlp returned no metadata for {resolved.source_uri}")
        self._info_cache[resolved.source_uri] = info
        return info

    def get_metadata(self, resolved: ResolvedInput) -> MediaMetadata:
        from vidcontext.workspace import compute_source_id  # avoid a circular import up top

        info = self._extract_info(resolved)
        chapters = [
            MediaChapter(
                title=chapter.get("title") or "",
                start=float(chapter.get("start_time") or 0.0),
                end=float(chapter.get("end_time") or 0.0),
            )
            for chapter in info.get("chapters") or []
        ]
        return MediaMetadata(
            source_id=compute_source_id(resolved),
            input_type=InputType.YOUTUBE,
            source_uri=resolved.source_uri,
            title=info.get("title"),
            author=info.get("uploader") or info.get("channel"),
            description=info.get("description"),
            duration_seconds=float(info.get("duration") or 0.0),
            language_hint=info.get("language"),
            chapters=chapters,
            has_video=info.get("vcodec") not in (None, "none"),
            has_audio=info.get("acodec") not in (None, "none"),
        )

    def list_transcripts(self, resolved: ResolvedInput) -> list[TranscriptTrack]:
        info = self._extract_info(resolved)
        tracks: list[TranscriptTrack] = []
        for language in info.get("subtitles") or {}:
            tracks.append(SubtitleTrack(language=language, is_generated=False))
        for language in info.get("automatic_captions") or {}:
            tracks.append(SubtitleTrack(language=language, is_generated=True))
        return tracks

    def download_subtitle(
        self, resolved: ResolvedInput, track: TranscriptTrack, destination: Path
    ) -> Path:
        info = self._extract_info(resolved)
        track_map = info.get("automatic_captions") if track.is_generated else info.get("subtitles")
        entries: list[dict[str, Any]] = (track_map or {}).get(track.language) or []
        entry = next((e for e in entries if e.get("ext") == "vtt"), None) or (
            entries[0] if entries else None
        )
        if entry is None or not entry.get("url"):
            raise SubtitleUnavailableError(
                f"no '{track.language}' subtitle (generated={track.is_generated}) available"
            )
        request = urllib.request.Request(entry["url"], headers={"User-Agent": _USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read()
        except OSError as exc:
            raise SubtitleUnavailableError(
                f"failed to download subtitle from {entry['url']}: {exc}"
            ) from exc
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return destination

    def download_audio(self, resolved: ResolvedInput, destination: Path) -> Path:
        return self._download(
            resolved,
            destination,
            {
                "format": "bestaudio/best",
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
            },
        )

    def download_video(self, resolved: ResolvedInput, destination: Path) -> Path:
        return self._download(resolved, destination, {"format": "bestvideo+bestaudio/best"})

    def _download(
        self, resolved: ResolvedInput, destination: Path, extra_opts: dict[str, Any]
    ) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        out_template = f"{destination.with_suffix('')}.%(ext)s"
        opts = _ydl_opts(skip_download=False, outtmpl=out_template, **extra_opts)
        try:
            with yt_dlp.YoutubeDL(cast(Any, opts)) as ydl:
                ydl.download([resolved.source_uri])
        except yt_dlp.utils.DownloadError as exc:
            raise DownloadError(
                f"failed to download media from {resolved.source_uri}: {exc}"
            ) from exc

        candidates = sorted(destination.parent.glob(destination.stem + ".*"))
        if not candidates:
            raise DownloadError(f"yt-dlp produced no file for {destination}")
        produced = candidates[0]
        if produced != destination:
            produced.replace(destination)
        return destination

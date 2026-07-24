"""Third link in the YouTube fallback chain: when yt-dlp exposes neither a
manual nor an automatic subtitle, try youtube-transcript-api before
falling back to local transcription (ASR)."""

from __future__ import annotations

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import YouTubeTranscriptApiException

from vidcontext.models import Transcript, TranscriptSegment, TranscriptSource


def fetch_via_transcript_api(video_id: str, language_hint: str | None = None) -> Transcript | None:
    languages = [language_hint] if language_hint else ["en"]
    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=languages)
    except YouTubeTranscriptApiException:
        return None

    segments = [
        TranscriptSegment(
            id=f"seg-{i:04d}",
            start=snippet.start,
            end=snippet.start + snippet.duration,
            text=snippet.text.strip(),
        )
        for i, snippet in enumerate(fetched)
        if snippet.text.strip()
    ]
    if not segments:
        return None

    full_text = " ".join(segment.text for segment in segments)
    return Transcript(
        language=language_hint or "en",
        source=TranscriptSource.YOUTUBE_GENERATED,
        segments=segments,
        full_text=full_text,
    )

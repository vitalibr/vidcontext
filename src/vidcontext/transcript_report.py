"""Markdown with the full transcript and timestamps, meant to be read by
an AI agent (or a person).

Contains no summary, highlights, or analysis - the raw transcript is the
only content. Deciding what matters is the job of whoever reads this file,
not this tool (the tool calls no AI API itself).
"""

from __future__ import annotations

from vidcontext.models import InputType, MediaMetadata, Transcript


def _format_timestamp(seconds: float) -> str:
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _timestamp_label(metadata: MediaMetadata, seconds: float) -> str:
    label = _format_timestamp(seconds)
    if metadata.input_type is InputType.YOUTUBE:
        video_id = metadata.source_id.removeprefix("youtube-")
        url = f"https://www.youtube.com/watch?v={video_id}&t={int(seconds)}s"
        return f"[{label}]({url})"
    return label


def build_transcript_markdown(metadata: MediaMetadata, transcript: Transcript) -> str:
    lines: list[str] = []
    title = metadata.title or metadata.source_id
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"- Source: `{metadata.input_type.value}` - {metadata.source_uri}")
    lines.append(f"- Author: {metadata.author or '(unknown)'}")
    lines.append(f"- Duration: {_format_timestamp(metadata.duration_seconds)}")
    lines.append(f"- Transcript: `{transcript.source.value}` (language: {transcript.language})")
    lines.append("")
    lines.append("## Transcript")
    lines.append("")
    for segment in transcript.segments:
        timestamp = _timestamp_label(metadata, segment.start)
        lines.append(f"**{timestamp}** {segment.text}")
    lines.append("")
    return "\n".join(lines)

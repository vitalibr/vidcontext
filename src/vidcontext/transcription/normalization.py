"""Subtitle parsing (VTT/SRT) and normalization into the Transcript model.

Preserves timestamps and never translates the content.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from vidcontext.models import Transcript, TranscriptSegment, TranscriptSource

_TAG_RE = re.compile(r"<[^>]*>")
_VTT_TIME_RE = re.compile(r"(?:(\d{2}):)?(\d{2}):(\d{2})\.(\d{3})")
_SRT_TIME_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})")


@dataclass
class RawCue:
    start: float
    end: float
    text: str


def _parse_vtt_timestamp(token: str) -> float:
    match = _VTT_TIME_RE.match(token.strip())
    if not match:
        raise ValueError(f"invalid VTT timestamp: {token!r}")
    hours = int(match.group(1)) if match.group(1) else 0
    minutes, seconds, millis = (int(match.group(i)) for i in (2, 3, 4))
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def _parse_srt_timestamp(token: str) -> float:
    match = _SRT_TIME_RE.match(token.strip())
    if not match:
        raise ValueError(f"invalid SRT timestamp: {token!r}")
    hours, minutes, seconds, millis = (int(g) for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def _parse_cue_blocks(content: str, timestamp_parser: Callable[[str], float]) -> list[RawCue]:
    lines = content.replace("\r\n", "\n").split("\n")
    cues: list[RawCue] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-->" in line:
            start_token, _, rest = line.partition("-->")
            end_token = rest.strip().split(" ")[0]
            start = timestamp_parser(start_token)
            end = timestamp_parser(end_token)
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i])
                i += 1
            text = _TAG_RE.sub("", " ".join(text_lines)).strip()
            if text:
                cues.append(RawCue(start=start, end=end, text=text))
        else:
            i += 1
    return cues


def parse_vtt(content: str) -> list[RawCue]:
    return _parse_cue_blocks(content, _parse_vtt_timestamp)


def parse_srt(content: str) -> list[RawCue]:
    return _parse_cue_blocks(content, _parse_srt_timestamp)


def merge_rolling_cues(cues: list[RawCue]) -> list[RawCue]:
    """YouTube auto-captions frequently 'roll': each cue repeats the
    previous one's text and appends a new word (e.g. cue1='hello',
    cue2='hello world', cue3='hello world how are you'). Without this,
    the final text would be duplicated several times over. Here, cues
    whose text is a prefix (in either direction) of their neighbor are
    collapsed into the longer version."""
    merged: list[RawCue] = []
    for cue in cues:
        if merged and (
            cue.text.startswith(merged[-1].text) or merged[-1].text.startswith(cue.text)
        ):
            longer = cue.text if len(cue.text) >= len(merged[-1].text) else merged[-1].text
            merged[-1] = RawCue(start=merged[-1].start, end=cue.end, text=longer)
        else:
            merged.append(cue)
    return merged


def build_transcript(cues: list[RawCue], language: str, source: TranscriptSource) -> Transcript:
    merged = merge_rolling_cues(cues)
    segments = [
        TranscriptSegment(id=f"seg-{i:04d}", start=cue.start, end=cue.end, text=cue.text)
        for i, cue in enumerate(merged)
    ]
    full_text = " ".join(segment.text for segment in segments)
    return Transcript(language=language, source=source, segments=segments, full_text=full_text)

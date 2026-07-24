"""Extraction of candidate frames per moment.

Moments (timestamps or intervals) are chosen by whoever calls the tool
(typically an AI agent that already read the transcript), not by this
tool. Extraction uses real ffmpeg calls; real quality/selection logic
lives in frame_quality.py and frame_selector.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from vidcontext.exceptions import FFmpegError
from vidcontext.media.ffmpeg import extract_frame
from vidcontext.models import ExtractedFrame, Moment


class FrameExtractor(Protocol):
    def extract_candidates(
        self, moment: Moment, video_path: Path, output_dir: Path
    ) -> list[ExtractedFrame]: ...


def _candidate_timestamps(moment: Moment) -> list[float]:
    duration = moment.end - moment.start
    if duration <= 0:
        return [moment.start]

    margin = min(1.0, duration / 4)
    points = {
        max(moment.start, moment.start + margin),
        moment.start + duration * 0.25,
        moment.start + duration * 0.5,
        moment.start + duration * 0.75,
        max(moment.start, moment.end - margin),
        moment.representative_time,
    }
    return sorted(p for p in points if moment.start <= p <= moment.end)


class FfmpegFrameExtractor:
    """Extracts real candidate frames via ffmpeg, at several points across
    the moment's interval (not just a single timestamp)."""

    def extract_candidates(
        self, moment: Moment, video_path: Path, output_dir: Path
    ) -> list[ExtractedFrame]:
        frames: list[ExtractedFrame] = []
        for idx, timestamp in enumerate(_candidate_timestamps(moment)):
            destination = output_dir / f"{moment.id}-frame-{idx:02d}.jpg"
            try:
                extract_frame(video_path, timestamp, destination)
            except FFmpegError:
                continue
            frames.append(
                ExtractedFrame(
                    id=f"{moment.id}-frame-{idx:02d}",
                    moment_id=moment.id,
                    timestamp=timestamp,
                    path=str(destination),
                )
            )
        return frames

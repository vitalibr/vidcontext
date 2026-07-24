"""Selection of the best candidate frames per moment.

Computes luminance (black frame), sharpness (blur), and a perceptual hash
per candidate; drops black frames, groups near-duplicates by hash, and
picks the sharpest one from each group - up to `max_frames` total.
"""

from __future__ import annotations

from pathlib import Path

from vidcontext.models import ExtractedFrame
from vidcontext.visual.frame_quality import (
    compute_average_hash,
    compute_black_frame_score,
    compute_blur_score,
    hamming_distance,
    is_black_frame,
)

MAX_SELECTED_FRAMES_DEFAULT = 3
DEDUP_HAMMING_THRESHOLD = 6  # out of 64 bits; below this we treat frames as "near identical"


def select_frames(
    frames: list[ExtractedFrame], max_frames: int = MAX_SELECTED_FRAMES_DEFAULT
) -> list[ExtractedFrame]:
    if not frames:
        return []

    scored: list[tuple[ExtractedFrame, str]] = []
    for frame in frames:
        path = Path(frame.path)
        frame.black_frame_score = compute_black_frame_score(path)
        frame.blur_score = compute_blur_score(path)
        scored.append((frame, compute_average_hash(path)))

    non_black = [item for item in scored if not is_black_frame(item[0].black_frame_score)]
    candidates = non_black or scored  # if every frame is black, don't end up with none at all

    groups: list[list[tuple[ExtractedFrame, str]]] = []
    for frame, frame_hash in candidates:
        for group in groups:
            if hamming_distance(frame_hash, group[0][1]) <= DEDUP_HAMMING_THRESHOLD:
                group.append((frame, frame_hash))
                break
        else:
            groups.append([(frame, frame_hash)])

    representatives: list[ExtractedFrame] = []
    for group_index, group in enumerate(groups):
        for frame, _ in group:
            frame.duplicate_group = f"group-{group_index:02d}"
        best = max(group, key=lambda item: item[0].blur_score or 0.0)
        representatives.append(best[0])

    representatives.sort(key=lambda frame: frame.blur_score or 0.0, reverse=True)
    selected = representatives[:max_frames]
    for frame in selected:
        frame.selected = True
    return selected

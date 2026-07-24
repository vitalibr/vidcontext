"""Tests the frame quality heuristics with synthetic images generated via
Pillow (no ffmpeg dependency)."""

from pathlib import Path

from PIL import Image, ImageDraw

from vidcontext.models import ExtractedFrame
from vidcontext.visual.frame_quality import (
    compute_average_hash,
    compute_black_frame_score,
    compute_blur_score,
    hamming_distance,
    is_black_frame,
)
from vidcontext.visual.frame_selector import select_frames


def _save(path: Path, image: Image.Image) -> Path:
    image.save(path)
    return path


def _black_image(size: int = 64) -> Image.Image:
    return Image.new("RGB", (size, size), color=(0, 0, 0))


def _flat_gray_image(size: int = 64) -> Image.Image:
    return Image.new("RGB", (size, size), color=(128, 128, 128))


def _checkerboard_image(size: int = 64, cell: int = 4) -> Image.Image:
    img = Image.new("RGB", (size, size), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    for y in range(0, size, cell):
        for x in range(0, size, cell):
            if ((x // cell) + (y // cell)) % 2 == 0:
                draw.rectangle([x, y, x + cell, y + cell], fill=(0, 0, 0))
    return img


def test_black_frame_has_low_luminance_and_is_flagged(tmp_path: Path):
    path = _save(tmp_path / "black.jpg", _black_image())
    score = compute_black_frame_score(path)
    assert score < 0.05
    assert is_black_frame(score) is True


def test_bright_flat_frame_is_not_flagged_as_black(tmp_path: Path):
    path = _save(tmp_path / "gray.jpg", _flat_gray_image())
    score = compute_black_frame_score(path)
    assert is_black_frame(score) is False


def test_checkerboard_has_higher_blur_score_than_flat_image(tmp_path: Path):
    flat_path = _save(tmp_path / "flat.jpg", _flat_gray_image())
    sharp_path = _save(tmp_path / "sharp.jpg", _checkerboard_image())

    flat_blur = compute_blur_score(flat_path)
    sharp_blur = compute_blur_score(sharp_path)

    assert sharp_blur > flat_blur


def test_average_hash_is_stable_for_identical_images(tmp_path: Path):
    path_a = _save(tmp_path / "a.jpg", _checkerboard_image())
    path_b = _save(tmp_path / "b.jpg", _checkerboard_image())

    hash_a = compute_average_hash(path_a)
    hash_b = compute_average_hash(path_b)

    assert hamming_distance(hash_a, hash_b) == 0


def test_average_hash_differs_for_different_images(tmp_path: Path):
    hash_flat = compute_average_hash(_save(tmp_path / "flat.jpg", _flat_gray_image()))
    hash_sharp = compute_average_hash(_save(tmp_path / "sharp.jpg", _checkerboard_image()))

    assert hamming_distance(hash_flat, hash_sharp) > 0


def test_select_frames_drops_black_frames_and_prefers_sharper_duplicates(tmp_path: Path):
    black_path = _save(tmp_path / "black.jpg", _black_image())
    dup_a_path = _save(tmp_path / "dup_a.jpg", _checkerboard_image())
    dup_b_path = _save(tmp_path / "dup_b.jpg", _checkerboard_image())

    frames = [
        ExtractedFrame(id="f0", moment_id="m", timestamp=0.0, path=str(black_path)),
        ExtractedFrame(id="f1", moment_id="m", timestamp=1.0, path=str(dup_a_path)),
        ExtractedFrame(id="f2", moment_id="m", timestamp=2.0, path=str(dup_b_path)),
    ]

    selected = select_frames(frames, max_frames=3)

    selected_ids = {f.id for f in selected}
    assert "f0" not in selected_ids  # black frame dropped
    assert len(selected_ids) == 1  # f1 and f2 are near-identical -> a single representative
    assert frames[1].duplicate_group == frames[2].duplicate_group


def test_select_frames_caps_at_max_frames(tmp_path: Path):
    frames = []
    for i in range(5):
        img = _checkerboard_image(cell=2 + i)
        path = _save(tmp_path / f"frame-{i}.jpg", img)
        frames.append(
            ExtractedFrame(id=f"f{i}", moment_id="m", timestamp=float(i), path=str(path))
        )

    selected = select_frames(frames, max_frames=2)
    assert len(selected) == 2
    assert all(f.selected for f in selected)


def test_select_frames_handles_empty_list():
    assert select_frames([]) == []

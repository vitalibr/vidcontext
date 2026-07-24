"""Real frame quality heuristics: black-frame detection, blur (Laplacian
variance), and a perceptual hash (average hash) for deduplication. No
OpenCV dependency - just Pillow + numpy.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

BLACK_FRAME_LUMINANCE_THRESHOLD = 0.08

_LAPLACIAN_KERNEL = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)


def _load_grayscale(path: Path) -> np.ndarray:
    with Image.open(path) as img:
        return np.asarray(img.convert("L"), dtype=np.float32)


def compute_black_frame_score(path: Path) -> float:
    """Mean luminance normalized to [0, 1]. Low values indicate a black
    (or near-black) frame."""
    gray = _load_grayscale(path)
    return float(gray.mean() / 255.0)


def is_black_frame(score: float | None) -> bool:
    return score is not None and score < BLACK_FRAME_LUMINANCE_THRESHOLD


def _convolve2d(image: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    kh, kw = kernel.shape
    pad_h, pad_w = kh // 2, kw // 2
    padded = np.pad(image, ((pad_h, pad_h), (pad_w, pad_w)), mode="edge")
    out = np.zeros_like(image)
    for i in range(kh):
        for j in range(kw):
            out += kernel[i, j] * padded[i : i + image.shape[0], j : j + image.shape[1]]
    return out


def compute_blur_score(path: Path) -> float:
    """Laplacian variance: the higher, the sharper (less blurry)."""
    gray = _load_grayscale(path)
    laplacian = _convolve2d(gray, _LAPLACIAN_KERNEL)
    return float(laplacian.var())


def compute_average_hash(path: Path, hash_size: int = 8) -> str:
    """Average hash (aHash): downsamples the image to a small grid and
    compares each pixel to the mean, producing a binary signature to
    compare similarity between frames (deduplication)."""
    with Image.open(path) as img:
        small = img.convert("L").resize((hash_size, hash_size), Image.Resampling.LANCZOS)
    pixels = np.asarray(small, dtype=np.float32)
    average = pixels.mean()
    bits = (pixels > average).flatten()
    return "".join("1" if bit else "0" for bit in bits)


def hamming_distance(hash_a: str, hash_b: str) -> int:
    return sum(a != b for a, b in zip(hash_a, hash_b, strict=True))

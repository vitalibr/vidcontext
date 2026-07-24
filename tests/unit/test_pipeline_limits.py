"""Tests the duration and file-size limits."""

from pathlib import Path

import pytest

from vidcontext.config import AppConfig
from vidcontext.exceptions import MediaLimitExceededError
from vidcontext.inputs.resolver import DefaultInputResolver
from vidcontext.mocks import MockMediaProvider, MockTranscriber
from vidcontext.pipeline import Providers, VidContext
from vidcontext.visual.frame_extractor import FfmpegFrameExtractor

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _providers() -> Providers:
    return Providers(
        resolver=DefaultInputResolver(),
        media_provider=MockMediaProvider(),
        transcriber=MockTranscriber(),
        frame_extractor=FfmpegFrameExtractor(),
    )


def test_file_size_over_limit_raises_before_any_artifact_is_created(tmp_path: Path):
    big_file = tmp_path / "big.wav"
    big_file.write_bytes(b"0" * 2048)

    config = AppConfig(runs_dir=tmp_path / "runs", use_mocks=True, max_file_size_bytes=1024)
    tool = VidContext(config=config, providers=_providers())

    with pytest.raises(MediaLimitExceededError):
        tool.run_transcript(str(big_file))

    assert not (tmp_path / "runs").exists()


def test_file_size_within_limit_proceeds(tmp_path: Path):
    config = AppConfig(runs_dir=tmp_path, use_mocks=True, max_file_size_bytes=10 * 1024 * 1024)
    tool = VidContext(config=config, providers=_providers())

    result = tool.run_transcript(str(FIXTURES_DIR / "sample-audio.wav"))
    assert result.transcript_md_path.exists()


def test_duration_over_limit_raises_after_metadata_stage(tmp_path: Path):
    config = AppConfig(runs_dir=tmp_path, use_mocks=True, max_duration_seconds=1.0)
    tool = VidContext(config=config, providers=_providers())

    with pytest.raises(MediaLimitExceededError):
        tool.run_transcript(str(FIXTURES_DIR / "sample-audio.wav"))

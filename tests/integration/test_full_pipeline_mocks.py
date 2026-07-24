"""Tests both tools end to end with mock providers: run resumption and
cache invalidation via --force for transcript; real frame extraction for
screenshots."""

from pathlib import Path

import pytest

from vidcontext.config import AppConfig
from vidcontext.inputs.resolver import DefaultInputResolver
from vidcontext.mocks import MockMediaProvider, MockTranscriber
from vidcontext.models import Moment, ResolvedInput, StageStatus
from vidcontext.pipeline import Providers, VidContext
from vidcontext.visual.frame_extractor import FfmpegFrameExtractor

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


class CountingMediaProvider(MockMediaProvider):
    def __init__(self) -> None:
        self.metadata_calls = 0

    def get_metadata(self, resolved: ResolvedInput):
        self.metadata_calls += 1
        return super().get_metadata(resolved)


def _providers(media_provider: MockMediaProvider | None = None) -> Providers:
    return Providers(
        resolver=DefaultInputResolver(),
        media_provider=media_provider or MockMediaProvider(),
        transcriber=MockTranscriber(),
        frame_extractor=FfmpegFrameExtractor(),
    )


def test_audio_only_transcript_produces_full_artifact_tree(tmp_path: Path):
    config = AppConfig(runs_dir=tmp_path, use_mocks=True)
    tool = VidContext(config=config, providers=_providers())

    result = tool.run_transcript(str(FIXTURES_DIR / "sample-audio.wav"))

    assert result.transcript_md_path.exists()
    assert result.transcript_json_path.exists()
    assert result.transcript_txt_path.exists()
    assert (result.workspace.root / "manifest.json").exists()

    assert result.manifest.stages["metadata"].status is StageStatus.COMPLETED
    assert result.manifest.stages["transcription"].status is StageStatus.COMPLETED
    assert result.metadata.input_type.value == "local_audio"


def test_second_run_reuses_cache_without_recomputing_metadata(tmp_path: Path):
    config = AppConfig(runs_dir=tmp_path, use_mocks=True)
    media_provider = CountingMediaProvider()
    tool = VidContext(config=config, providers=_providers(media_provider))

    tool.run_transcript(str(FIXTURES_DIR / "sample-audio.wav"))
    assert media_provider.metadata_calls == 1

    tool.run_transcript(str(FIXTURES_DIR / "sample-audio.wav"))
    assert media_provider.metadata_calls == 1  # cache reused, not called again


def test_force_flag_invalidates_cache(tmp_path: Path):
    config = AppConfig(runs_dir=tmp_path, use_mocks=True, force=True)
    media_provider = CountingMediaProvider()
    tool = VidContext(config=config, providers=_providers(media_provider))

    tool.run_transcript(str(FIXTURES_DIR / "sample-audio.wav"))
    tool.run_transcript(str(FIXTURES_DIR / "sample-audio.wav"))

    assert media_provider.metadata_calls == 2


def test_screenshots_extracts_real_frames_for_local_video(tmp_path: Path):
    video_fixture = FIXTURES_DIR / "sample-video.mp4"
    if not video_fixture.exists():
        pytest.skip("sample-video.mp4 fixture not generated in this environment")

    config = AppConfig(runs_dir=tmp_path, use_mocks=True)
    tool = VidContext(config=config, providers=_providers())
    moments = [Moment(id="moment-0000", start=1.0, end=4.0, representative_time=2.5)]

    result = tool.run_screenshots(str(video_fixture), moments)

    assert result.moments_json_path.exists()
    assert any(result.workspace.frame_selected_dir.iterdir())
    assert len(result.frames_by_moment["moment-0000"]) > 0


def test_screenshots_raises_for_audio_only_source(tmp_path: Path):
    from vidcontext.exceptions import MediaUnavailableError

    config = AppConfig(runs_dir=tmp_path, use_mocks=True)
    tool = VidContext(config=config, providers=_providers())
    moments = [Moment(id="moment-0000", start=0.0, end=1.0, representative_time=0.5)]

    with pytest.raises(MediaUnavailableError):
        tool.run_screenshots(str(FIXTURES_DIR / "sample-audio.wav"), moments)

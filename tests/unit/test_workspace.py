from pathlib import Path

import pytest

from vidcontext.exceptions import InvalidArtifactError
from vidcontext.models import InputType, ResolvedInput
from vidcontext.workspace import Workspace, compute_source_id


def test_compute_source_id_for_youtube_uses_video_id():
    resolved = ResolvedInput(
        input_type=InputType.YOUTUBE,
        source_uri="https://www.youtube.com/watch?v=abc12345678",
        youtube_video_id="abc12345678",
    )
    assert compute_source_id(resolved) == "youtube-abc12345678"


def test_compute_source_id_for_local_file_is_content_based(tmp_path: Path):
    file_a = tmp_path / "a.wav"
    file_b = tmp_path / "b.wav"
    file_a.write_bytes(b"same content")
    file_b.write_bytes(b"same content")

    resolved_a = ResolvedInput(
        input_type=InputType.LOCAL_AUDIO, source_uri=str(file_a), local_path=file_a
    )
    resolved_b = ResolvedInput(
        input_type=InputType.LOCAL_AUDIO, source_uri=str(file_b), local_path=file_b
    )

    # Same content, different names -> same source_id (content hash, not name).
    assert compute_source_id(resolved_a) == compute_source_id(resolved_b)
    assert compute_source_id(resolved_a).startswith("local-")


def test_compute_source_id_changes_when_content_changes(tmp_path: Path):
    file_a = tmp_path / "a.wav"
    file_a.write_bytes(b"content one")
    resolved = ResolvedInput(
        input_type=InputType.LOCAL_AUDIO, source_uri=str(file_a), local_path=file_a
    )
    first_id = compute_source_id(resolved)

    file_a.write_bytes(b"content two, different")
    second_id = compute_source_id(resolved)

    assert first_id != second_id


def test_compute_source_id_youtube_without_video_id_raises():
    resolved = ResolvedInput(input_type=InputType.YOUTUBE, source_uri="https://youtu.be/x")
    with pytest.raises(InvalidArtifactError):
        compute_source_id(resolved)


def test_workspace_ensure_dirs_creates_expected_layout(tmp_path: Path):
    resolved = ResolvedInput(
        input_type=InputType.YOUTUBE,
        source_uri="https://youtu.be/abc12345678",
        youtube_video_id="abc12345678",
    )
    workspace = Workspace.for_resolved_input(resolved, tmp_path)
    workspace.ensure_dirs()
    workspace.ensure_frame_dirs()

    assert workspace.root == tmp_path / "youtube-abc12345678"
    for directory in (
        workspace.source_dir,
        workspace.transcript_dir,
        workspace.frame_candidates_dir,
        workspace.frame_selected_dir,
    ):
        assert directory.is_dir()

from pathlib import Path

from vidcontext.models import InputType, ResolvedInput, StageName, StageStatus
from vidcontext.workspace import ManifestStore, Workspace


def _workspace(tmp_path: Path) -> Workspace:
    resolved = ResolvedInput(
        input_type=InputType.YOUTUBE,
        source_uri="https://youtu.be/abc12345678",
        youtube_video_id="abc12345678",
    )
    workspace = Workspace.for_resolved_input(resolved, tmp_path)
    workspace.ensure_dirs()
    return workspace


def test_load_or_create_creates_fresh_manifest_when_missing(tmp_path: Path):
    workspace = _workspace(tmp_path)
    store = ManifestStore(workspace)

    manifest = store.load_or_create()

    assert manifest.source_id == workspace.source_id
    assert not workspace.manifest_path.exists()  # load_or_create doesn't persist by itself


def test_save_then_load_roundtrips(tmp_path: Path):
    workspace = _workspace(tmp_path)
    store = ManifestStore(workspace)
    manifest = store.load_or_create()

    store.mark(manifest, StageName.METADATA, StageStatus.COMPLETED, artifact="metadata.json")

    reloaded = store.load_or_create()
    assert reloaded.stages["metadata"].status is StageStatus.COMPLETED
    assert reloaded.stages["metadata"].artifact == "metadata.json"


def test_is_reusable_false_when_not_completed(tmp_path: Path):
    workspace = _workspace(tmp_path)
    store = ManifestStore(workspace)
    manifest = store.load_or_create()

    assert store.is_reusable(manifest, StageName.METADATA, workspace.metadata_path) is False


def test_is_reusable_false_when_artifact_missing_on_disk(tmp_path: Path):
    workspace = _workspace(tmp_path)
    store = ManifestStore(workspace)
    manifest = store.load_or_create()
    store.mark(manifest, StageName.METADATA, StageStatus.COMPLETED, artifact="metadata.json")

    # Artifact was never written to disk -> should not be reused.
    assert store.is_reusable(manifest, StageName.METADATA, workspace.metadata_path) is False


def test_is_reusable_true_when_completed_and_artifact_exists(tmp_path: Path):
    workspace = _workspace(tmp_path)
    store = ManifestStore(workspace)
    manifest = store.load_or_create()
    workspace.metadata_path.write_text("{}")
    store.mark(manifest, StageName.METADATA, StageStatus.COMPLETED, artifact="metadata.json")

    assert store.is_reusable(manifest, StageName.METADATA, workspace.metadata_path) is True

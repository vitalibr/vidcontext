"""Run workspace: a runs/<source-id>/ directory per run, persisting each
stage to disk so a run can resume without repeating work.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from vidcontext.exceptions import InvalidArtifactError
from vidcontext.models import (
    InputType,
    Manifest,
    ResolvedInput,
    StageName,
    StageRecord,
    StageStatus,
)

_HASH_PREFIX_LENGTH = 16
_HASH_CHUNK_SIZE = 1 << 20


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def compute_source_id(resolved: ResolvedInput) -> str:
    if resolved.input_type is InputType.YOUTUBE:
        if not resolved.youtube_video_id:
            raise InvalidArtifactError("YouTube ResolvedInput missing youtube_video_id")
        return f"youtube-{resolved.youtube_video_id}"

    if not resolved.local_path:
        raise InvalidArtifactError("Local ResolvedInput missing local_path")
    digest = hashlib.sha256()
    with resolved.local_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return f"local-{digest.hexdigest()[:_HASH_PREFIX_LENGTH]}"


@dataclass(frozen=True)
class Workspace:
    root: Path
    source_id: str

    @classmethod
    def for_resolved_input(cls, resolved: ResolvedInput, runs_dir: Path) -> Workspace:
        source_id = compute_source_id(resolved)
        return cls(root=runs_dir / source_id, source_id=source_id)

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    @property
    def metadata_path(self) -> Path:
        return self.root / "metadata.json"

    @property
    def source_dir(self) -> Path:
        return self.root / "source"

    @property
    def source_info_path(self) -> Path:
        return self.source_dir / "source-info.json"

    @property
    def audio_path(self) -> Path:
        return self.source_dir / "audio.wav"

    @property
    def video_path(self) -> Path:
        return self.source_dir / "video.mp4"

    @property
    def subtitles_path(self) -> Path:
        return self.source_dir / "subtitles.vtt"

    @property
    def transcript_dir(self) -> Path:
        return self.root / "transcript"

    @property
    def transcript_json_path(self) -> Path:
        return self.transcript_dir / "transcript.json"

    @property
    def transcript_txt_path(self) -> Path:
        return self.transcript_dir / "transcript.txt"

    @property
    def transcript_md_path(self) -> Path:
        return self.transcript_dir / "transcript.md"

    @property
    def frames_dir(self) -> Path:
        return self.root / "frames"

    @property
    def frame_candidates_dir(self) -> Path:
        return self.frames_dir / "candidates"

    @property
    def frame_selected_dir(self) -> Path:
        return self.frames_dir / "selected"

    @property
    def moments_path(self) -> Path:
        return self.frames_dir / "moments.json"

    def ensure_dirs(self) -> None:
        for directory in (self.root, self.source_dir, self.transcript_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def ensure_frame_dirs(self) -> None:
        for directory in (self.frames_dir, self.frame_candidates_dir, self.frame_selected_dir):
            directory.mkdir(parents=True, exist_ok=True)


class ManifestStore:
    """Loads and persists a workspace's manifest.json."""

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    def load_or_create(self) -> Manifest:
        path = self.workspace.manifest_path
        if not path.exists():
            return Manifest.new(self.workspace.source_id, now_iso())
        try:
            return Manifest.model_validate_json(path.read_text())
        except ValueError as exc:
            raise InvalidArtifactError(f"invalid manifest.json at {path}: {exc}") from exc

    def save(self, manifest: Manifest) -> None:
        manifest.updated_at = now_iso()
        self.workspace.root.mkdir(parents=True, exist_ok=True)
        self.workspace.manifest_path.write_text(manifest.model_dump_json(indent=2))

    def mark(
        self,
        manifest: Manifest,
        stage: StageName,
        status: StageStatus,
        artifact: str | None = None,
        error: str | None = None,
    ) -> None:
        manifest.stages[stage.value] = StageRecord(
            status=status, artifact=artifact, error=error, updated_at=now_iso()
        )
        self.save(manifest)

    def is_reusable(self, manifest: Manifest, stage: StageName, artifact_path: Path | None) -> bool:
        record = manifest.stages.get(stage.value)
        if record is None or record.status is not StageStatus.COMPLETED:
            return False
        if artifact_path is not None and not artifact_path.exists():
            return False
        return True

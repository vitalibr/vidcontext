"""Domain models shared by the two tools: transcription and screenshot
extraction.

No model here should know the details of a specific provider (YouTube,
Whisper, etc). Providers translate their native formats into these models.

This tool performs no AI content analysis: whoever reads the transcript,
decides what matters, and picks which moments become screenshots is the
agent invoking this tool, not the tool itself.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class InputType(StrEnum):
    YOUTUBE = "youtube"
    LOCAL_VIDEO = "local_video"
    LOCAL_AUDIO = "local_audio"


class ResolvedInput(BaseModel):
    """Output of the InputResolver: the user's input, already classified."""

    input_type: InputType
    source_uri: str
    local_path: Path | None = None
    youtube_video_id: str | None = None


class MediaChapter(BaseModel):
    title: str
    start: float
    end: float


class MediaMetadata(BaseModel):
    source_id: str
    input_type: InputType
    source_uri: str
    title: str | None = None
    author: str | None = None
    description: str | None = None
    duration_seconds: float
    language_hint: str | None = None
    chapters: list[MediaChapter] = Field(default_factory=list)
    has_video: bool
    has_audio: bool


class TranscriptSegment(BaseModel):
    id: str
    start: float
    end: float
    text: str
    confidence: float | None = None
    speaker: str | None = None


class TranscriptSource(StrEnum):
    YOUTUBE_MANUAL = "youtube_manual"
    YOUTUBE_GENERATED = "youtube_generated"
    LOCAL_ASR = "local_asr"
    EXTERNAL_SUBTITLE = "external_subtitle"
    MOCK = "mock"


class Transcript(BaseModel):
    schema_version: int = 1
    language: str
    source: TranscriptSource
    segments: list[TranscriptSegment]
    full_text: str


class Moment(BaseModel):
    """A point or interval in the video, chosen by the agent (not by this
    tool) to become a screenshot."""

    id: str
    label: str | None = None
    start: float
    end: float
    representative_time: float


class ExtractedFrame(BaseModel):
    id: str
    moment_id: str
    timestamp: float
    path: str
    blur_score: float | None = None
    black_frame_score: float | None = None
    duplicate_group: str | None = None
    selected: bool = False


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StageName(StrEnum):
    METADATA = "metadata"
    TRANSCRIPTION = "transcription"


class StageRecord(BaseModel):
    status: StageStatus = StageStatus.PENDING
    artifact: str | None = None
    error: str | None = None
    updated_at: str | None = None


class Manifest(BaseModel):
    version: int = 1
    source_id: str
    created_at: str
    updated_at: str
    stages: dict[str, StageRecord] = Field(default_factory=dict)

    @classmethod
    def new(cls, source_id: str, now: str) -> Manifest:
        stages = {name.value: StageRecord() for name in StageName}
        return cls(source_id=source_id, created_at=now, updated_at=now, stages=stages)

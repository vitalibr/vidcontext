from vidcontext.models import (
    InputType,
    Manifest,
    MediaMetadata,
    StageName,
    StageStatus,
    Transcript,
    TranscriptSegment,
    TranscriptSource,
)


def test_transcript_roundtrips_through_json():
    transcript = Transcript(
        language="pt",
        source=TranscriptSource.MOCK,
        segments=[TranscriptSegment(id="seg-0000", start=0.0, end=1.5, text="ola")],
        full_text="ola",
    )
    restored = Transcript.model_validate_json(transcript.model_dump_json())
    assert restored == transcript


def test_media_metadata_requires_input_type_and_duration():
    metadata = MediaMetadata(
        source_id="local-abc123",
        input_type=InputType.LOCAL_AUDIO,
        source_uri="/tmp/audio.wav",
        duration_seconds=42.0,
        has_video=False,
        has_audio=True,
    )
    assert metadata.chapters == []
    assert metadata.title is None


def test_manifest_new_initializes_every_stage_as_pending():
    manifest = Manifest.new("local-abc123", "2026-07-24T00:00:00+00:00")
    assert set(manifest.stages) == {name.value for name in StageName}
    assert all(record.status is StageStatus.PENDING for record in manifest.stages.values())

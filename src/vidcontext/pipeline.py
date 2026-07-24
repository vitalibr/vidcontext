"""Two independent tools, not one monolithic pipeline:

- `run_transcript`: resolves the input, fetches metadata, and gets the
  transcript (manual subtitle -> auto subtitle -> youtube-transcript-api
  -> local ASR).
- `run_screenshots`: given a set of moments (timestamps/intervals already
  chosen by the caller - typically an AI agent that read the transcript),
  extracts and selects the best real frames via ffmpeg.

Neither one calls any AI API: deciding what matters is the job of
whoever consumes transcript.json/transcript.md, not this tool.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from vidcontext.config import AppConfig
from vidcontext.exceptions import (
    MediaLimitExceededError,
    MediaUnavailableError,
    VidContextError,
)
from vidcontext.inputs.resolver import InputResolver
from vidcontext.logging import StageLogger
from vidcontext.media.base import MediaProvider, TranscriptTrack
from vidcontext.models import (
    ExtractedFrame,
    InputType,
    Manifest,
    MediaMetadata,
    Moment,
    ResolvedInput,
    StageName,
    StageStatus,
    Transcript,
    TranscriptSource,
)
from vidcontext.transcript_report import build_transcript_markdown
from vidcontext.transcription.base import Transcriber
from vidcontext.transcription.normalization import build_transcript, parse_vtt
from vidcontext.transcription.youtube_subtitles import fetch_via_transcript_api
from vidcontext.visual.frame_extractor import FrameExtractor
from vidcontext.visual.frame_selector import select_frames
from vidcontext.workspace import ManifestStore, Workspace


@dataclass
class Providers:
    resolver: InputResolver
    media_provider: MediaProvider
    transcriber: Transcriber
    frame_extractor: FrameExtractor


@dataclass
class TranscriptResult:
    workspace: Workspace
    manifest: Manifest
    metadata: MediaMetadata
    transcript: Transcript
    transcript_json_path: Path
    transcript_txt_path: Path
    transcript_md_path: Path


@dataclass
class ScreenshotResult:
    workspace: Workspace
    moments: list[Moment]
    frames_by_moment: dict[str, list[ExtractedFrame]]
    moments_json_path: Path


def _format_hms(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    hours, rem_ms = divmod(total_ms, 3_600_000)
    minutes, rem_ms = divmod(rem_ms, 60_000)
    secs, ms = divmod(rem_ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"


def _render_transcript_txt(transcript: Transcript) -> str:
    lines = [
        f"[{_format_hms(seg.start)} - {_format_hms(seg.end)}] {seg.text}"
        for seg in transcript.segments
    ]
    return "\n".join(lines)


def _pick_best_track(
    tracks: list[TranscriptTrack], language_hint: str | None
) -> TranscriptTrack | None:
    """Preference order: manual in the requested language, manual in
    another language, auto in the requested language, auto in another
    language."""
    manual = [t for t in tracks if not t.is_generated]
    generated = [t for t in tracks if t.is_generated]

    def _match(candidates: list[TranscriptTrack]) -> TranscriptTrack | None:
        if language_hint:
            for candidate in candidates:
                if candidate.language == language_hint or candidate.language.startswith(
                    language_hint
                ):
                    return candidate
        return candidates[0] if candidates else None

    return _match(manual) or _match(generated)


class VidContext:
    def __init__(
        self, config: AppConfig, providers: Providers, logger: StageLogger | None = None
    ) -> None:
        self.config = config
        self.providers = providers
        self.logger = logger or StageLogger(verbose=config.verbose)

    # ------------------------------------------------------------------
    # transcript
    # ------------------------------------------------------------------

    def run_transcript(self, source: str) -> TranscriptResult:
        resolved = self.providers.resolver.resolve(source)
        self._check_size_limit(resolved)
        workspace = Workspace.for_resolved_input(resolved, self.config.runs_dir)
        workspace.ensure_dirs()
        store = ManifestStore(workspace)
        manifest = store.load_or_create()
        store.save(manifest)

        metadata = self._stage_metadata(resolved, workspace, store, manifest)
        self._check_duration_limit(metadata)
        transcript = self._stage_transcription(resolved, metadata, workspace, store, manifest)

        markdown = build_transcript_markdown(metadata, transcript)
        workspace.transcript_md_path.write_text(markdown)

        return TranscriptResult(
            workspace=workspace,
            manifest=manifest,
            metadata=metadata,
            transcript=transcript,
            transcript_json_path=workspace.transcript_json_path,
            transcript_txt_path=workspace.transcript_txt_path,
            transcript_md_path=workspace.transcript_md_path,
        )

    def _check_size_limit(self, resolved: ResolvedInput) -> None:
        if resolved.local_path is None:
            return
        size = resolved.local_path.stat().st_size
        if size > self.config.max_file_size_bytes:
            raise MediaLimitExceededError(
                f"file {resolved.local_path} is {size} bytes, above the configured limit "
                f"({self.config.max_file_size_bytes} bytes)"
            )

    def _check_duration_limit(self, metadata: MediaMetadata) -> None:
        if metadata.duration_seconds > self.config.max_duration_seconds:
            raise MediaLimitExceededError(
                f"duration of {metadata.duration_seconds:.0f}s exceeds the configured limit "
                f"({self.config.max_duration_seconds:.0f}s)"
            )

    def _stage_metadata(
        self,
        resolved: ResolvedInput,
        workspace: Workspace,
        store: ManifestStore,
        manifest: Manifest,
    ) -> MediaMetadata:
        name = StageName.METADATA
        if not self.config.force and store.is_reusable(manifest, name, workspace.metadata_path):
            self.logger.stage_cached(name.value, "metadata.json")
            return MediaMetadata.model_validate_json(workspace.metadata_path.read_text())

        self.logger.stage_start(name.value)
        try:
            metadata = self.providers.media_provider.get_metadata(resolved)
        except VidContextError as exc:
            store.mark(manifest, name, StageStatus.FAILED, error=str(exc))
            raise
        workspace.metadata_path.write_text(metadata.model_dump_json(indent=2))
        store.mark(manifest, name, StageStatus.COMPLETED, artifact="metadata.json")
        self.logger.stage_completed(name.value, artifact="metadata.json")
        return metadata

    def _language_hint(self, metadata: MediaMetadata) -> str | None:
        if self.config.transcription_language != "auto":
            return self.config.transcription_language
        return metadata.language_hint

    def _stage_transcription(
        self,
        resolved: ResolvedInput,
        metadata: MediaMetadata,
        workspace: Workspace,
        store: ManifestStore,
        manifest: Manifest,
    ) -> Transcript:
        name = StageName.TRANSCRIPTION
        cached = store.is_reusable(manifest, name, workspace.transcript_json_path)
        if not self.config.force and cached:
            self.logger.stage_cached(name.value, "transcript/transcript.json")
            return Transcript.model_validate_json(workspace.transcript_json_path.read_text())

        self.logger.stage_start(name.value)
        try:
            transcript = self._acquire_transcript(resolved, metadata, workspace, name)
        except VidContextError as exc:
            store.mark(manifest, name, StageStatus.FAILED, error=str(exc))
            raise
        workspace.transcript_json_path.write_text(transcript.model_dump_json(indent=2))
        workspace.transcript_txt_path.write_text(_render_transcript_txt(transcript))
        store.mark(manifest, name, StageStatus.COMPLETED, artifact="transcript/transcript.json")
        self.logger.stage_completed(name.value, artifact="transcript/transcript.json")
        return transcript

    def _acquire_transcript(
        self,
        resolved: ResolvedInput,
        metadata: MediaMetadata,
        workspace: Workspace,
        name: StageName,
    ) -> Transcript:
        """Fallback chain: manual subtitle -> auto subtitle ->
        youtube-transcript-api -> local transcription (ASR)."""
        subtitle_transcript = self._try_subtitle_sources(resolved, workspace, name)
        if subtitle_transcript is not None:
            return subtitle_transcript

        self.logger.stage_fallback(name.value, "no subtitle available, using local ASR")
        audio_path = self.providers.media_provider.download_audio(resolved, workspace.audio_path)
        return self.providers.transcriber.transcribe(
            audio_path, language_hint=self._language_hint(metadata)
        )

    def _try_subtitle_sources(
        self, resolved: ResolvedInput, workspace: Workspace, name: StageName
    ) -> Transcript | None:
        language_hint = self._config_language_hint()
        try:
            tracks = self.providers.media_provider.list_transcripts(resolved)
        except VidContextError:
            tracks = []

        track = _pick_best_track(tracks, language_hint)
        if track is not None:
            try:
                self.providers.media_provider.download_subtitle(
                    resolved, track, workspace.subtitles_path
                )
                cues = parse_vtt(workspace.subtitles_path.read_text(encoding="utf-8"))
            except VidContextError:
                cues = []
            if cues:
                kind = "auto-generated" if track.is_generated else "manual"
                self.logger.stage_fallback(
                    name.value, f"found {kind} subtitle ({track.language})"
                )
                source = (
                    TranscriptSource.YOUTUBE_GENERATED
                    if track.is_generated
                    else TranscriptSource.YOUTUBE_MANUAL
                )
                return build_transcript(cues, track.language, source)

        if resolved.input_type is InputType.YOUTUBE and resolved.youtube_video_id:
            self.logger.stage_fallback(name.value, "trying youtube-transcript-api")
            api_transcript = fetch_via_transcript_api(resolved.youtube_video_id, language_hint)
            if api_transcript is not None:
                return api_transcript

        return None

    def _config_language_hint(self) -> str | None:
        if self.config.transcription_language == "auto":
            return None
        return self.config.transcription_language

    # ------------------------------------------------------------------
    # screenshots
    # ------------------------------------------------------------------

    def run_screenshots(self, source: str, moments: list[Moment]) -> ScreenshotResult:
        if not moments:
            raise ValueError("no moments provided")

        resolved = self.providers.resolver.resolve(source)
        workspace = Workspace.for_resolved_input(resolved, self.config.runs_dir)
        workspace.ensure_dirs()
        workspace.ensure_frame_dirs()
        store = ManifestStore(workspace)
        manifest = store.load_or_create()
        store.save(manifest)

        metadata = self._stage_metadata(resolved, workspace, store, manifest)
        if not metadata.has_video:
            raise MediaUnavailableError("source is audio-only, there is no video to screenshot")

        video_path = self.providers.media_provider.download_video(resolved, workspace.video_path)

        self.logger.stage_start("screenshots")
        frames_by_moment: dict[str, list[ExtractedFrame]] = {}
        for moment in moments:
            candidates = self.providers.frame_extractor.extract_candidates(
                moment, video_path, workspace.frame_candidates_dir
            )
            selected = select_frames(candidates)
            for frame in selected:
                selected_path = workspace.frame_selected_dir / Path(frame.path).name
                selected_path.write_bytes(Path(frame.path).read_bytes())
                frame.path = str(selected_path)
            frames_by_moment[moment.id] = selected
            message = (
                f"selected {len(selected)} of {len(candidates)} candidates for moment {moment.id}"
            )
            self.logger.stage("screenshots", message)

        self._write_moments_json(workspace, moments, frames_by_moment)
        self.logger.stage_completed("screenshots", artifact=str(workspace.moments_path))

        return ScreenshotResult(
            workspace=workspace,
            moments=moments,
            frames_by_moment=frames_by_moment,
            moments_json_path=workspace.moments_path,
        )

    @staticmethod
    def _write_moments_json(
        workspace: Workspace,
        moments: list[Moment],
        frames_by_moment: dict[str, list[ExtractedFrame]],
    ) -> None:
        payload = [
            {
                "moment": moment.model_dump(mode="json"),
                "frames": [f.model_dump(mode="json") for f in frames_by_moment.get(moment.id, [])],
            }
            for moment in moments
        ]
        workspace.moments_path.write_text(json.dumps(payload, indent=2))

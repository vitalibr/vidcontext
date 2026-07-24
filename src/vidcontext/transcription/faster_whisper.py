"""Real Transcriber via faster-whisper.

Runs locally (CPU) on any platform supported by ctranslate2 - no
dependency on Apple Silicon or a compiled whisper.cpp. The model is
downloaded from the Hugging Face Hub on first use and cached by
faster-whisper itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vidcontext.exceptions import TranscriptionError
from vidcontext.models import Transcript, TranscriptSegment, TranscriptSource


def _confidence_from_logprob(avg_logprob: float | None) -> float | None:
    if avg_logprob is None:
        return None
    # avg_logprob is a mean log-probability (typically negative). Rough
    # mapping to [0, 1], only as an approximate confidence signal.
    return max(0.0, min(1.0, 1.0 + avg_logprob))


class FasterWhisperTranscriber:
    def __init__(
        self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8"
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model: Any = None

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        from faster_whisper import WhisperModel

        try:
            self._model = WhisperModel(
                self.model_size, device=self.device, compute_type=self.compute_type
            )
        except Exception as exc:
            raise TranscriptionError(
                f"failed to load whisper model '{self.model_size}': {exc}"
            ) from exc
        return self._model

    def transcribe(self, audio_path: Path, language_hint: str | None = None) -> Transcript:
        model = self._load_model()
        try:
            segments_iter, info = model.transcribe(str(audio_path), language=language_hint)
            segments = [
                TranscriptSegment(
                    id=f"seg-{i:04d}",
                    start=seg.start,
                    end=seg.end,
                    text=seg.text.strip(),
                    confidence=_confidence_from_logprob(seg.avg_logprob),
                )
                for i, seg in enumerate(segments_iter)
                if seg.text.strip()
            ]
        except Exception as exc:
            raise TranscriptionError(f"failed to transcribe {audio_path}: {exc}") from exc

        full_text = " ".join(segment.text for segment in segments)
        return Transcript(
            language=language_hint or info.language,
            source=TranscriptSource.LOCAL_ASR,
            segments=segments,
            full_text=full_text,
        )

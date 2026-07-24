"""Tests for the faster-whisper transcriber's language code handling.

Doesn't load a real model - only exercises the pure normalization logic
that guards against sources (like yt-dlp) reporting BCP-47 tags such as
"pt-BR", which faster-whisper rejects outright.
"""

from vidcontext.transcription.faster_whisper import _normalize_language_code


def test_normalizes_bcp47_region_tag_to_bare_language_code():
    assert _normalize_language_code("pt-BR") == "pt"


def test_lowercases_already_bare_codes():
    assert _normalize_language_code("EN") == "en"


def test_passes_through_none():
    assert _normalize_language_code(None) is None

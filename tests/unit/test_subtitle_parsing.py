import pytest

from vidcontext.models import TranscriptSource
from vidcontext.transcription.normalization import (
    RawCue,
    build_transcript,
    merge_rolling_cues,
    parse_srt,
    parse_vtt,
)

ROLLING_VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.080 --> 00:00:02.720 align:start position:0%
hello<00:00:00.560><c> everyone</c><00:00:01.040><c> welcome</c>

00:00:02.720 --> 00:00:02.730 align:start position:0%
hello everyone welcome

00:00:02.730 --> 00:00:05.200 align:start position:0%
hello everyone welcome<00:00:03.200><c> back</c>

00:00:05.200 --> 00:00:08.000 align:start position:0%
this is a new sentence entirely
"""

SIMPLE_SRT = """1
00:00:01,000 --> 00:00:04,000
First line.

2
00:00:04,000 --> 00:00:06,500
Second line
with a break.
"""


def test_parse_vtt_strips_inline_tags_and_cue_settings():
    cues = parse_vtt(ROLLING_VTT)
    assert cues[0].text == "hello everyone welcome"
    assert cues[0].start == pytest.approx(0.08)
    assert cues[0].end == pytest.approx(2.72)


def test_parse_vtt_ignores_header_and_blank_blocks():
    cues = parse_vtt(ROLLING_VTT)
    assert len(cues) == 4  # should not capture "WEBVTT" / "Kind:" / "Language:" as cues


def test_merge_rolling_cues_collapses_growing_captions():
    cues = parse_vtt(ROLLING_VTT)
    merged = merge_rolling_cues(cues)

    assert len(merged) == 2
    assert merged[0].text == "hello everyone welcome back"
    assert merged[0].start == 0.08
    assert merged[0].end == 5.2
    assert merged[1].text == "this is a new sentence entirely"


def test_merge_rolling_cues_keeps_distinct_non_prefix_cues():
    cues = [
        RawCue(start=0.0, end=1.0, text="alpha"),
        RawCue(start=1.0, end=2.0, text="beta"),
    ]
    assert merge_rolling_cues(cues) == cues


def test_parse_srt_handles_multiline_text_and_comma_decimals():
    cues = parse_srt(SIMPLE_SRT)
    assert len(cues) == 2
    assert cues[0].start == 1.0
    assert cues[0].end == 4.0
    assert cues[0].text == "First line."
    assert cues[1].text == "Second line with a break."


def test_build_transcript_assigns_sequential_ids_and_full_text():
    cues = parse_srt(SIMPLE_SRT)
    transcript = build_transcript(cues, "en", TranscriptSource.EXTERNAL_SUBTITLE)

    assert transcript.language == "en"
    assert transcript.source is TranscriptSource.EXTERNAL_SUBTITLE
    assert [s.id for s in transcript.segments] == ["seg-0000", "seg-0001"]
    assert transcript.full_text == "First line. Second line with a break."


def test_parse_vtt_with_no_cues_returns_empty_list():
    assert parse_vtt("WEBVTT\n\n") == []

# vidcontext

Real transcription and real screenshot extraction from YouTube videos or
local video/audio files — built to be used **by an AI agent**, not to
replace one.

`vidcontext` calls no AI API itself. It does the mechanical, deterministic
work:

- **Transcript**: real subtitles when available (YouTube manual → YouTube
  auto-generated → `youtube-transcript-api`), falling back to real local
  ASR (`faster-whisper`) when there's no subtitle at all.
- **Screenshots**: real frame extraction via `ffmpeg` at timestamps you
  give it, with real quality filtering (drops black frames, ranks by
  sharpness, deduplicates near-identical frames via a perceptual hash).

Deciding what a video is *about*, which moments matter, and what to write
in a summary is the job of whoever consumes `vidcontext`'s output —
typically an AI coding agent (Claude Code, Codex, etc.) that reads the
transcript, picks the interesting timestamps, asks `vidcontext` for
screenshots at exactly those timestamps, and writes its own report.

## Why not just call an AI API from inside the tool?

Because the agent invoking this tool is *already* an LLM. Piping the
transcript through a second, separate AI API call to "summarize it" would
be redundant, opaque, and would need its own API key. Instead,
`vidcontext` hands the agent clean, structured ground truth
(`transcript.json` / `transcript.md`, real screenshots with real
timestamps) and lets the agent's own reasoning do the analysis — fully
inside the conversation the user is already having with it.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

Requirements:

- Python 3.12+
- `ffmpeg` / `ffprobe` on PATH (`brew install ffmpeg` on macOS)

## Usage

```bash
# Real metadata + real subtitle/ASR transcript
vidcontext transcript "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
vidcontext transcript ./my-video.mp4

# Real local ASR (faster-whisper) instead of the default mock transcriber
vidcontext transcript ./my-video.mp4 --transcriber base

# Real screenshots at chosen timestamps (12.5s) or intervals (40s-55s)
vidcontext screenshots ./my-video.mp4 --at 12.5 --at 40-55

# Force every provider to mock (100% offline, no ffmpeg/yt-dlp/network needed)
vidcontext transcript tests/fixtures/sample-audio.wav --use-mocks

# List available providers/backends
vidcontext providers

# Remove a run's artifacts
vidcontext clean runs/<source-id> --yes
```

Each run creates `runs/<source-id>/` with a `manifest.json` tracking
completed stages, `metadata.json`, and:

- `transcript/transcript.json`, `transcript/transcript.txt`,
  `transcript/transcript.md` (the file meant for an agent to read)
- `frames/candidates/`, `frames/selected/`, `frames/moments.json` (after
  running `screenshots`)

Re-running `transcript` on the same source reuses completed stages; pass
`--force` to ignore the cache.

## Using it as a Claude Code plugin / skill

This repo is also a Claude Code plugin (`.claude-plugin/plugin.json`) with
a skill at `skills/vidcontext/SKILL.md` that teaches an agent exactly how
and when to call `vidcontext transcript` and `vidcontext screenshots`. Any
other coding agent (Codex, etc.) can follow the same workflow described in
[`AGENTS.md`](AGENTS.md).

## Configuration

Precedence: CLI flags > environment variables (`VIDCONTEXT_*`) > config
file (`--config path.toml`) > defaults.

```text
VIDCONTEXT_RUNS_DIR
VIDCONTEXT_FFMPEG_PATH
VIDCONTEXT_FFPROBE_PATH
VIDCONTEXT_TRANSCRIPTION_LANGUAGE
VIDCONTEXT_TRANSCRIBER              mock | tiny | base | small | medium | ...
VIDCONTEXT_MAX_DURATION_SECONDS     default: 14400 (4h)
VIDCONTEXT_MAX_FILE_SIZE_BYTES      default: 2147483648 (2GiB)
VIDCONTEXT_VERBOSE
```

## Development

```bash
ruff check src tests
mypy
pytest
```

CI (`.github/workflows/ci.yml`) runs lint, typecheck, and tests on every
push. The automated test suite never touches the real network (YouTube is
always replaced by a double) and never downloads an ASR model — those are
verified manually.

## License

MIT — see [LICENSE](LICENSE).

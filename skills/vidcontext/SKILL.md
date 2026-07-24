---
name: vidcontext
description: Use when the user wants to understand, summarize, or extract information from a YouTube video or a local video/audio file - get a real transcript and real screenshots to reason over yourself. Also use when the user wants a written report about a video's content.
version: 0.1.0
---

# vidcontext

`vidcontext` is a CLI that does two mechanical things for you, with real
tools (ffmpeg, yt-dlp, faster-whisper) - it calls no AI API itself:

1. **Get a real transcript** of a video (YouTube subtitles or local ASR).
2. **Extract real screenshots** at timestamps you choose.

You are the one who reads the transcript, decides what matters, and
writes any summary or report. `vidcontext` never summarizes anything for
you.

## Workflow

1. **Get the transcript first, always.**

   ```bash
   vidcontext transcript "<youtube-url-or-local-file>"
   ```

   This prints the path to `transcript.md` (e.g.
   `runs/<source-id>/transcript/transcript.md`). Read that file. It
   contains the full transcript with timestamps (clickable YouTube links
   when the source is YouTube) and basic metadata (title, author,
   duration).

   - For a local video/audio file with no useful transcription backend
     configured, pass `--transcriber base` (or `tiny`/`small`/`medium`) to
     run real local speech recognition instead of a placeholder. The
     first run downloads the model; subsequent runs reuse it.
   - Re-running `transcript` on the same source is cheap - completed
     stages are cached in `runs/<source-id>/manifest.json`. Use `--force`
     to bypass the cache.

2. **Decide what's interesting, yourself.**

   After reading the transcript, pick the timestamps (or short intervals)
   that would benefit from a screenshot - a slide, a diagram, a code
   sample on screen, a demonstrated UI action, a chart. You choose these;
   the tool has no opinion about them.

3. **Ask for screenshots at those exact moments.**

   ```bash
   vidcontext screenshots "<same-source>" --at 125.0 --at 340-360
   ```

   - `--at TIMESTAMP` (e.g. `125.0`) captures a single point in time.
   - `--at START-END` (e.g. `340-360`) samples across an interval and
     keeps the sharpest, non-duplicate frame(s).
   - Repeat `--at` for as many moments as you need in one call.
   - This only works when the source has video (an audio-only file will
     raise a clear error).

   The command prints where the selected images live
   (`runs/<source-id>/frames/selected/`) and a `moments.json` file mapping
   each moment back to its image path(s) and quality scores.

4. **Write the report yourself.**

   Combine the transcript excerpts and the screenshot paths into whatever
   the user asked for - a summary, a how-to guide, a set of highlights
   with embedded images, a Q&A. This is your job, not `vidcontext`'s.

## Notes

- `--use-mocks` forces every provider to a fake, offline mode - useful
  only for testing `vidcontext` itself, never for a real user request.
- If a run's artifacts are no longer needed, `vidcontext clean
  runs/<source-id> --yes` removes them.
- `vidcontext providers` lists the available transcriber backends.
- Everything lives under `runs/<source-id>/` by default (override with
  `--output-dir`), where `<source-id>` is derived from the YouTube video
  id or a content hash of the local file.

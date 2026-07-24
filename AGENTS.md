# Agent instructions for vidcontext

This repo ships `vidcontext`, a CLI that gives an AI agent a real
transcript and real screenshots from a video - it never calls an AI API
itself. If you are an AI coding agent working in a project that uses
`vidcontext` (or asked to analyze a video), follow this workflow.

## Workflow

1. **Get the transcript:**

   ```bash
   vidcontext transcript "<youtube-url-or-local-file>"
   ```

   Read the printed `transcript.md` path. It has the full transcript with
   timestamps. For local files without a real transcription backend
   configured, add `--transcriber base` to run real speech recognition
   (faster-whisper) instead of a placeholder.

2. **Decide what matters yourself** - `vidcontext` has no opinion on
   this. Pick timestamps or short intervals worth a screenshot (a slide,
   a diagram, an on-screen action).

3. **Get screenshots at those moments:**

   ```bash
   vidcontext screenshots "<same-source>" --at 125.0 --at 340-360
   ```

   `--at TIMESTAMP` for a single point, `--at START-END` for an interval.
   Repeat `--at` for multiple moments in one call. Requires a source with
   video.

4. **Write the summary/report yourself**, combining transcript text and
   screenshot file paths as needed. This tool never summarizes - you do.

## Reference

- `vidcontext providers` — lists available transcriber backends.
- `vidcontext clean runs/<source-id> --yes` — removes a run's artifacts.
- `--use-mocks` — forces an offline/fake run; only for testing this tool
  itself, not for real analysis requests.
- Artifacts live under `runs/<source-id>/` (override with `--output-dir`).

See [README.md](README.md) for installation and configuration details.

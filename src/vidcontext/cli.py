"""CLI (Typer).

Two mechanical tools, meant to be called by an AI agent (or a person) -
neither calls any AI API:

  vidcontext transcript <source>
  vidcontext screenshots <source> --at 12.5 --at 340-360
"""

from __future__ import annotations

import shutil
from pathlib import Path

import typer
from rich.console import Console

from vidcontext.config import AppConfig, load_config
from vidcontext.exceptions import VidContextError
from vidcontext.inputs.resolver import DefaultInputResolver
from vidcontext.logging import StageLogger
from vidcontext.media.dispatch import CompositeMediaProvider
from vidcontext.media.local import LocalFileMediaProvider
from vidcontext.media.youtube import YouTubeMediaProvider
from vidcontext.mocks import MockMediaProvider, MockTranscriber
from vidcontext.models import Moment
from vidcontext.pipeline import Providers, VidContext
from vidcontext.transcription.base import Transcriber
from vidcontext.transcription.faster_whisper import FasterWhisperTranscriber
from vidcontext.visual.frame_extractor import FfmpegFrameExtractor

app = typer.Typer(add_completion=False, help="Real video transcription and screenshots.")
console = Console()


@app.callback()
def _main() -> None:
    """Real video transcription and screenshots, for use by an AI agent.

    This tool calls no AI API. It only does the mechanical work: get the
    transcript (real subtitle or local ASR) and extract real screenshots
    via ffmpeg. Summarizing the content and deciding which moments deserve
    a screenshot is the job of whoever consumes this tool.
    """


def _build_providers(config: AppConfig) -> Providers:
    if config.use_mocks:
        return Providers(
            resolver=DefaultInputResolver(),
            media_provider=MockMediaProvider(),
            transcriber=MockTranscriber(),
            frame_extractor=FfmpegFrameExtractor(),
        )

    media_provider = CompositeMediaProvider(
        youtube=YouTubeMediaProvider(), local=LocalFileMediaProvider()
    )
    transcriber: Transcriber
    if config.transcriber == "mock":
        transcriber = MockTranscriber()
    else:
        # any other value is treated as a faster-whisper model_size
        # (e.g. tiny, base, small, medium, large-v3).
        transcriber = FasterWhisperTranscriber(model_size=config.transcriber)

    return Providers(
        resolver=DefaultInputResolver(),
        media_provider=media_provider,
        transcriber=transcriber,
        frame_extractor=FfmpegFrameExtractor(),
    )


def _parse_moment(raw: str, index: int) -> Moment:
    raw = raw.strip()
    try:
        if "-" in raw:
            start_str, _, end_str = raw.partition("-")
            start, end = float(start_str), float(end_str)
        else:
            start = end = float(raw)
    except ValueError as exc:
        raise typer.BadParameter(
            f"invalid moment: {raw!r} (use a timestamp like 12.5 or an interval like 40-55)"
        ) from exc
    if end < start:
        raise typer.BadParameter(f"invalid interval (end < start): {raw!r}")
    return Moment(
        id=f"moment-{index:04d}", start=start, end=end, representative_time=(start + end) / 2
    )


@app.command()
def transcript(
    source: str = typer.Argument(
        ..., help="YouTube URL, local video file, or local audio file."
    ),
    output_dir: Path = typer.Option(
        Path("runs"), "--output-dir", help="Root directory for runs."
    ),
    config_file: Path | None = typer.Option(
        None, "--config", help="Configuration file (TOML)."
    ),
    transcription_language: str = typer.Option("auto", "--transcription-language"),
    transcriber: str = typer.Option(
        "mock", "--transcriber", help="'mock' or a faster-whisper model_size (e.g. base)."
    ),
    force: bool = typer.Option(
        False, "--force", help="Ignore the cache and re-run every stage."
    ),
    resume: bool = typer.Option(True, "--resume/--no-resume"),
    verbose: bool = typer.Option(
        False, "--verbose", help="Show a full traceback on error."
    ),
    use_mocks: bool = typer.Option(
        False, "--use-mocks", help="Force all providers to mock (100% offline run)."
    ),
) -> None:
    """Get the real transcript (subtitle or local ASR) for a source."""
    config = load_config(
        config_file=config_file,
        cli_overrides={
            "runs_dir": output_dir,
            "transcription_language": transcription_language,
            "transcriber": transcriber,
            "force": force or not resume,
            "resume": resume,
            "verbose": verbose,
            "use_mocks": use_mocks,
        },
    )

    logger = StageLogger(verbose=config.verbose, console=console)
    tool = VidContext(config=config, providers=_build_providers(config), logger=logger)

    try:
        result = tool.run_transcript(source)
    except VidContextError as exc:
        logger.error(str(exc))
        if config.verbose:
            raise
        raise typer.Exit(code=1) from None

    console.print(f"[bold green]Done.[/bold green] Transcript at {result.transcript_md_path}")


@app.command()
def screenshots(
    source: str = typer.Argument(
        ..., help="YouTube URL or local video file (must have video)."
    ),
    at: list[str] = typer.Option(
        ...,
        "--at",
        help="Timestamp (12.5) or interval (40-55) in seconds. Repeat for multiple moments.",
    ),
    output_dir: Path = typer.Option(
        Path("runs"), "--output-dir", help="Root directory for runs."
    ),
    config_file: Path | None = typer.Option(
        None, "--config", help="Configuration file (TOML)."
    ),
    force: bool = typer.Option(
        False, "--force", help="Ignore the metadata cache and re-run."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Show a full traceback on error."
    ),
    use_mocks: bool = typer.Option(
        False, "--use-mocks", help="Force all providers to mock (100% offline run)."
    ),
) -> None:
    """Extract real screenshots at the given moments (chosen by the caller)."""
    config = load_config(
        config_file=config_file,
        cli_overrides={
            "runs_dir": output_dir,
            "force": force,
            "verbose": verbose,
            "use_mocks": use_mocks,
        },
    )

    moments = [_parse_moment(raw, idx) for idx, raw in enumerate(at)]

    logger = StageLogger(verbose=config.verbose, console=console)
    tool = VidContext(config=config, providers=_build_providers(config), logger=logger)

    try:
        result = tool.run_screenshots(source, moments)
    except VidContextError as exc:
        logger.error(str(exc))
        if config.verbose:
            raise
        raise typer.Exit(code=1) from None

    total_frames = sum(len(frames) for frames in result.frames_by_moment.values())
    console.print(
        f"[bold green]Done.[/bold green] {total_frames} screenshot(s) in "
        f"{result.workspace.frame_selected_dir}. Details at {result.moments_json_path}"
    )


@app.command()
def clean(
    run_dir: Path = typer.Argument(..., help="A run directory (runs/<source-id>)."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Don't ask for confirmation."),
) -> None:
    """Remove the artifacts of a run (runs/<source-id>/)."""
    if not run_dir.exists():
        console.print(f"[bold red]error:[/bold red] {run_dir} does not exist.")
        raise typer.Exit(code=1)
    if not (run_dir / "manifest.json").exists():
        console.print(
            f"[bold red]error:[/bold red] {run_dir} does not look like a run directory "
            "(manifest.json not found)."
        )
        raise typer.Exit(code=1)

    if not yes and not typer.confirm(f"Permanently remove {run_dir}?"):
        console.print("Cancelled.")
        raise typer.Exit(code=0)

    shutil.rmtree(run_dir)
    console.print(f"[bold green]Removed:[/bold green] {run_dir}")


@app.command()
def providers() -> None:
    """List the available providers/backends."""
    lines = [
        "[bold]media_provider[/bold]: always real (YouTube via yt-dlp / local ffprobe)",
        "[bold]--transcriber[/bold]: mock | faster-whisper model_size (e.g. tiny, base, small)",
        "[bold]--use-mocks[/bold]: forces every provider to mock (100% offline)",
    ]
    for line in lines:
        console.print(line)


if __name__ == "__main__":
    app()

"""Progress logging.

Each line identifies a stage and its status (e.g. "[metadata] completed").
Never logs API keys, tokens, or full sensitive content.
"""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape


class StageLogger:
    def __init__(self, verbose: bool = False, console: Console | None = None) -> None:
        self.verbose = verbose
        self.console = console or Console()

    def stage(self, name: str, message: str) -> None:
        bracketed = escape(f"[{name}]")
        self.console.print(f"[bold cyan]{bracketed}[/bold cyan] {escape(message)}")

    def stage_start(self, name: str) -> None:
        self.stage(name, "running")

    def stage_cached(self, name: str, artifact: str) -> None:
        self.stage(name, f"cached ({artifact})")

    def stage_completed(
        self, name: str, artifact: str | None = None, duration_seconds: float | None = None
    ) -> None:
        suffix = ""
        if artifact:
            suffix += f" -> {artifact}"
        if duration_seconds is not None:
            suffix += f" ({duration_seconds:.1f}s)"
        self.stage(name, f"completed{suffix}")

    def stage_skipped(self, name: str, reason: str) -> None:
        self.stage(name, f"skipped ({reason})")

    def stage_fallback(self, name: str, message: str) -> None:
        self.stage(name, message)

    def stage_failed(self, name: str, error: str) -> None:
        bracketed = escape(f"[{name}]")
        self.console.print(f"[bold red]{bracketed}[/bold red] failed: {escape(error)}")

    def error(self, message: str) -> None:
        self.console.print(f"[bold red]error:[/bold red] {escape(message)}")

"""
CLI Progress Adapter

Provides progress reporting for command-line interfaces using rich
or basic print statements as fallback.
"""

import sys
from typing import Optional

try:
    from rich.console import Console
    from rich.progress import (
        Progress, TaskID, TextColumn, BarColumn, PercentageColumn,
        TimeElapsedColumn, TimeRemainingColumn
    )
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    # Create dummy classes to avoid NameError
    Console = None
    TaskID = None

from ...core.domain import ProgressUpdate


class CLIProgressAdapter:
    """CLI progress reporting using rich library when available"""

    def __init__(self, use_rich: bool = True, console: Optional[Console] = None):
        self.use_rich = use_rich and RICH_AVAILABLE
        self.console = console or Console() if self.use_rich else None
        self.progress_context = None
        self.current_task: Optional[TaskID] = None
        self.total_steps = 1
        self.current_step = 0

        if self.use_rich:
            self.progress = Progress(
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                PercentageColumn(),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=self.console
            )
        else:
            self.progress = None

    def __enter__(self):
        """Context manager entry"""
        if self.use_rich and self.progress:
            self.progress_context = self.progress
            self.progress_context.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.progress_context:
            self.progress_context.__exit__(exc_type, exc_val, exc_tb)
            self.progress_context = None

    def update_progress(self, percent: int, message: str) -> None:
        """Update progress with percentage and message"""
        if self.use_rich and self.progress:
            if self.current_task is None:
                self.current_task = self.progress.add_task(message, total=100)

            self.progress.update(self.current_task, completed=percent, description=message)
        else:
            # Fallback to simple print statements
            print(f"\r[{percent:3d}%] {message}", end="", flush=True)
            if percent == 100:
                print()  # New line when complete

    def set_total_steps(self, total: int) -> None:
        """Set the total number of steps for the operation"""
        self.total_steps = max(total, 1)
        self.current_step = 0

    def increment_step(self, message: str) -> None:
        """Increment to the next step with a message"""
        self.current_step += 1
        percent = int((self.current_step / self.total_steps) * 100)
        self.update_progress(percent, message)

    def report_progress(self, progress: ProgressUpdate) -> None:
        """Report detailed progress information"""
        self.update_progress(progress.percent, progress.message)

    def is_progress_enabled(self) -> bool:
        """Check if progress reporting is enabled"""
        return True

    def start(self, description: str = "Processing...") -> None:
        """Start progress reporting"""
        if self.use_rich and self.progress:
            self.current_task = self.progress.add_task(description, total=100)
        else:
            print(f"Starting: {description}")

    def finish(self, message: str = "Complete") -> None:
        """Finish progress reporting"""
        if self.use_rich and self.progress and self.current_task:
            self.progress.update(self.current_task, completed=100, description=message)
        else:
            print(f"\r[100%] {message}")


class SimpleCLIProgressAdapter:
    """Simple CLI progress adapter without external dependencies"""

    def __init__(self, show_spinner: bool = True):
        self.show_spinner = show_spinner
        self.total_steps = 1
        self.current_step = 0
        self.last_percent = -1

    def update_progress(self, percent: int, message: str) -> None:
        """Update progress with percentage and message"""
        # Only print if percent has changed to reduce output noise
        if percent != self.last_percent:
            print(f"[{percent:3d}%] {message}")
            self.last_percent = percent

    def set_total_steps(self, total: int) -> None:
        """Set the total number of steps"""
        self.total_steps = max(total, 1)
        self.current_step = 0

    def increment_step(self, message: str) -> None:
        """Increment step and show progress"""
        self.current_step += 1
        percent = int((self.current_step / self.total_steps) * 100)
        print(f"Step {self.current_step}/{self.total_steps}: {message}")
        self.update_progress(percent, message)

    def report_progress(self, progress: ProgressUpdate) -> None:
        """Report detailed progress information"""
        self.update_progress(progress.percent, progress.message)

    def is_progress_enabled(self) -> bool:
        """Check if progress reporting is enabled"""
        return True


class SilentProgressAdapter:
    """Silent progress adapter that does nothing"""

    def update_progress(self, percent: int, message: str) -> None:
        """Silent - do nothing"""
        pass

    def set_total_steps(self, total: int) -> None:
        """Silent - do nothing"""
        pass

    def increment_step(self, message: str) -> None:
        """Silent - do nothing"""
        pass

    def report_progress(self, progress: ProgressUpdate) -> None:
        """Silent - do nothing"""
        pass

    def is_progress_enabled(self) -> bool:
        """Progress reporting is disabled"""
        return False


def create_cli_progress_adapter(
    progress_type: str = "auto",
    **kwargs
):
    """
    Factory function to create appropriate CLI progress adapter.

    Args:
        progress_type: Type of progress adapter ("rich", "simple", "silent", "auto")
        **kwargs: Additional arguments for the adapter

    Returns:
        Configured progress adapter
    """
    if progress_type == "auto":
        # Auto-detect best available option
        if RICH_AVAILABLE and sys.stdout.isatty() and kwargs.get('use_rich', True):
            rich_kwargs = {k: v for k, v in kwargs.items() if k in ['use_rich', 'console']}
            return CLIProgressAdapter(**rich_kwargs)
        elif sys.stdout.isatty():
            simple_kwargs = {k: v for k, v in kwargs.items() if k in ['show_spinner']}
            return SimpleCLIProgressAdapter(**simple_kwargs)
        else:
            return SilentProgressAdapter()

    elif progress_type == "rich":
        if not RICH_AVAILABLE:
            raise ImportError("Rich library not available. Install with: pip install rich")
        rich_kwargs = {k: v for k, v in kwargs.items() if k in ['use_rich', 'console']}
        return CLIProgressAdapter(**rich_kwargs)

    elif progress_type == "simple":
        # Filter out kwargs that SimpleCLIProgressAdapter doesn't accept
        simple_kwargs = {k: v for k, v in kwargs.items() if k in ['show_spinner']}
        return SimpleCLIProgressAdapter(**simple_kwargs)

    elif progress_type == "silent":
        return SilentProgressAdapter()

    else:
        raise ValueError(f"Unknown progress type: {progress_type}")
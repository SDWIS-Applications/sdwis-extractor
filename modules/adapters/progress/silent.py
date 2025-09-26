"""
Silent Progress Adapter

No-op progress adapter for batch jobs or situations where
progress reporting is not desired.
"""

from ...core.domain import ProgressUpdate


class SilentProgressAdapter:
    """Silent progress adapter that performs no operations"""

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
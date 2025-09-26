"""
Streamlit Progress Adapter

Provides progress reporting for Streamlit applications using
Streamlit's built-in progress components.
"""

from typing import Optional, Any
from ...core.domain import ProgressUpdate


class StreamlitProgressAdapter:
    """Streamlit progress integration"""

    def __init__(
        self,
        progress_bar: Any,
        status_text: Optional[Any] = None,
        use_spinner: bool = True
    ):
        """
        Initialize Streamlit progress adapter.

        Args:
            progress_bar: Streamlit progress bar component (st.progress)
            status_text: Optional Streamlit text component for status messages
            use_spinner: Whether to show spinner for indeterminate operations
        """
        self.progress_bar = progress_bar
        self.status_text = status_text
        self.use_spinner = use_spinner
        self.total_steps = 1
        self.current_step = 0
        self.spinner_context = None

    def update_progress(self, percent: int, message: str) -> None:
        """Update progress bar and status message"""
        # Update progress bar (Streamlit expects 0.0 to 1.0)
        self.progress_bar.progress(percent / 100.0, text=message)

        # Update status text if available
        if self.status_text:
            self.status_text.text(message)

    def set_total_steps(self, total: int) -> None:
        """Set the total number of steps"""
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

        # Add metadata to status text if available
        if self.status_text and progress.metadata:
            metadata_info = []
            if 'records_processed' in progress.metadata:
                metadata_info.append(f"Records: {progress.metadata['records_processed']}")
            if 'batch' in progress.metadata:
                metadata_info.append(f"Batch: {progress.metadata['batch']}")

            if metadata_info:
                extended_message = f"{progress.message} ({', '.join(metadata_info)})"
                self.status_text.text(extended_message)

    def is_progress_enabled(self) -> bool:
        """Check if progress reporting is enabled"""
        return True

    def start_spinner(self, message: str = "Processing...") -> Any:
        """Start a Streamlit spinner for indeterminate operations"""
        if self.use_spinner:
            # Import streamlit here to avoid dependency issues
            try:
                import streamlit as st
                self.spinner_context = st.spinner(message)
                return self.spinner_context.__enter__()
            except ImportError:
                # Fallback if streamlit not available
                pass
        return None

    def stop_spinner(self) -> None:
        """Stop the current spinner"""
        if self.spinner_context:
            self.spinner_context.__exit__(None, None, None)
            self.spinner_context = None


class StreamlitMultiProgressAdapter:
    """Multiple progress bars for complex operations"""

    def __init__(self):
        self.progress_bars = {}
        self.status_containers = {}

    def add_progress_bar(self, key: str, progress_bar: Any, status_text: Optional[Any] = None):
        """Add a progress bar for a specific operation"""
        self.progress_bars[key] = StreamlitProgressAdapter(progress_bar, status_text)

    def get_progress_adapter(self, key: str) -> Optional[StreamlitProgressAdapter]:
        """Get progress adapter for a specific operation"""
        return self.progress_bars.get(key)

    def update_progress(self, percent: int, message: str, key: str = "default") -> None:
        """Update progress for a specific operation"""
        adapter = self.progress_bars.get(key)
        if adapter:
            adapter.update_progress(percent, message)

    def set_total_steps(self, total: int, key: str = "default") -> None:
        """Set total steps for a specific operation"""
        adapter = self.progress_bars.get(key)
        if adapter:
            adapter.set_total_steps(total)

    def increment_step(self, message: str, key: str = "default") -> None:
        """Increment step for a specific operation"""
        adapter = self.progress_bars.get(key)
        if adapter:
            adapter.increment_step(message)

    def report_progress(self, progress: ProgressUpdate, key: str = "default") -> None:
        """Report progress for a specific operation"""
        adapter = self.progress_bars.get(key)
        if adapter:
            adapter.report_progress(progress)

    def is_progress_enabled(self) -> bool:
        """Check if progress reporting is enabled"""
        return len(self.progress_bars) > 0


class StreamlitStatusAdapter:
    """Streamlit status updates without progress bars"""

    def __init__(self, status_container: Any):
        """
        Initialize with Streamlit status container.

        Args:
            status_container: Streamlit container for status messages (st.empty, st.container, etc.)
        """
        self.status_container = status_container
        self.total_steps = 1
        self.current_step = 0

    def update_progress(self, percent: int, message: str) -> None:
        """Update status message with progress"""
        status_text = f"[{percent:3d}%] {message}"
        self.status_container.text(status_text)

    def set_total_steps(self, total: int) -> None:
        """Set total steps"""
        self.total_steps = max(total, 1)
        self.current_step = 0

    def increment_step(self, message: str) -> None:
        """Increment step and update status"""
        self.current_step += 1
        percent = int((self.current_step / self.total_steps) * 100)
        step_message = f"Step {self.current_step}/{self.total_steps}: {message}"
        self.update_progress(percent, step_message)

    def report_progress(self, progress: ProgressUpdate) -> None:
        """Report detailed progress"""
        self.update_progress(progress.percent, progress.message)

    def is_progress_enabled(self) -> bool:
        """Progress reporting is enabled"""
        return True


def create_streamlit_progress_adapter(
    progress_bar: Any,
    status_text: Optional[Any] = None,
    adapter_type: str = "standard"
) -> StreamlitProgressAdapter:
    """
    Factory function to create Streamlit progress adapter.

    Args:
        progress_bar: Streamlit progress component
        status_text: Optional status text component
        adapter_type: Type of adapter to create

    Returns:
        Configured Streamlit progress adapter
    """
    if adapter_type == "standard":
        return StreamlitProgressAdapter(progress_bar, status_text)
    elif adapter_type == "status_only":
        return StreamlitStatusAdapter(progress_bar)
    else:
        raise ValueError(f"Unknown adapter type: {adapter_type}")
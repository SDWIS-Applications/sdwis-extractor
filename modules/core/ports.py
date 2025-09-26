"""
Port interfaces for SDWIS data extraction.

These interfaces define the contracts between the domain layer and infrastructure.
They enable dependency inversion and allow for easy testing with mock implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol

from .domain import ExtractionQuery, ExtractionResult, ProgressUpdate

# Import playwright types for browser session
try:
    from playwright.async_api import Page, BrowserContext
except ImportError:
    # For environments without playwright installed
    Page = Any
    BrowserContext = Any


class AuthenticationValidationPort(Protocol):
    """Port for HTTP-only authentication validation - fast credential checking"""

    async def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """
        Validate credentials using HTTP-only requests (no browser).

        Args:
            credentials: Dictionary containing username, password

        Returns:
            True if credentials are valid, False otherwise

        Raises:
            AuthenticationError: If validation fails due to technical issues
        """
        ...

    async def check_connectivity(self) -> bool:
        """
        Check connectivity to SDWIS server.

        Returns:
            True if server is reachable, False otherwise
        """
        ...


class AuthenticatedBrowserSessionPort(Protocol):
    """Port for authenticated browser sessions that can be shared across adapters"""

    async def authenticate(self, credentials: Dict[str, str], browser_config: Optional[Dict[str, Any]] = None) -> 'AuthenticatedBrowserSessionPort':
        """
        Authenticate and return authenticated session.

        Args:
            credentials: Dictionary containing username, password
            browser_config: Optional browser configuration (headless, timeout, etc.)

        Returns:
            Self after successful authentication

        Raises:
            AuthenticationError: If authentication fails
        """
        ...

    async def get_page(self) -> Page:
        """
        Get authenticated browser page.

        Returns:
            Authenticated Playwright page

        Raises:
            AuthenticationError: If not authenticated or session invalid
        """
        ...

    async def get_context(self) -> BrowserContext:
        """
        Get authenticated browser context.

        Returns:
            Authenticated browser context

        Raises:
            AuthenticationError: If not authenticated or session invalid
        """
        ...

    def is_authenticated(self) -> bool:
        """
        Check if session is authenticated and valid.

        Returns:
            True if authenticated and session valid, False otherwise
        """
        ...

    async def close(self) -> None:
        """
        Close browser session and clean up resources.
        """
        ...


class ExtractionPort(Protocol):
    """Port for data extraction operations"""

    async def extract_data(self, query: ExtractionQuery, browser_session: AuthenticatedBrowserSessionPort) -> ExtractionResult:
        """
        Extract data based on the provided query using an authenticated browser session.

        Args:
            query: ExtractionQuery containing data type, filters, and pagination config
            browser_session: Authenticated browser session to use for extraction

        Returns:
            ExtractionResult with success status, data, metadata, and any errors

        Raises:
            ExtractionError: If extraction fails due to technical issues
            AuthenticationError: If browser session is not authenticated
        """
        ...

    async def validate_query(self, query: ExtractionQuery) -> bool:
        """
        Validate that a query can be executed by this extractor.

        Args:
            query: ExtractionQuery to validate

        Returns:
            True if query is valid and can be executed, False otherwise
        """
        ...

    def get_supported_data_types(self) -> List[str]:
        """
        Get list of data types supported by this extractor.

        Returns:
            List of supported data type strings
        """
        ...




class ProgressReportingPort(Protocol):
    """Port for progress updates"""

    def update_progress(self, percent: int, message: str) -> None:
        """
        Update progress with percentage and message.

        Args:
            percent: Progress percentage (0-100)
            message: Human-readable progress message
        """
        ...

    def set_total_steps(self, total: int) -> None:
        """
        Set the total number of steps for the operation.

        Args:
            total: Total number of steps
        """
        ...

    def increment_step(self, message: str) -> None:
        """
        Increment to the next step with a message.

        Args:
            message: Message describing the current step
        """
        ...

    def report_progress(self, progress: ProgressUpdate) -> None:
        """
        Report detailed progress information.

        Args:
            progress: ProgressUpdate with detailed information
        """
        ...

    def is_progress_enabled(self) -> bool:
        """
        Check if progress reporting is enabled.

        Returns:
            True if progress reporting is enabled, False otherwise
        """
        ...


class OutputPort(Protocol):
    """Port for data output operations"""

    async def save_data(self, result: ExtractionResult, destination: str) -> bool:
        """
        Save extraction result to specified destination.

        Args:
            result: ExtractionResult to save
            destination: Output destination (file path, URL, etc.)

        Returns:
            True if save successful, False otherwise

        Raises:
            OutputError: If save operation fails
        """
        ...

    def get_supported_formats(self) -> List[str]:
        """
        Get list of supported output formats.

        Returns:
            List of supported format strings (e.g., ["json", "csv"])
        """
        ...

    def validate_destination(self, destination: str, format_type: str) -> bool:
        """
        Validate that a destination is valid for the specified format.

        Args:
            destination: Output destination to validate
            format_type: Output format type

        Returns:
            True if destination is valid, False otherwise
        """
        ...


class ConfigurationPort(Protocol):
    """Port for configuration management"""

    def get_credentials(self) -> Dict[str, str]:
        """
        Get authentication credentials from configuration.

        Returns:
            Dictionary containing credentials (never returns actual passwords in logs)

        Raises:
            ConfigurationError: If credentials are not available or invalid
        """
        ...

    def get_server_config(self) -> Dict[str, str]:
        """
        Get server configuration settings.

        Returns:
            Dictionary containing server configuration (URLs, timeouts, etc.)
        """
        ...

    def get_extraction_config(self) -> Dict[str, Any]:
        """
        Get extraction-specific configuration.

        Returns:
            Dictionary containing extraction settings (batch sizes, timeouts, etc.)
        """
        ...

    def get_browser_config(self) -> Dict[str, Any]:
        """
        Get browser-specific configuration.

        Returns:
            Dictionary containing browser settings (headless mode, timeouts, etc.)
        """
        ...

    def validate_config(self) -> bool:
        """
        Validate that current configuration is complete and valid.

        Returns:
            True if configuration is valid, False otherwise
        """
        ...


# Exception classes for ports
class ExtractionError(Exception):
    """Raised when data extraction fails"""
    pass


class AuthenticationError(Exception):
    """Raised when authentication fails"""
    pass


class OutputError(Exception):
    """Raised when output operation fails"""
    pass


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing"""
    pass


class BrowserSessionError(Exception):
    """Raised when browser session operations fail"""
    pass
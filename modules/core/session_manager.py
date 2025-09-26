"""
Browser session context manager for SDWIS extractions.

Provides a context manager that handles the complete lifecycle of an authenticated
browser session, with optional reset capabilities between operations.
"""

from typing import Optional, Dict, Any, AsyncContextManager
from contextlib import asynccontextmanager

from .ports import AuthenticatedBrowserSessionPort, ConfigurationPort
from .ports import AuthenticationError, BrowserSessionError


class BrowserSessionManager:
    """
    Context manager for SDWIS browser sessions.

    Handles authentication, session lifecycle, and optional reset operations
    between different extractions (similar to database transaction commit/rollback).
    """

    def __init__(
        self,
        browser_session_factory: callable,
        config: ConfigurationPort,
        auto_reset: bool = False
    ):
        """
        Initialize session manager.

        Args:
            browser_session_factory: Factory function that creates browser sessions
            config: Configuration adapter for credentials
            auto_reset: Whether to automatically reset navigation between operations
        """
        self.browser_session_factory = browser_session_factory
        self.config = config
        self.auto_reset = auto_reset
        self._session: Optional[AuthenticatedBrowserSessionPort] = None

    async def __aenter__(self) -> AuthenticatedBrowserSessionPort:
        """
        Context manager entry - create and authenticate session.

        Returns:
            Authenticated browser session

        Raises:
            AuthenticationError: If authentication fails
        """
        if self._session and self._session.is_authenticated():
            return self._session

        try:
            credentials = self.config.get_credentials()
            self._session = self.browser_session_factory()
            authenticated_session = await self._session.authenticate(credentials)

            if not authenticated_session.is_authenticated():
                raise AuthenticationError("Authentication succeeded but session is invalid")

            return authenticated_session

        except Exception as e:
            # Clean up on failure
            if self._session:
                try:
                    await self._session.close()
                except Exception:
                    pass
                self._session = None

            if isinstance(e, AuthenticationError):
                raise
            raise AuthenticationError(f"Failed to create authenticated browser session: {e}")

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit - cleanup session regardless of what happened.

        Args:
            exc_type: Exception type (if any)
            exc_val: Exception value (if any)
            exc_tb: Exception traceback (if any)
        """
        if self._session:
            try:
                await self._session.close()
            except Exception:
                pass  # Ignore cleanup errors
            finally:
                self._session = None

    async def reset_navigation(self) -> None:
        """
        Reset navigation to neutral state (like database rollback).

        Useful between extractions that navigate to different modules
        to ensure clean starting state.

        Raises:
            BrowserSessionError: If reset fails
            AuthenticationError: If session is not authenticated
        """
        if not self._session or not self._session.is_authenticated():
            raise AuthenticationError("No authenticated session available for reset")

        try:
            # Use the browser session's reset method if available
            if hasattr(self._session, 'reset_to_home'):
                await self._session.reset_to_home()
            else:
                # Fallback: navigate to main page
                if hasattr(self._session, 'navigate_to_module'):
                    await self._session.navigate_to_module('ibsmain_tc.jsp')

        except Exception as e:
            raise BrowserSessionError(f"Failed to reset navigation: {e}")

    async def commit_operation(self) -> None:
        """
        Commit current operation (like database commit).

        In the browser context, this could mean:
        - Taking a screenshot for evidence
        - Saving current state
        - Performing auto-reset if configured
        """
        if self.auto_reset and self._session:
            try:
                await self.reset_navigation()
            except Exception:
                pass  # Don't fail commit on reset errors

    def get_session(self) -> Optional[AuthenticatedBrowserSessionPort]:
        """
        Get the current session (if authenticated).

        Returns:
            Current authenticated session or None
        """
        return self._session if self._session and self._session.is_authenticated() else None


@asynccontextmanager
async def managed_browser_session(
    browser_session_factory: callable,
    config: ConfigurationPort,
    auto_reset: bool = False
) -> AsyncContextManager[AuthenticatedBrowserSessionPort]:
    """
    Async context manager factory for browser sessions.

    Usage:
        async with managed_browser_session(factory, config) as session:
            # Use session for extractions
            result1 = await extractor1.extract_data(query1, session)
            # Session automatically cleaned up on exit

    Args:
        browser_session_factory: Factory function for browser sessions
        config: Configuration adapter
        auto_reset: Whether to auto-reset navigation between uses

    Yields:
        Authenticated browser session
    """
    manager = BrowserSessionManager(browser_session_factory, config, auto_reset)
    async with manager as session:
        yield session


class MultiExtractionSessionManager:
    """
    Context manager for multiple extractions with session reuse and reset capabilities.

    Provides transaction-like semantics where each extraction can be "committed"
    with optional navigation reset between operations.
    """

    def __init__(
        self,
        browser_session_factory: callable,
        config: ConfigurationPort,
        reset_between_extractions: bool = False
    ):
        self.session_manager = BrowserSessionManager(
            browser_session_factory,
            config,
            auto_reset=False  # Manual control
        )
        self.reset_between_extractions = reset_between_extractions
        self.extraction_count = 0

    async def __aenter__(self) -> 'MultiExtractionSessionManager':
        """Enter context - create authenticated session"""
        await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context - cleanup session"""
        await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    async def perform_extraction(self, extractor_func, *args, **kwargs):
        """
        Perform an extraction with automatic session management.

        Args:
            extractor_func: Async function that performs extraction
            *args, **kwargs: Arguments to pass to extractor function

        Returns:
            Result from extractor function
        """
        session = self.session_manager.get_session()
        if not session:
            raise AuthenticationError("No authenticated session available")

        # Reset navigation if configured and not first extraction
        if self.reset_between_extractions and self.extraction_count > 0:
            await self.session_manager.reset_navigation()

        try:
            # Perform extraction
            result = await extractor_func(session, *args, **kwargs)

            # Commit operation
            await self.session_manager.commit_operation()
            self.extraction_count += 1

            return result

        except Exception as e:
            # Could add rollback logic here if needed
            raise

    def get_session(self) -> Optional[AuthenticatedBrowserSessionPort]:
        """Get current authenticated session"""
        return self.session_manager.get_session()

    async def reset_navigation(self) -> None:
        """Manually reset navigation state"""
        await self.session_manager.reset_navigation()
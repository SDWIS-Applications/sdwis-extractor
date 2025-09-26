"""
Authenticated browser session adapter for SDWIS.

Implements the AuthenticatedBrowserSessionPort interface to provide
shared browser sessions across adapters.
"""

import os
from typing import Dict, Optional, Any
from dotenv import load_dotenv
from playwright.async_api import Page, BrowserContext, async_playwright

from ...core.ports import AuthenticatedBrowserSessionPort, AuthenticationError, BrowserSessionError

# Load environment variables
load_dotenv()


class SDWISAuthenticatedBrowserSession:
    """SDWIS implementation of authenticated browser session"""

    def __init__(self, base_url: str = None, headless: bool = True, timeout_ms: int = 10000):
        """
        Initialize browser session.

        Args:
            base_url: SDWIS server base URL
            headless: Whether to run browser in headless mode
            timeout_ms: Timeout for browser operations in milliseconds
        """
        self.base_url = base_url or os.getenv('SDWIS_URL', 'http://sdwis:8080/SDWIS/')
        if not self.base_url.endswith('/'):
            self.base_url += '/'

        self.login_url = f"{self.base_url}jsp/secure/"
        self.headless = headless
        self.timeout = timeout_ms

        # Browser state
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._authenticated = False

    async def authenticate(self, credentials: Dict[str, str], browser_config: Optional[Dict[str, Any]] = None) -> 'SDWISAuthenticatedBrowserSession':
        """
        Authenticate with SDWIS and return self.

        Args:
            credentials: Dictionary containing username, password
            browser_config: Optional browser configuration (headless, timeout, etc.)

        Returns:
            Self after successful authentication

        Raises:
            AuthenticationError: If authentication fails
        """
        if self._authenticated and self._page and not self._page.is_closed():
            return self

        username = credentials.get('username')
        password = credentials.get('password')

        if not username or not password:
            raise AuthenticationError("Username and password are required")

        # Apply browser configuration if provided
        if browser_config:
            if 'headless' in browser_config:
                self.headless = browser_config['headless']
            if 'timeout' in browser_config:
                self.timeout = browser_config['timeout']

        try:
            # Create browser if needed
            await self._ensure_browser()

            # Navigate to login page
            await self._page.goto(self.login_url)

            # Fill credentials
            await self._page.fill('input[name="j_username"]', username)
            await self._page.fill('input[name="j_password"]', password)

            # Submit login form
            await self._page.click('input[type="submit"]')

            # Wait for authentication
            await self._page.wait_for_load_state('networkidle')

            # Basic validation - just check we're not on error/login page
            current_url = self._page.url
            if any(indicator in current_url.lower() for indicator in ['error', 'fail']):
                raise AuthenticationError("Invalid credentials or login failed")

            self._authenticated = True
            return self

        except Exception as e:
            if isinstance(e, AuthenticationError):
                raise
            raise AuthenticationError(f"Browser authentication failed: {str(e)}")

    async def get_page(self) -> Page:
        """
        Get authenticated browser page.

        Returns:
            Authenticated Playwright page

        Raises:
            AuthenticationError: If not authenticated or session invalid
        """
        if not self._authenticated or not self._page or self._page.is_closed():
            raise AuthenticationError("Not authenticated or session invalid")

        return self._page

    async def get_context(self) -> BrowserContext:
        """
        Get authenticated browser context.

        Returns:
            Authenticated browser context

        Raises:
            AuthenticationError: If not authenticated or session invalid
        """
        if not self._authenticated or not self._context:
            raise AuthenticationError("Not authenticated or session invalid")

        return self._context

    def is_authenticated(self) -> bool:
        """
        Check if session is authenticated and valid.

        Returns:
            True if authenticated and session valid, False otherwise
        """
        return (self._authenticated and
                self._page is not None and
                not self._page.is_closed())

    async def close(self) -> None:
        """
        Close browser session and clean up resources.
        """
        try:
            if self._page and not self._page.is_closed():
                await self._page.close()

            if self._context:
                await self._context.close()

            if self._browser:
                await self._browser.close()

            if self._playwright:
                await self._playwright.stop()

        except Exception:
            # Ignore cleanup errors
            pass
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
            self._authenticated = False

    async def _ensure_browser(self) -> None:
        """
        Ensure browser and page are created and ready.

        Raises:
            BrowserSessionError: If browser creation fails
        """
        try:
            if not self._playwright:
                self._playwright = await async_playwright().start()

            if not self._browser:
                self._browser = await self._playwright.chromium.launch(headless=self.headless)

            if not self._context:
                # Create context with reasonable defaults for SDWIS
                self._context = await self._browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                )

            if not self._page:
                self._page = await self._context.new_page()

                # Set default timeouts
                self._page.set_default_timeout(self.timeout)
                self._page.set_default_navigation_timeout(self.timeout)

        except Exception as e:
            raise BrowserSessionError(f"Failed to create browser session: {str(e)}")

    async def navigate_to_module(self, module_url: str) -> None:
        """
        Navigate to a specific SDWIS module URL.

        Args:
            module_url: Relative or absolute URL to navigate to

        Raises:
            AuthenticationError: If not authenticated
            BrowserSessionError: If navigation fails
        """
        if not self.is_authenticated():
            raise AuthenticationError("Must be authenticated to navigate")

        try:
            if not module_url.startswith('http'):
                # Relative URL, make it absolute
                module_url = self.base_url + module_url.lstrip('/')

            await self._page.goto(module_url)
            await self._page.wait_for_load_state('domcontentloaded')

        except Exception as e:
            raise BrowserSessionError(f"Failed to navigate to {module_url}: {str(e)}")

    async def take_screenshot(self, path: str) -> None:
        """
        Take a screenshot of the current page.

        Args:
            path: File path to save screenshot

        Raises:
            BrowserSessionError: If screenshot fails
        """
        if not self.is_authenticated():
            return

        try:
            await self._page.screenshot(path=path)
        except Exception as e:
            raise BrowserSessionError(f"Failed to take screenshot: {str(e)}")

    async def reset_to_home(self) -> None:
        """
        Navigate back to main menu to reset navigation state.

        This can be useful when switching between different SDWIS modules
        to ensure a clean starting state.

        Raises:
            AuthenticationError: If not authenticated
            BrowserSessionError: If navigation fails
        """
        if not self.is_authenticated():
            raise AuthenticationError("Must be authenticated to reset navigation")

        try:
            # Navigate to the main IBS module page
            home_url = f"{self.base_url}ibsmain_tc.jsp"
            await self._page.goto(home_url)
            await self._page.wait_for_load_state('networkidle')

        except Exception as e:
            raise BrowserSessionError(f"Failed to reset to home: {str(e)}")

    async def __aenter__(self) -> 'SDWISAuthenticatedBrowserSession':
        """Context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.close()


class MockBrowserSession:
    """Mock browser session for testing"""

    def __init__(self, authenticated: bool = True):
        self._authenticated = authenticated

    async def authenticate(self, credentials: Dict[str, str], browser_config: Optional[Dict[str, Any]] = None) -> 'MockBrowserSession':
        self._authenticated = True
        return self

    async def get_page(self) -> None:
        if not self._authenticated:
            raise AuthenticationError("Not authenticated")
        return None  # Mock page

    async def get_context(self) -> None:
        if not self._authenticated:
            raise AuthenticationError("Not authenticated")
        return None  # Mock context

    def is_authenticated(self) -> bool:
        return self._authenticated

    async def close(self) -> None:
        self._authenticated = False
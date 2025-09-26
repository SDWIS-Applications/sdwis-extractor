"""
HTTP-only authentication validator for SDWIS.

Provides fast credential validation without browser overhead.
Used for --check-auth commands and optional pre-validation.
"""

import aiohttp
import asyncio
import os
from typing import Dict
from dotenv import load_dotenv

from ...core.ports import AuthenticationValidationPort, AuthenticationError

# Load environment variables
load_dotenv()


class SDWISHttpAuthValidator:
    """HTTP-only authentication validator for SDWIS system"""

    def __init__(self, base_url: str = None, timeout_seconds: int = 10):
        """
        Initialize HTTP validator.

        Args:
            base_url: SDWIS server base URL
            timeout_seconds: Timeout for HTTP requests
        """
        self.base_url = base_url or os.getenv('SDWIS_URL', 'http://sdwis:8080/SDWIS/')
        if not self.base_url.endswith('/'):
            self.base_url += '/'

        self.login_url = f"{self.base_url}jsp/secure/"
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    async def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """
        Validate credentials using HTTP-only requests following the working pattern.

        Args:
            credentials: Dictionary containing username, password

        Returns:
            True if credentials are valid, False otherwise

        Raises:
            AuthenticationError: If validation fails due to technical issues
        """
        username = credentials.get('username')
        password = credentials.get('password')

        if not username or not password:
            raise AuthenticationError("Username and password are required")

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # Submit login credentials directly (following working pattern)
                login_data = {
                    'j_username': username,
                    'j_password': password
                }

                async with session.post(self.login_url, data=login_data, allow_redirects=True) as response:
                    # Check for JSESSIONID cookie (indicates successful auth - following working pattern)
                    cookies = response.cookies
                    for key in cookies:
                        if key.upper() == 'JSESSIONID':
                            # Test that we can access a module to confirm authentication
                            module_url = f"{self.base_url}ibsmain_tc.jsp"
                            async with session.get(module_url, params={'clearScreenInputs': 'CHANGE'}) as module_response:
                                return module_response.status == 200

                    # No JSESSIONID found - authentication failed
                    return False

        except aiohttp.ClientError as e:
            raise AuthenticationError(f"Network error during authentication: {str(e)}")
        except asyncio.TimeoutError:
            raise AuthenticationError("Authentication request timed out")
        except Exception as e:
            raise AuthenticationError(f"HTTP authentication validation failed: {str(e)}")

    async def check_connectivity(self) -> bool:
        """
        Check connectivity to SDWIS server.

        Returns:
            True if server is reachable, False otherwise
        """
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(self.base_url) as response:
                    # Any response (even error codes) indicates connectivity
                    return response.status in [200, 302, 401, 403, 404]
        except:
            return False

    async def validate_session_cookie(self, session_cookie: str) -> bool:
        """
        Validate if a session cookie is still valid.

        Args:
            session_cookie: JSESSIONID cookie value

        Returns:
            True if session is valid, False otherwise
        """
        try:
            cookies = {'JSESSIONID': session_cookie}

            async with aiohttp.ClientSession(timeout=self.timeout, cookies=cookies) as session:
                # Try to access a protected page
                protected_url = f"{self.base_url}ibsmain_tc.jsp"
                async with session.get(protected_url) as response:
                    # If we get redirected to login, session is invalid
                    final_url = str(response.url)
                    if 'login' in final_url.lower():
                        return False

                    # If we can access the main page, session is valid
                    return response.status == 200 and 'ibsmain_tc.jsp' in final_url

        except:
            return False
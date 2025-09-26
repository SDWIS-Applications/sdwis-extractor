"""
HTTP Authentication Test Adapter

Provides HTTP-only authentication testing without requiring browser automation.
Uses the proven pattern from the Streamlit app.
"""

import aiohttp
import os
from typing import Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class HTTPAuthTestAdapter:
    """HTTP-only authentication test adapter"""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or os.getenv('SDWIS_URL', 'http://sdwis:8080/SDWIS/')).rstrip('/')
        self.login_url = f"{self.base_url}/jsp/secure/"

    async def test_authentication(self, username: str, password: str) -> bool:
        """
        Test authentication using HTTP-only approach.

        Args:
            username: SDWIS username
            password: SDWIS password

        Returns:
            True if authentication successful, False otherwise
        """
        temp_session = None
        try:
            temp_session = aiohttp.ClientSession()

            # Attempt HTTP POST authentication (CoolGen pattern)
            async with temp_session.post(
                self.login_url,
                data={
                    'j_username': username,
                    'j_password': password
                },
                allow_redirects=True
            ) as response:
                # Check for JSESSIONID cookie (indicates successful auth)
                cookies = response.cookies
                for key in cookies:
                    if key.upper() == 'JSESSIONID':
                        # Test that we can access a module to confirm authentication
                        module_url = f"{self.base_url}/ibsmain_tc.jsp"
                        async with temp_session.get(
                            module_url,
                            params={'clearScreenInputs': 'CHANGE'}
                        ) as module_response:
                            return module_response.status == 200

                # No JSESSIONID found - authentication failed
                return False

        except Exception:
            return False
        finally:
            if temp_session:
                await temp_session.close()

    async def test_authentication_from_env(self) -> Dict[str, any]:
        """
        Test authentication using environment variables.

        Returns:
            Dictionary with test results and metadata
        """
        username = os.getenv('SDWIS_USERNAME')
        password = os.getenv('SDWIS_PASSWORD')

        if not username or not password:
            return {
                'success': False,
                'error': 'credentials_missing',
                'message': 'SDWIS_USERNAME and SDWIS_PASSWORD environment variables not set'
            }

        try:
            success = await self.test_authentication(username, password)
            return {
                'success': success,
                'username': username,
                'base_url': self.base_url,
                'message': 'Authentication successful' if success else 'Invalid credentials'
            }
        except Exception as e:
            return {
                'success': False,
                'error': 'connection_failed',
                'message': f'Connection failed: {str(e)}',
                'base_url': self.base_url
            }

    def get_server_info(self) -> Dict[str, str]:
        """Get server configuration information"""
        return {
            'base_url': self.base_url,
            'login_url': self.login_url,
            'username': os.getenv('SDWIS_USERNAME', 'Not set'),
            'password_set': bool(os.getenv('SDWIS_PASSWORD'))
        }
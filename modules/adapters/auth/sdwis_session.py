"""
SDWIS Authentication Adapter

Handles authentication and session management for SDWIS system.
Provides session caching and validation.
"""

import hashlib
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Optional
from dotenv import load_dotenv
from playwright.async_api import Page, Browser

# Load environment variables from .env file
load_dotenv()

# AuthSession removed in new architecture
from ...core.ports import AuthenticationError


# Removed in new architecture - replaced by AuthenticatedBrowserSessionPort
# The SDWISAuthAdapter class has been removed as it violated hexagonal architecture principles
# by directly implementing authentication logic in the adapter layer. It has been replaced
# by proper port-based authentication interfaces and adapter implementations.


# SessionAuthAdapter removed - replaced by proper hexagonal authentication ports


class EnvironmentConfigAdapter:
    """Configuration adapter that reads from environment variables"""

    def get_credentials(self) -> Dict[str, str]:
        """Get credentials from environment variables"""
        username = os.getenv('SDWIS_USERNAME')
        password = os.getenv('SDWIS_PASSWORD')

        if not username or not password:
            raise ValueError(
                "SDWIS credentials not found. "
                "Set SDWIS_USERNAME and SDWIS_PASSWORD environment variables"
            )

        return {
            'username': username,
            'password': password
        }

    def get_server_config(self) -> Dict[str, str]:
        """Get server configuration from environment"""
        return {
            'base_url': os.getenv('SDWIS_URL', 'http://sdwis:8080/SDWIS/'),
            'timeout': os.getenv('SDWIS_TIMEOUT', '30'),
            'headless': os.getenv('SDWIS_HEADLESS', 'true').lower() == 'true'
        }

    def get_extraction_config(self) -> Dict[str, str]:
        """Get extraction configuration"""
        return {
            'batch_size': os.getenv('SDWIS_BATCH_SIZE', '1000'),
            'max_retries': os.getenv('SDWIS_MAX_RETRIES', '3'),
            'retry_delay': os.getenv('SDWIS_RETRY_DELAY', '5')
        }

    def validate_config(self) -> bool:
        """Validate that required configuration is present"""
        try:
            credentials = self.get_credentials()
            server_config = self.get_server_config()
            return bool(credentials.get('username') and
                       credentials.get('password') and
                       server_config.get('base_url'))
        except:
            return False


class StreamlitConfigAdapter:
    """Configuration adapter for Streamlit session state"""

    def __init__(self, session_state=None):
        self.session_state = session_state

    def get_credentials(self) -> Dict[str, str]:
        """Get credentials from Streamlit session state"""
        if not self.session_state:
            raise ValueError("No Streamlit session state available")

        username = getattr(self.session_state, 'sdwis_username', None)
        password = getattr(self.session_state, 'sdwis_password', None)

        if not username or not password:
            raise ValueError("SDWIS credentials not found in session state")

        return {
            'username': username,
            'password': password
        }

    def get_server_config(self) -> Dict[str, str]:
        """Get server config from session state or environment"""
        base_url = (getattr(self.session_state, 'sdwis_url', None) if self.session_state
                   else None) or os.getenv('SDWIS_URL', 'http://sdwis:8080/SDWIS/')

        return {
            'base_url': base_url,
            'timeout': '30',
            'headless': 'true'
        }

    def get_extraction_config(self) -> Dict[str, str]:
        """Get extraction configuration"""
        return {
            'batch_size': '1000',
            'max_retries': '3',
            'retry_delay': '2'
        }

    def validate_config(self) -> bool:
        """Validate configuration"""
        try:
            credentials = self.get_credentials()
            return bool(credentials.get('username') and credentials.get('password'))
        except:
            return False
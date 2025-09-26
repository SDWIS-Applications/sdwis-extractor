"""
Configuration adapters for SDWIS authentication.

These adapters provide credentials and configuration settings
without handling authentication sessions.
"""

import os
from typing import Dict
from dotenv import load_dotenv

from ...core.validation import ConfigurationValidator, InvalidConfigurationError, ValidationResult

# Load environment variables
load_dotenv()


class EnvironmentConfigAdapter:
    """Configuration adapter that reads from environment variables with enhanced validation"""

    def __init__(self, validate_on_access: bool = False):
        self.validator = ConfigurationValidator()
        self.validate_on_access = validate_on_access

    def get_credentials(self) -> Dict[str, str]:
        """Get credentials from environment variables with validation"""
        credentials = {
            'username': os.getenv('SDWIS_USERNAME', ''),
            'password': os.getenv('SDWIS_PASSWORD', '')
        }

        if self.validate_on_access:
            result = self.validator.validate_credentials(credentials)
            if not result.valid:
                raise InvalidConfigurationError(result)

        if not credentials['username'] or not credentials['password']:
            raise ValueError(
                "SDWIS credentials not found. "
                "Set SDWIS_USERNAME and SDWIS_PASSWORD environment variables"
            )

        return credentials

    def get_server_config(self) -> Dict[str, str]:
        """Get server configuration from environment"""
        return {
            'base_url': os.getenv('SDWIS_URL', 'http://sdwis:8080/SDWIS/'),
            'timeout': os.getenv('SDWIS_TIMEOUT', '30')
        }

    def get_browser_config(self) -> Dict[str, str]:
        """Get browser configuration from environment"""
        return {
            'headless': os.getenv('SDWIS_HEADLESS', 'true').lower() == 'true',
            'timeout': int(os.getenv('SDWIS_BROWSER_TIMEOUT', '30000'))
        }

    def get_extraction_config(self) -> Dict[str, str]:
        """Get extraction configuration"""
        return {
            'batch_size': os.getenv('SDWIS_BATCH_SIZE', '1000'),
            'max_retries': os.getenv('SDWIS_MAX_RETRIES', '3'),
            'retry_delay': os.getenv('SDWIS_RETRY_DELAY', '5')
        }


    def validate_config_detailed(self) -> ValidationResult:
        """
        Perform detailed configuration validation with helpful error messages.

        Returns:
            ValidationResult with detailed feedback
        """
        try:
            credentials = {
                'username': os.getenv('SDWIS_USERNAME', ''),
                'password': os.getenv('SDWIS_PASSWORD', '')
            }
            server_config = {
                'base_url': os.getenv('SDWIS_URL', 'http://sdwis:8080/SDWIS/'),
                'timeout': os.getenv('SDWIS_TIMEOUT', '30'),
                'headless': os.getenv('SDWIS_HEADLESS', 'true')
            }
            extraction_config = {
                'batch_size': os.getenv('SDWIS_BATCH_SIZE', '1000'),
                'timeout_ms': int(os.getenv('SDWIS_TIMEOUT', '30')) * 1000,  # Convert to ms
                'max_retries': os.getenv('SDWIS_MAX_RETRIES', '3')
            }

            return self.validator.validate_complete_configuration(
                credentials, server_config, extraction_config
            )

        except Exception as e:
            from ...core.validation import ValidationError
            return ValidationResult(
                valid=False,
                errors=[ValidationError(
                    field="configuration",
                    value=str(e),
                    message="unexpected error during validation",
                    suggestion="Check environment variables and configuration",
                    code="VALIDATION_ERROR"
                )],
                warnings=[]
            )


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
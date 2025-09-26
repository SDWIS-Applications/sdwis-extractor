"""
Simplified unit tests for Streamlit configuration adapter.

These tests focus on the core functionality without complex mocking.
"""

import pytest
import sys
from pathlib import Path

# Add modules to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class TestStreamlitConfigAdapterSimple:
    """Simplified test suite for StreamlitConfigAdapter"""

    @pytest.fixture
    def mock_session_state(self):
        """Create a simple mock session state"""
        class MockSessionState:
            def __init__(self):
                self.data = {}

            def get(self, key, default=None):
                return self.data.get(key, default)

            def __contains__(self, key):
                return key in self.data

            def __setitem__(self, key, value):
                self.data[key] = value

            def __getitem__(self, key):
                return self.data[key]

        return MockSessionState()

    def test_get_credentials_with_cached_values(self):
        """Test credentials retrieval with cached values (thread-safe mode)"""
        # Import here to avoid module pollution
        from modules.adapters.ui.streamlit_app import StreamlitConfigAdapter

        cached_values = {
            'username': 'testuser',
            'password': 'testpass123',
            'server_url': 'http://test:8080/SDWIS/'
        }

        adapter = StreamlitConfigAdapter(cached_values=cached_values)
        credentials = adapter.get_credentials()

        assert credentials['username'] == 'testuser'
        assert credentials['password'] == 'testpass123'

    def test_get_credentials_returns_empty_with_cached_values(self):
        """Test that cached values bypass validation (thread-safe mode behavior)"""
        from modules.adapters.ui.streamlit_app import StreamlitConfigAdapter

        cached_values = {
            'username': '',
            'password': '',
            'server_url': ''
        }

        adapter = StreamlitConfigAdapter(cached_values=cached_values)
        credentials = adapter.get_credentials()

        # Cached values bypass validation - returns empty strings
        assert credentials['username'] == ''
        assert credentials['password'] == ''

    def test_get_server_config_with_cached_values(self):
        """Test server config retrieval with cached values"""
        from modules.adapters.ui.streamlit_app import StreamlitConfigAdapter

        cached_values = {
            'server_url': 'http://custom:9090/SDWIS/',
            'username': 'user',
            'password': 'pass'
        }

        adapter = StreamlitConfigAdapter(cached_values=cached_values)
        server_config = adapter.get_server_config()

        assert server_config['base_url'] == 'http://custom:9090/SDWIS/'

    def test_get_server_config_with_missing_cached_key(self):
        """Test server config uses default when cached key is missing"""
        from modules.adapters.ui.streamlit_app import StreamlitConfigAdapter

        cached_values = {
            # server_url key is missing
            'username': 'user',
            'password': 'pass'
        }

        adapter = StreamlitConfigAdapter(cached_values=cached_values)
        server_config = adapter.get_server_config()

        # Should use default when key is missing
        assert server_config['base_url'] == 'http://sdwis:8080/SDWIS/'

    def test_get_server_config_with_empty_cached_value(self):
        """Test server config uses empty cached value when explicitly set"""
        from modules.adapters.ui.streamlit_app import StreamlitConfigAdapter

        cached_values = {
            'server_url': '',  # Explicitly empty
            'username': 'user',
            'password': 'pass'
        }

        adapter = StreamlitConfigAdapter(cached_values=cached_values)
        server_config = adapter.get_server_config()

        # Should use the empty string that was explicitly cached
        assert server_config['base_url'] == ''

    def test_get_browser_config(self):
        """Test browser configuration"""
        from modules.adapters.ui.streamlit_app import StreamlitConfigAdapter

        adapter = StreamlitConfigAdapter(cached_values={'username': 'u', 'password': 'p'})
        browser_config = adapter.get_browser_config()

        assert browser_config['headless'] is True
        assert browser_config['timeout'] == 60000
        assert '--no-sandbox' in browser_config['args']
        assert '--disable-dev-shm-usage' in browser_config['args']

    def test_get_extraction_config(self):
        """Test extraction configuration"""
        from modules.adapters.ui.streamlit_app import StreamlitConfigAdapter

        adapter = StreamlitConfigAdapter(cached_values={'username': 'u', 'password': 'p'})
        extraction_config = adapter.get_extraction_config()

        assert extraction_config['batch_size'] == '1000'
        assert extraction_config['timeout'] == 60000

    def test_validate_config_success_with_cached(self):
        """Test config validation with complete cached configuration"""
        from modules.adapters.ui.streamlit_app import StreamlitConfigAdapter

        cached_values = {
            'username': 'testuser',
            'password': 'testpass',
            'server_url': 'http://sdwis:8080/SDWIS/'
        }

        adapter = StreamlitConfigAdapter(cached_values=cached_values)
        assert adapter.validate_config() is True

    def test_validate_config_failure_no_credentials(self):
        """Test config validation fails without credentials in cached values"""
        from modules.adapters.ui.streamlit_app import StreamlitConfigAdapter

        cached_values = {
            'username': '',
            'password': 'testpass',
            'server_url': 'http://sdwis:8080/SDWIS/'
        }

        adapter = StreamlitConfigAdapter(cached_values=cached_values)
        assert adapter.validate_config() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
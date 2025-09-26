"""
Shared pytest configuration and fixtures for SDWIS automation tests.

This file provides common fixtures and configuration used across all test types
in the hexagonal architecture test suite.
"""

import pytest
import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import domain models for fixtures
from modules.core.domain import (
    ExtractionQuery, ExtractionResult, ExtractionMetadata,
    PaginationConfig, ProgressUpdate
)
from modules.core.export_configuration import ExportConfiguration, ExportMode, FileNamingPolicy


# Use pytest-asyncio's default event loop management


# Domain Model Fixtures
@pytest.fixture
def sample_extraction_query():
    """Standard extraction query for testing."""
    return ExtractionQuery(
        data_type="water_systems",
        filters={"status": "active"},
        pagination=PaginationConfig(max_pages=2, page_size=100)
    )


@pytest.fixture
def sample_extraction_result():
    """Sample extraction result for testing output adapters."""
    return ExtractionResult(
        success=True,
        data=[
            {
                "Water System No.": "0010001",
                "Name": "Test Water System",
                "Activity Status": "Active",
                "Population": "1500",
                "Principal County Served": "Test County"
            },
            {
                "Water System No.": "0010002",
                "Name": "Another Test System",
                "Activity Status": "Active",
                "Population": "2500",
                "Principal County Served": "Another County"
            }
        ],
        metadata=ExtractionMetadata(
            extracted_count=2,
            extraction_time=1.5,
            data_type="water_systems",
            total_available=2
        )
    )


@pytest.fixture
def sample_export_configuration():
    """Standard export configuration for testing."""
    return ExportConfiguration(
        data_types=["water_systems"],
        export_mode=ExportMode.GENERAL,
        output_format="json",
        output_path="test_output.json",
        file_naming_policy=FileNamingPolicy()
    )


# Mock Adapter Fixtures
@pytest.fixture
def mock_extraction_port():
    """Mock extraction port for service testing."""
    mock = AsyncMock()
    mock.get_supported_data_types.return_value = ["water_systems", "legal_entities"]
    mock.validate_query.return_value = True
    mock.extract_data.return_value = ExtractionResult(
        success=True,
        data=[{"test": "data"}],
        metadata=ExtractionMetadata(
            extracted_count=1,
            extraction_time=0.1,
            data_type="water_systems"
        )
    )
    return mock


@pytest.fixture
def mock_browser_session():
    """Mock authenticated browser session."""
    mock = AsyncMock()
    # is_authenticated is called synchronously in production code, so use a regular Mock
    mock.is_authenticated = Mock(return_value=True)

    # Create a Mock page that has .on() method but doesn't fail when called
    mock_page = Mock()
    mock_page.on = Mock()  # This prevents the async warnings

    # get_page is async, so we need to set up the return value properly
    async def get_mock_page():
        return mock_page

    mock.get_page = get_mock_page

    mock.get_context.return_value = Mock()  # Mock context object
    return mock


@pytest.fixture
def mock_progress_port():
    """Mock progress reporting port."""
    mock = Mock()
    mock.is_progress_enabled.return_value = True
    return mock


@pytest.fixture
def mock_output_port():
    """Mock output port for service testing."""
    mock = AsyncMock()
    mock.get_supported_formats.return_value = ["json", "csv"]
    mock.validate_destination.return_value = True
    mock.save_data.return_value = True
    return mock


@pytest.fixture
def mock_config_port():
    """Mock configuration port."""
    mock = Mock()
    mock.get_credentials.return_value = {"username": "test", "password": "test"}
    mock.get_server_config.return_value = {"base_url": "http://test:8080/SDWIS/"}
    mock.get_extraction_config.return_value = {"batch_size": 1000}
    mock.validate_config.return_value = True
    return mock


@pytest.fixture
def mock_auth_validator():
    """Mock authentication validator."""
    mock = AsyncMock()
    mock.validate_credentials.return_value = True
    mock.check_connectivity.return_value = True
    return mock


# Test Data Fixtures
@pytest.fixture
def sample_water_systems_data():
    """Sample water systems data for testing."""
    return [
        {
            "Activity Status": "Active",
            "Water System No.": "0010001",
            "Name": "Municipal Water System",
            "Federal Primary Source": "GW",
            "Federal Type": "CWS",
            "State Type": "Municipal",
            "Population": "15000",
            "Principal County Served": "Test County"
        },
        {
            "Activity Status": "Active",
            "Water System No.": "0010002",
            "Name": "Rural Water District",
            "Federal Primary Source": "SW",
            "Federal Type": "CWS",
            "State Type": "Rural",
            "Population": "5000",
            "Principal County Served": "Rural County"
        }
    ]


@pytest.fixture
def sample_legal_entities_data():
    """Sample legal entities data for testing."""
    return [
        {
            "Last Name": "SMITH",
            "First Name": "JOHN",
            "Middle Initial": "A",
            "Status": "Active",
            "Organization": "Test Utility",
            "Mail Stop": "MS001",
            "State Code": "MS"
        },
        {
            "Last Name": "JOHNSON",
            "First Name": "MARY",
            "Middle Initial": "B",
            "Status": "Active",
            "Organization": "Another Utility",
            "Mail Stop": "MS002",
            "State Code": "MS"
        }
    ]


# Configuration Fixtures
@pytest.fixture
def test_config():
    """Test configuration dictionary."""
    return {
        "base_url": "http://test-sdwis:8080/SDWIS/",
        "timeout_ms": 5000,
        "headless": True,
        "credentials": {
            "username": "test_user",
            "password": "test_pass"
        }
    }


# Factory Fixtures
@pytest.fixture
def mock_browser_session_factory():
    """Factory function that creates mock browser sessions."""
    def factory():
        return mock_browser_session
    return factory


# Helper Functions for Tests
def assert_extraction_result_valid(result: ExtractionResult):
    """Helper function to validate extraction results."""
    assert isinstance(result, ExtractionResult)
    assert isinstance(result.success, bool)
    assert isinstance(result.data, list)
    assert isinstance(result.metadata, ExtractionMetadata)
    assert isinstance(result.errors, list)
    assert isinstance(result.warnings, list)


def assert_extraction_query_valid(query: ExtractionQuery):
    """Helper function to validate extraction queries."""
    assert isinstance(query, ExtractionQuery)
    assert query.data_type in ["water_systems", "legal_entities", "sample_schedules"]
    assert isinstance(query.filters, dict)
    assert isinstance(query.pagination, PaginationConfig)
    assert isinstance(query.metadata, dict)


# Pytest Configuration Hooks
def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Add custom markers if not already defined
    markers = [
        "unit: Unit tests (fast, isolated)",
        "integration: Integration tests (slower, multiple components)",
        "contract: Port contract compliance tests",
        "architecture: Architecture validation tests",
        "e2e: End-to-end tests (slowest, full system)",
        "mock: Tests using mock data only",
        "real: Tests requiring real SDWIS connection"
    ]

    for marker in markers:
        config.addinivalue_line("markers", marker)


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Auto-mark tests based on file path
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "contract" in str(item.fspath):
            item.add_marker(pytest.mark.contract)
        elif "architecture" in str(item.fspath):
            item.add_marker(pytest.mark.architecture)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)

        # Mark tests that require real SDWIS connection
        if "real" in item.name or "live" in item.name:
            item.add_marker(pytest.mark.real)
        else:
            item.add_marker(pytest.mark.mock)


# Async Test Helpers
class AsyncContextManager:
    """Helper for testing async context managers."""
    def __init__(self, mock_object):
        self.mock_object = mock_object

    async def __aenter__(self):
        return self.mock_object

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def async_context_manager():
    """Factory for creating async context managers in tests."""
    return AsyncContextManager


# Test Environment Validation
def pytest_sessionstart(session):
    """Validate test environment at session start."""
    import sys
    import os

    # Ensure we can import modules
    try:
        import modules.core.domain
        import modules.adapters.output.json
    except ImportError as e:
        pytest.fail(f"Cannot import modules: {e}")

    # Check Python version
    if sys.version_info < (3, 11):
        pytest.fail("Tests require Python 3.11 or higher")

    print(f"Running tests with Python {sys.version}")
    print(f"Test environment: {os.environ.get('TEST_ENV', 'development')}")


def pytest_sessionfinish(session, exitstatus):
    """Clean up after test session."""
    print(f"Test session completed with exit status: {exitstatus}")
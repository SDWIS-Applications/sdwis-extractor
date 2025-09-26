"""
Test helpers and utilities for the SDWIS automation test suite.

This module provides common test utilities, assertion helpers, mock factories,
and test data generators used across all test types in the hexagonal architecture.
"""

import asyncio
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union
from unittest.mock import AsyncMock, Mock

from modules.core.domain import (
    ExtractionQuery, ExtractionResult, ExtractionMetadata,
    PaginationConfig, ProgressUpdate
)
from modules.core.export_configuration import ExportConfiguration, ExportMode, FileNamingPolicy


class TestDataGenerator:
    """Generate test data for various SDWIS components."""

    @staticmethod
    def water_systems_data(count: int = 5) -> List[Dict[str, Any]]:
        """Generate sample water systems data."""
        systems = []
        for i in range(count):
            systems.append({
                "Activity Status": "Active",
                "Water System No.": f"00100{i:02d}",
                "Name": f"Test Water System {i + 1}",
                "Federal Primary Source": "GW" if i % 2 == 0 else "SW",
                "Federal Type": "CWS",
                "State Type": "Municipal" if i % 3 == 0 else "Rural",
                "Population": str((i + 1) * 1000),
                "Principal County Served": f"Test County {i + 1}"
            })
        return systems

    @staticmethod
    def legal_entities_data(count: int = 5) -> List[Dict[str, Any]]:
        """Generate sample legal entities data."""
        entities = []
        for i in range(count):
            entities.append({
                "Last Name": f"LASTNAME{i + 1}",
                "First Name": f"FIRSTNAME{i + 1}",
                "Middle Initial": chr(65 + i),  # A, B, C, etc.
                "Status": "Active",
                "Organization": f"Test Organization {i + 1}",
                "Mail Stop": f"MS{i + 1:03d}",
                "State Code": "MS",
                "ID Number": f"ID{i + 1:06d}"
            })
        return entities

    @staticmethod
    def sample_schedules_data(count: int = 3) -> List[Dict[str, Any]]:
        """Generate sample schedules data."""
        schedules = []
        for i in range(count):
            schedules.append({
                "PWS ID": f"00100{i:02d}",
                "Facility ID": f"FACILITY_{i + 1}",
                "Schedule Type": "Monthly" if i % 2 == 0 else "Quarterly",
                "Analyte Group": "DBP" if i % 2 == 0 else "IOC",
                "Sample Point": f"SP{i + 1:03d}",
                "Collection Date": f"2023-{i + 1:02d}-15",
                "Status": "Active"
            })
        return schedules

    @staticmethod
    def extraction_metadata(
        data_type: str = "water_systems",
        extracted_count: int = 5,
        extraction_time: float = 1.5,
        total_available: Optional[int] = None
    ) -> ExtractionMetadata:
        """Generate sample extraction metadata."""
        return ExtractionMetadata(
            extracted_count=extracted_count,
            extraction_time=extraction_time,
            data_type=data_type,
            total_available=total_available or extracted_count,
            extraction_timestamp=datetime.now(),
            source_info={
                "extractor": "TestExtractor",
                "base_url": "http://test-sdwis:8080/SDWIS/",
                "extraction_method": "test_method"
            },
            pagination_info={
                "batches_processed": 1,
                "unique_records_found": extracted_count
            }
        )


class MockFactory:
    """Factory for creating mock objects with realistic behavior."""

    @staticmethod
    def create_extraction_port(
        data_types: List[str] = None,
        should_succeed: bool = True
    ):
        """Create a mock ExtractionPort."""
        mock = AsyncMock()
        mock.get_supported_data_types.return_value = data_types or ["water_systems"]
        mock.validate_query.return_value = True

        if should_succeed:
            mock.extract_data.return_value = ExtractionResult(
                success=True,
                data=TestDataGenerator.water_systems_data(2),
                metadata=TestDataGenerator.extraction_metadata()
            )
        else:
            mock.extract_data.return_value = ExtractionResult(
                success=False,
                data=[],
                metadata=TestDataGenerator.extraction_metadata(extracted_count=0),
                errors=["Test extraction failed"]
            )

        return mock

    @staticmethod
    def create_browser_session(authenticated: bool = True):
        """Create a mock AuthenticatedBrowserSessionPort."""
        mock = AsyncMock()
        mock.is_authenticated.return_value = authenticated
        mock.authenticate.return_value = mock
        mock.get_page.return_value = Mock()  # Mock Playwright page
        mock.get_context.return_value = Mock()  # Mock browser context
        return mock

    @staticmethod
    def create_progress_port(enabled: bool = True):
        """Create a mock ProgressReportingPort."""
        mock = Mock()
        mock.is_progress_enabled.return_value = enabled
        mock.update_progress = Mock()
        mock.set_total_steps = Mock()
        mock.increment_step = Mock()
        mock.report_progress = Mock()
        return mock

    @staticmethod
    def create_output_port(should_succeed: bool = True):
        """Create a mock OutputPort."""
        mock = AsyncMock()
        mock.get_supported_formats.return_value = ["json", "csv"]
        mock.validate_destination.return_value = True
        mock.save_data.return_value = should_succeed
        return mock

    @staticmethod
    def create_config_port(credentials: Dict[str, str] = None):
        """Create a mock ConfigurationPort."""
        mock = Mock()
        mock.get_credentials.return_value = credentials or {"username": "test", "password": "test"}
        mock.get_server_config.return_value = {"base_url": "http://test:8080/SDWIS/"}
        mock.get_extraction_config.return_value = {"batch_size": 1000}
        mock.validate_config.return_value = True
        return mock

    @staticmethod
    def create_auth_validator(credentials_valid: bool = True):
        """Create a mock AuthenticationValidationPort."""
        mock = AsyncMock()
        mock.validate_credentials.return_value = credentials_valid
        mock.check_connectivity.return_value = True
        return mock


class AssertionHelpers:
    """Helper functions for common test assertions."""

    @staticmethod
    def assert_extraction_result_valid(result: ExtractionResult):
        """Assert that an ExtractionResult has valid structure."""
        assert isinstance(result, ExtractionResult)
        assert isinstance(result.success, bool)
        assert isinstance(result.data, list)
        assert hasattr(result, 'metadata')
        assert isinstance(result.metadata, ExtractionMetadata)
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)

    @staticmethod
    def assert_extraction_result_successful(result: ExtractionResult, expected_count: int = None):
        """Assert that an ExtractionResult represents successful extraction."""
        AssertionHelpers.assert_extraction_result_valid(result)
        assert result.success is True, f"Expected successful result, got errors: {result.errors}"
        assert len(result.data) > 0, "Expected data in successful result"

        if expected_count is not None:
            assert len(result.data) == expected_count, \
                f"Expected {expected_count} records, got {len(result.data)}"
            assert result.metadata.extracted_count == expected_count, \
                f"Metadata count {result.metadata.extracted_count} doesn't match data length {len(result.data)}"

    @staticmethod
    def assert_extraction_result_failed(result: ExtractionResult):
        """Assert that an ExtractionResult represents failed extraction."""
        AssertionHelpers.assert_extraction_result_valid(result)
        assert result.success is False, "Expected failed result"
        assert len(result.errors) > 0, "Expected error messages in failed result"

    @staticmethod
    def assert_extraction_query_valid(query: ExtractionQuery):
        """Assert that an ExtractionQuery has valid structure."""
        assert isinstance(query, ExtractionQuery)
        assert query.data_type in ["water_systems", "legal_entities", "sample_schedules"]
        assert isinstance(query.filters, dict)
        assert isinstance(query.pagination, PaginationConfig)
        assert isinstance(query.metadata, dict)

    @staticmethod
    def assert_water_systems_data_structure(data: List[Dict[str, Any]]):
        """Assert that data has the expected water systems structure."""
        assert isinstance(data, list)

        expected_fields = {
            "Activity Status", "Water System No.", "Name",
            "Federal Primary Source", "Federal Type", "State Type",
            "Population", "Principal County Served"
        }

        for record in data:
            assert isinstance(record, dict)
            record_fields = set(record.keys())
            assert expected_fields.issubset(record_fields), \
                f"Missing fields: {expected_fields - record_fields}"

    @staticmethod
    def assert_legal_entities_data_structure(data: List[Dict[str, Any]]):
        """Assert that data has the expected legal entities structure."""
        assert isinstance(data, list)

        expected_fields = {
            "Last Name", "First Name", "Status", "Organization"
        }

        for record in data:
            assert isinstance(record, dict)
            record_fields = set(record.keys())
            assert expected_fields.issubset(record_fields), \
                f"Missing fields: {expected_fields - record_fields}"

    @staticmethod
    def assert_port_compliance(obj: Any, port_type: Type):
        """Assert that an object implements the required port interface."""
        port_methods = [
            attr for attr in dir(port_type)
            if not attr.startswith('_') and callable(getattr(port_type, attr, None))
        ]

        for method in port_methods:
            assert hasattr(obj, method), f"Object {type(obj)} missing required method: {method}"
            assert callable(getattr(obj, method)), f"Object {type(obj)}.{method} is not callable"


class FileHelpers:
    """Helpers for file system operations in tests."""

    @staticmethod
    def create_temp_file(content: str = "", suffix: str = ".txt") -> str:
        """Create a temporary file with given content."""
        with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
            f.write(content)
            return f.name

    @staticmethod
    def create_temp_json_file(data: Dict[str, Any]) -> str:
        """Create a temporary JSON file with given data."""
        content = json.dumps(data, indent=2)
        return FileHelpers.create_temp_file(content, ".json")

    @staticmethod
    def read_temp_file(file_path: str) -> str:
        """Read content from a temporary file."""
        with open(file_path, 'r') as f:
            return f.read()

    @staticmethod
    def cleanup_temp_file(file_path: str):
        """Clean up a temporary file."""
        try:
            Path(file_path).unlink(missing_ok=True)
        except Exception:
            pass  # Ignore cleanup errors in tests


class AsyncTestHelpers:
    """Helpers for async test scenarios."""

    @staticmethod
    async def run_with_timeout(coro, timeout: float = 5.0):
        """Run an async operation with timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            raise AssertionError(f"Operation timed out after {timeout} seconds")

    @staticmethod
    def create_async_context_manager(mock_obj):
        """Create an async context manager for testing."""
        class AsyncContext:
            async def __aenter__(self):
                return mock_obj

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        return AsyncContext()

    @staticmethod
    async def assert_async_call_made(mock_method, *args, **kwargs):
        """Assert that an async mock method was called with specific arguments."""
        mock_method.assert_called_with(*args, **kwargs)


class ConfigurationHelpers:
    """Helpers for test configuration management."""

    @staticmethod
    def create_test_config() -> Dict[str, Any]:
        """Create a standard test configuration."""
        return {
            "base_url": "http://test-sdwis:8080/SDWIS/",
            "timeout_ms": 5000,
            "headless": True,
            "credentials": {
                "username": "test_user",
                "password": "test_password"
            },
            "extraction": {
                "batch_size": 1000,
                "max_retries": 3,
                "retry_delay": 1.0
            }
        }

    @staticmethod
    def create_export_config(
        data_types: List[str] = None,
        export_mode: ExportMode = ExportMode.GENERAL,
        output_format: str = "json"
    ) -> ExportConfiguration:
        """Create a test export configuration."""
        return ExportConfiguration(
            data_types=data_types or ["water_systems"],
            export_mode=export_mode,
            output_format=output_format,
            output_path=None,  # Will be auto-generated
            file_naming_policy=FileNamingPolicy()
        )


class PerformanceHelpers:
    """Helpers for performance testing."""

    @staticmethod
    def time_execution(func):
        """Decorator to time function execution."""
        import functools
        import time

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time
            return result, execution_time

        return wrapper

    @staticmethod
    async def time_async_execution(coro):
        """Time async function execution."""
        import time
        start_time = time.time()
        result = await coro
        end_time = time.time()
        execution_time = end_time - start_time
        return result, execution_time

    @staticmethod
    def assert_execution_time(execution_time: float, max_time: float):
        """Assert that execution time is within acceptable limits."""
        assert execution_time <= max_time, \
            f"Execution took {execution_time:.3f}s, expected <= {max_time:.3f}s"


class ArchitectureHelpers:
    """Helpers for architecture testing."""

    @staticmethod
    def get_class_dependencies(cls: Type) -> List[str]:
        """Get the dependencies of a class from its constructor."""
        import inspect

        try:
            signature = inspect.signature(cls.__init__)
            dependencies = []

            for param_name, param in signature.parameters.items():
                if param_name != 'self' and param.annotation != inspect.Parameter.empty:
                    dependencies.append(str(param.annotation))

            return dependencies
        except Exception:
            return []

    @staticmethod
    def is_interface_dependency(dependency: str) -> bool:
        """Check if a dependency is an interface/port rather than concrete class."""
        interface_indicators = ['Port', 'Protocol', 'Interface', 'Abstract']
        return any(indicator in dependency for indicator in interface_indicators)

    @staticmethod
    def check_layer_violation(module_path: str, forbidden_imports: List[str]) -> List[str]:
        """Check if a module violates layer boundaries by importing forbidden modules."""
        violations = []

        try:
            with open(module_path, 'r') as f:
                content = f.read()

            for forbidden in forbidden_imports:
                if f"from {forbidden}" in content or f"import {forbidden}" in content:
                    violations.append(f"Imports forbidden module: {forbidden}")

        except Exception:
            pass

        return violations


# Export all helpers for easy importing
__all__ = [
    'TestDataGenerator',
    'MockFactory',
    'AssertionHelpers',
    'FileHelpers',
    'AsyncTestHelpers',
    'ConfigurationHelpers',
    'PerformanceHelpers',
    'ArchitectureHelpers'
]
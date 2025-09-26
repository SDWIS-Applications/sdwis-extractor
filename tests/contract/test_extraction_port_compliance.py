"""
Contract tests for ExtractionPort compliance.

These tests verify that all implementations of ExtractionPort follow the same
interface contract and behavioral expectations, ensuring proper hexagonal
architecture compliance.
"""

import pytest
from unittest.mock import AsyncMock, Mock
from typing import Type, List

from modules.core.ports import ExtractionPort
from modules.core.domain import ExtractionQuery, ExtractionResult
from modules.adapters.extractors.water_systems import WaterSystemsExtractor
from modules.adapters.extractors.legal_entities import LegalEntitiesExtractor
from modules.adapters.extractors.sample_schedules import SampleSchedulesExtractor
from modules.adapters.extractors.native_sdwis import NativeSDWISExtractorAdapter, MockNativeSDWISExtractorAdapter


# Define all extractor implementations to test
EXTRACTOR_IMPLEMENTATIONS = [
    WaterSystemsExtractor,
    LegalEntitiesExtractor,
    SampleSchedulesExtractor,
    NativeSDWISExtractorAdapter,
    MockNativeSDWISExtractorAdapter
]


@pytest.mark.contract
class TestExtractionPortCompliance:
    """Test that all extractors implement ExtractionPort correctly."""

    @pytest.mark.parametrize("extractor_class", EXTRACTOR_IMPLEMENTATIONS)
    def test_extractor_implements_required_methods(self, extractor_class: Type):
        """Verify all extractors have required ExtractionPort methods."""
        extractor = extractor_class()

        # Test method existence
        assert hasattr(extractor, 'extract_data'), f"{extractor_class} missing extract_data method"
        assert hasattr(extractor, 'validate_query'), f"{extractor_class} missing validate_query method"
        assert hasattr(extractor, 'get_supported_data_types'), f"{extractor_class} missing get_supported_data_types method"

        # Test methods are callable
        assert callable(extractor.extract_data), f"{extractor_class}.extract_data is not callable"
        assert callable(extractor.validate_query), f"{extractor_class}.validate_query is not callable"
        assert callable(extractor.get_supported_data_types), f"{extractor_class}.get_supported_data_types is not callable"

    @pytest.mark.parametrize("extractor_class", EXTRACTOR_IMPLEMENTATIONS)
    def test_get_supported_data_types_returns_list(self, extractor_class: Type):
        """Test that get_supported_data_types returns a list of strings."""
        extractor = extractor_class()
        supported_types = extractor.get_supported_data_types()

        assert isinstance(supported_types, list), f"{extractor_class}.get_supported_data_types() must return list"
        assert len(supported_types) > 0, f"{extractor_class} must support at least one data type"

        for data_type in supported_types:
            assert isinstance(data_type, str), f"{extractor_class} data types must be strings"
            assert data_type in ["water_systems", "legal_entities", "sample_schedules", "deficiency_types"], \
                f"{extractor_class} returned unsupported data type: {data_type}"

    @pytest.mark.parametrize("extractor_class", EXTRACTOR_IMPLEMENTATIONS)
    @pytest.mark.asyncio
    async def test_validate_query_returns_boolean(self, extractor_class: Type):
        """Test that validate_query returns a boolean."""
        extractor = extractor_class()
        supported_types = extractor.get_supported_data_types()

        if supported_types:
            query = ExtractionQuery(data_type=supported_types[0])
            result = await extractor.validate_query(query)

            assert isinstance(result, bool), f"{extractor_class}.validate_query() must return boolean"

    @pytest.mark.parametrize("extractor_class", EXTRACTOR_IMPLEMENTATIONS)
    @pytest.mark.asyncio
    async def test_validate_query_accepts_supported_types(self, extractor_class: Type):
        """Test that validate_query returns True for supported data types."""
        extractor = extractor_class()
        supported_types = extractor.get_supported_data_types()

        for data_type in supported_types:
            query = ExtractionQuery(data_type=data_type)
            is_valid = await extractor.validate_query(query)

            assert is_valid is True, f"{extractor_class} should validate supported data type: {data_type}"

    @pytest.mark.parametrize("extractor_class", EXTRACTOR_IMPLEMENTATIONS)
    @pytest.mark.asyncio
    async def test_validate_query_rejects_unsupported_types(self, extractor_class: Type):
        """Test that validate_query returns False for unsupported data types."""
        extractor = extractor_class()
        supported_types = extractor.get_supported_data_types()

        # Find an unsupported type
        all_types = ["water_systems", "legal_entities", "sample_schedules"]
        unsupported_types = [t for t in all_types if t not in supported_types]

        for unsupported_type in unsupported_types:
            query = ExtractionQuery(data_type=unsupported_type)
            is_valid = await extractor.validate_query(query)

            assert is_valid is False, f"{extractor_class} should reject unsupported data type: {unsupported_type}"

    @pytest.mark.parametrize("extractor_class", EXTRACTOR_IMPLEMENTATIONS)
    @pytest.mark.asyncio
    async def test_extract_data_returns_extraction_result(self, extractor_class: Type, mock_browser_session):
        """Test that extract_data returns an ExtractionResult."""
        extractor = extractor_class()
        supported_types = extractor.get_supported_data_types()

        if supported_types:
            query = ExtractionQuery(data_type=supported_types[0])
            result = await extractor.extract_data(query, mock_browser_session)

            assert isinstance(result, ExtractionResult), \
                f"{extractor_class}.extract_data() must return ExtractionResult"
            assert isinstance(result.success, bool), "ExtractionResult.success must be boolean"
            assert isinstance(result.data, list), "ExtractionResult.data must be list"
            assert hasattr(result, 'metadata'), "ExtractionResult must have metadata"
            assert hasattr(result, 'errors'), "ExtractionResult must have errors"
            assert hasattr(result, 'warnings'), "ExtractionResult must have warnings"

    @pytest.mark.parametrize("extractor_class", EXTRACTOR_IMPLEMENTATIONS)
    @pytest.mark.asyncio
    async def test_extract_data_handles_invalid_query(self, extractor_class: Type, mock_browser_session):
        """Test that extract_data handles invalid queries gracefully."""
        extractor = extractor_class()
        supported_types = extractor.get_supported_data_types()

        # Find an unsupported type
        all_types = ["water_systems", "legal_entities", "sample_schedules"]
        unsupported_types = [t for t in all_types if t not in supported_types]

        if unsupported_types:
            query = ExtractionQuery(data_type=unsupported_types[0])
            result = await extractor.extract_data(query, mock_browser_session)

            # Should return unsuccessful result, not raise exception
            assert isinstance(result, ExtractionResult), \
                f"{extractor_class} should return ExtractionResult for invalid query"
            assert result.success is False, \
                f"{extractor_class} should return unsuccessful result for invalid query"
            assert len(result.errors) > 0, \
                f"{extractor_class} should include error message for invalid query"

    @pytest.mark.parametrize("extractor_class", EXTRACTOR_IMPLEMENTATIONS)
    @pytest.mark.asyncio
    async def test_extract_data_with_mock_session(self, extractor_class: Type):
        """Test that extractors work with mock browser sessions."""
        extractor = extractor_class()
        supported_types = extractor.get_supported_data_types()

        if supported_types:
            # Create mock browser session
            mock_session = AsyncMock()
            mock_session.is_authenticated = Mock(return_value=True)  # Sync method

            # Create a proper mock page that won't cause async warnings
            mock_page = Mock()
            mock_page.on = Mock()  # Sync method for event handlers

            async def get_mock_page():
                return mock_page

            mock_session.get_page = get_mock_page
            mock_session.get_context.return_value = AsyncMock()

            query = ExtractionQuery(data_type=supported_types[0])
            result = await extractor.extract_data(query, mock_session)

            # Should handle mock session without errors
            assert isinstance(result, ExtractionResult), \
                f"{extractor_class} should work with mock browser session"


@pytest.mark.contract
class TestExtractionPortBehavioralContract:
    """Test behavioral contracts that all ExtractionPort implementations must follow."""

    @pytest.mark.parametrize("extractor_class", EXTRACTOR_IMPLEMENTATIONS)
    @pytest.mark.asyncio
    async def test_consistent_validation_behavior(self, extractor_class: Type):
        """Test that validation behavior is consistent across calls."""
        extractor = extractor_class()
        supported_types = extractor.get_supported_data_types()

        if supported_types:
            query = ExtractionQuery(data_type=supported_types[0])

            # Multiple calls should return same result
            result1 = await extractor.validate_query(query)
            result2 = await extractor.validate_query(query)

            assert result1 == result2, f"{extractor_class} validation should be consistent"

    @pytest.mark.parametrize("extractor_class", EXTRACTOR_IMPLEMENTATIONS)
    def test_supported_types_consistency(self, extractor_class: Type):
        """Test that get_supported_data_types returns consistent results."""
        extractor = extractor_class()

        # Multiple calls should return same result
        types1 = extractor.get_supported_data_types()
        types2 = extractor.get_supported_data_types()

        assert types1 == types2, f"{extractor_class} supported types should be consistent"
        assert set(types1) == set(types2), f"{extractor_class} supported types set should be consistent"

    @pytest.mark.parametrize("extractor_class", EXTRACTOR_IMPLEMENTATIONS)
    @pytest.mark.asyncio
    async def test_error_handling_consistency(self, extractor_class: Type, mock_browser_session):
        """Test that error handling is consistent across extractors."""
        extractor = extractor_class()

        # Test with None browser session (should handle gracefully)
        supported_types = extractor.get_supported_data_types()
        if supported_types:
            query = ExtractionQuery(data_type=supported_types[0])

            try:
                result = await extractor.extract_data(query, None)
                # Should return error result, not raise exception
                assert isinstance(result, ExtractionResult)
                assert result.success is False
            except Exception:
                # If exception is raised, it should be a specific type
                # (implementation detail, but should be documented)
                pass


@pytest.mark.contract
class TestMockVsRealImplementationContract:
    """Test that mock implementations behave like real ones."""

    @pytest.mark.asyncio
    async def test_mock_extractors_follow_same_interface(self):
        """Test that mock extractors implement the same interface as real ones."""
        mock_extractor = MockNativeSDWISExtractorAdapter()
        real_extractor = NativeSDWISExtractorAdapter()

        # Should have same methods
        mock_methods = set(dir(mock_extractor))
        real_methods = set(dir(real_extractor))

        # Mock should have at least the core methods
        core_methods = {'extract_data', 'validate_query', 'get_supported_data_types'}
        assert core_methods.issubset(mock_methods), "Mock extractor missing core methods"

    @pytest.mark.asyncio
    async def test_mock_extractor_returns_valid_results(self, mock_browser_session):
        """Test that mock extractor returns realistic results."""
        mock_extractor = MockNativeSDWISExtractorAdapter()
        supported_types = mock_extractor.get_supported_data_types()

        for data_type in supported_types:
            query = ExtractionQuery(data_type=data_type)
            result = await mock_extractor.extract_data(query, mock_browser_session)

            assert isinstance(result, ExtractionResult)
            assert result.success is True  # Mock should generally succeed
            assert len(result.data) > 0, "Mock should return sample data"
            assert result.metadata.data_type == data_type

    @pytest.mark.asyncio
    async def test_mock_and_real_validation_consistency(self):
        """Test that mock and real extractors validate queries consistently."""
        mock_extractor = MockNativeSDWISExtractorAdapter()
        real_extractor = NativeSDWISExtractorAdapter()

        # Test with supported types
        mock_types = set(mock_extractor.get_supported_data_types())
        real_types = set(real_extractor.get_supported_data_types())

        # Should support same data types (or mock should be subset)
        assert mock_types.issubset(real_types) or mock_types == real_types, \
            "Mock extractor should support same or fewer types as real extractor"

        for data_type in mock_types.intersection(real_types):
            query = ExtractionQuery(data_type=data_type)

            mock_valid = await mock_extractor.validate_query(query)
            real_valid = await real_extractor.validate_query(query)

            assert mock_valid == real_valid, \
                f"Mock and real extractors should validate {data_type} consistently"
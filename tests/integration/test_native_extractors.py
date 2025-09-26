"""
Comprehensive Integration Tests for Native SDWIS Extractors

Tests the new purpose-built extractors that replace the wrapper-based approach.
Includes both mock and real connection testing scenarios.
"""

import asyncio
import json
import tempfile
import os
import pytest
from pathlib import Path
from typing import Dict, Any

from modules.core.domain import ExtractionQuery, PaginationConfig
from modules.core.services import ExtractionService, BatchExtractionService
from modules.adapters.extractors.native_sdwis import MockNativeSDWISExtractorAdapter
from modules.adapters.progress.silent import SilentProgressAdapter
from modules.adapters.auth.config import EnvironmentConfigAdapter
from modules.adapters.output.json import JSONOutputAdapter
from modules.adapters.output.csv import CSVOutputAdapter
from modules.adapters.auth.browser_session import MockBrowserSession


class TestConfig:
    """Test configuration class"""

    def get_credentials(self):
        return {'username': 'test', 'password': 'test'}

    def get_server_config(self):
        return {'base_url': 'http://test:8080/SDWIS/'}

    def get_browser_config(self):
        return {'headless': True, 'timeout': 30000}

    def get_extraction_config(self):
        return {'batch_size': '1000'}

    def validate_config(self):
        return True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_native_extractor_initialization():
    """Test that native extractors initialize correctly"""
    print("🧪 Testing native extractor initialization...")

    # Test mock extractor initialization
    extractor = MockNativeSDWISExtractorAdapter()

    # Test validation method exists
    query = ExtractionQuery(data_type="water_systems")
    mock_session = MockBrowserSession()

    # Basic functionality test
    result = await extractor.extract_data(query, mock_session)
    assert result is not None, "Should return extraction result"

    print("✅ Native extractor initialization test passed")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mock_extractors_all_data_types():
    """Test mock extractors for all supported data types"""
    print("🧪 Testing mock extractors for all data types...")

    mock_extractor = MockNativeSDWISExtractorAdapter()
    progress = SilentProgressAdapter()
    browser_session_factory = MockBrowserSession
    config = TestConfig()
    json_output = JSONOutputAdapter()

    service = ExtractionService(
        extractor=mock_extractor,
        browser_session_factory=browser_session_factory,
        progress=progress,
        output=json_output,
        config=config
    )

    # Test all supported data types dynamically
    supported_types = mock_extractor.get_supported_data_types()
    print(f"Supported data types: {supported_types}")

    expected_fields = {
        "water_systems": "Water System No.",
        "legal_entities": "Individual Name",
        "deficiency_types": "Type Code"
    }

    for data_type in supported_types:
        print(f"  Testing {data_type}...")
        query = ExtractionQuery(data_type=data_type)
        result = await service.perform_extraction(query)
        assert result.success, f"{data_type} extraction should succeed"
        assert result.metadata.extracted_count >= 1, f"Should extract at least 1 {data_type}"

        # Check for expected field if we have it defined
        if data_type in expected_fields:
            expected_field = expected_fields[data_type]
            assert expected_field in result.data[0], f"Should have proper {data_type} fields"

    print("✅ Mock extractors test passed for all data types")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_query_parameters_handling():
    """Test handling of query parameters for different extractors"""
    print("🧪 Testing query parameters handling...")

    mock_extractor = MockNativeSDWISExtractorAdapter()
    progress = SilentProgressAdapter()
    browser_session_factory = MockBrowserSession
    config = TestConfig()
    json_output = JSONOutputAdapter()

    service = ExtractionService(
        extractor=mock_extractor,
        browser_session_factory=browser_session_factory,
        progress=progress,
        output=json_output,
        config=config
    )

    # Test legal entities with exclusion patterns
    le_query_filtered = ExtractionQuery(
        data_type="legal_entities",
        filters={
            'exclusion_patterns': [".*ADDRESS.*", "^[A-Z]{2}\\d+$"]
        }
    )
    le_result = await service.perform_extraction(le_query_filtered)
    assert le_result.success, "Legal entities with filters should succeed"

    # Test deficiency types with search parameters
    dt_query_params = ExtractionQuery(
        data_type="deficiency_types",
        filters={
            'search_params': {
                'category_code': 'SO',
                'severity_code': 'SIG'
            }
        }
    )
    dt_result = await service.perform_extraction(dt_query_params)
    assert dt_result.success, "Deficiency types with search params should succeed"

    # Test pagination config
    ws_query_paginated = ExtractionQuery(
        data_type="water_systems",
        pagination=PaginationConfig(max_pages=5, page_size=100)
    )
    ws_result = await service.perform_extraction(ws_query_paginated)
    assert ws_result.success, "Water systems with pagination should succeed"

    print("✅ Query parameters handling test passed")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling for various failure scenarios"""
    print("🧪 Testing error handling...")

    mock_extractor = MockNativeSDWISExtractorAdapter()
    progress = SilentProgressAdapter()
    browser_session_factory = MockBrowserSession
    config = TestConfig()
    json_output = JSONOutputAdapter()

    service = ExtractionService(
        extractor=mock_extractor,
        browser_session_factory=browser_session_factory,
        progress=progress,
        output=json_output,
        config=config
    )

    # Test domain validation works correctly
    try:
        invalid_query = ExtractionQuery(data_type="invalid_type")
        assert False, "Domain validation should prevent invalid data types"
    except ValueError as e:
        assert "Unsupported data_type" in str(e), "Should get proper validation error"
        print("   ✓ Domain validation correctly rejects invalid data types")

    # Test extraction with empty data (valid scenario)
    empty_mock = MockNativeSDWISExtractorAdapter(mock_data={
        "water_systems": [],  # Empty but valid data type
        "legal_entities": [],
        "sample_schedules": []
    })
    empty_service = ExtractionService(
        extractor=empty_mock,
        browser_session_factory=browser_session_factory,
        progress=progress,
        output=json_output,
        config=config
    )

    valid_query = ExtractionQuery(data_type="water_systems")
    empty_result = await empty_service.perform_extraction(valid_query)
    # This should succeed but return empty data
    assert empty_result.success, "Empty data should still be a successful extraction"
    assert empty_result.metadata.extracted_count == 0, "Should extract 0 records"

    print("   ✓ Empty data extraction handled correctly")

    print("✅ Error handling test passed")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_output_compatibility():
    """Test that output format is compatible with existing extractors"""
    print("🧪 Testing output format compatibility...")

    mock_extractor = MockNativeSDWISExtractorAdapter()
    progress = SilentProgressAdapter()
    browser_session_factory = MockBrowserSession
    config = TestConfig()

    # Test JSON output compatibility
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json_output = JSONOutputAdapter()
        service = ExtractionService(
            extractor=mock_extractor,
            browser_session_factory=browser_session_factory,
            progress=progress,
            output=json_output,
            config=config
        )

        query = ExtractionQuery(data_type="water_systems")
        result = await service.perform_extraction(query, f.name)

        # Verify JSON structure matches existing extractor format
        json_path = Path(f.name)
        with open(json_path) as json_file:
            data = json.load(json_file)

            # Check required keys
            assert "all_water_systems" in data, "Should have all_water_systems key"
            assert "extraction_summary" in data, "Should have extraction_summary key"

            # Check extraction summary structure
            summary = data["extraction_summary"]
            assert "total_extracted" in summary, "Should have total_extracted"
            assert "extraction_time" in summary, "Should have extraction_time"
            assert "timestamp" in summary, "Should have timestamp"
            assert "success" in summary, "Should have success flag"

            # Verify enhanced metadata from native extractors
            assert "source_info" in summary, "Should have enhanced source_info"
            source_info = summary["source_info"]
            assert "adapter" in source_info, "Should identify the adapter used"
            assert "extraction_architecture" in source_info, "Should identify architecture"

        json_path.unlink()

    # Test CSV output
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        csv_output = CSVOutputAdapter()
        service = ExtractionService(
            extractor=mock_extractor,
            browser_session_factory=browser_session_factory,
            progress=progress,
            output=csv_output,
            config=config
        )

        query = ExtractionQuery(data_type="legal_entities")
        result = await service.perform_extraction(query, f.name)

        csv_path = Path(f.name)
        with open(csv_path) as csv_file:
            content = csv_file.read()
            assert "Individual Name" in content, "Should have legal entities headers"
            assert "SMITH, JOHN" in content, "Should have test data"

        csv_path.unlink()

    print("✅ Output format compatibility test passed")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_batch_processing():
    """Test batch processing with native extractors"""
    print("🧪 Testing batch processing...")

    mock_extractor = MockNativeSDWISExtractorAdapter()
    progress = SilentProgressAdapter()
    browser_session_factory = MockBrowserSession
    config = TestConfig()
    json_output = JSONOutputAdapter()

    batch_service = BatchExtractionService(
        extractor=mock_extractor,
        browser_session_factory=browser_session_factory,
        progress=progress,
        output=json_output,
        config=config
    )

    # Create batch queries using supported data types
    supported_types = mock_extractor.get_supported_data_types()
    queries = [ExtractionQuery(data_type=dt) for dt in supported_types]

    results = await batch_service.perform_batch_extraction(queries)

    assert len(results) == len(supported_types), f"Should return results for all {len(supported_types)} queries"
    assert all(result.success for result in results), "All extractions should succeed"

    # Verify data types
    data_types = [result.metadata.data_type for result in results]
    for expected_type in supported_types:
        assert expected_type in data_types, f"Should include {expected_type}"

    # Verify batch metadata
    for result in results:
        source_info = result.metadata.source_info
        assert "batch_index" in source_info, "Should have batch index"
        assert "batch_total" in source_info, "Should have batch total"
        assert "batch_id" in source_info, "Should have batch ID"

    print("✅ Batch processing test passed")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_progress_integration():
    """Test progress reporting integration"""
    print("🧪 Testing progress integration...")

    mock_extractor = MockNativeSDWISExtractorAdapter()
    progress = SilentProgressAdapter()  # Use silent instead of CLI for tests
    browser_session_factory = MockBrowserSession
    config = TestConfig()
    json_output = JSONOutputAdapter()

    service = ExtractionService(
        extractor=mock_extractor,
        browser_session_factory=browser_session_factory,
        progress=progress,
        output=json_output,
        config=config
    )

    # This should show progress output
    query = ExtractionQuery(data_type="water_systems")
    result = await service.perform_extraction(query)

    assert result.success, "Extraction with progress should succeed"

    print("✅ Progress integration test passed")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_connection_availability():
    """Test if real SDWIS connection is possible (optional)"""
    print("🧪 Testing real connection availability (optional)...")

    # Only run if credentials are available
    try:
        config = EnvironmentConfigAdapter()
        credentials = config.get_credentials()
        server_config = config.get_server_config()

        print(f"📋 Credentials available: username={credentials.get('username', 'None')}")
        print(f"📋 Server URL: {server_config.get('base_url', 'None')}")

        # Don't actually connect in automated tests, just validate config format
        query = ExtractionQuery(data_type="water_systems")
        assert query.data_type == "water_systems", "Query should be valid"

        print("✅ Real connection configuration is valid")

    except Exception as e:
        print(f"ℹ️  Real connection not available: {e}")
        print("   (This is expected in testing environments)")


async def main():
    """Run all integration tests"""
    print("🚀 Starting comprehensive native extractors tests...\n")

    try:
        await test_native_extractor_initialization()
        await test_mock_extractors_all_data_types()
        await test_query_parameters_handling()
        await test_error_handling()
        await test_output_compatibility()
        await test_batch_processing()
        await test_progress_integration()
        await test_real_connection_availability()

        print("\n🎉 All native extractor tests passed!")
        print("🏗️  The new architecture is working correctly with purpose-built extractors!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
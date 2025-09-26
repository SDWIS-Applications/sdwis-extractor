"""
Integration tests for the modular SDWIS extraction architecture.

This script tests the core functionality without requiring actual SDWIS access.
"""

import asyncio
import json
import tempfile
import pytest
from pathlib import Path
from modules.core.domain import ExtractionQuery, PaginationConfig
from modules.core.services import ExtractionService
from modules.adapters.extractors.native_sdwis import MockNativeSDWISExtractorAdapter
from modules.adapters.progress.silent import SilentProgressAdapter
from modules.adapters.output.json import JSONOutputAdapter
from modules.adapters.output.csv import CSVOutputAdapter
from modules.adapters.auth.config import EnvironmentConfigAdapter
from modules.adapters.auth.browser_session import MockBrowserSession


class MockConfigAdapter:
    """Mock configuration adapter for testing"""

    def get_credentials(self):
        return {'username': 'test', 'password': 'test'}

    def get_server_config(self):
        return {'base_url': 'http://test:8080/SDWIS/'}

    def get_extraction_config(self):
        return {'batch_size': '1000'}

    def get_browser_config(self):
        return {'headless': True, 'timeout': 60000}

    def validate_config(self):
        return True


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_basic_extraction():
    """Test basic extraction functionality"""
    print("🧪 Testing basic extraction functionality...")

    # Create mock adapters
    extractor = MockNativeSDWISExtractorAdapter()
    progress = SilentProgressAdapter()
    browser_session_factory = MockBrowserSession
    config = MockConfigAdapter()

    # Test JSON output
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json_output = JSONOutputAdapter()

        service = ExtractionService(
            extractor=extractor,
            browser_session_factory=browser_session_factory,
            progress=progress,
            output=json_output,
            config=config
        )

        # Test water systems extraction
        query = ExtractionQuery(
            data_type="water_systems",
            filters={},
            pagination=PaginationConfig()
        )

        result = await service.perform_extraction(query, f.name)

        assert result.success, "Extraction should succeed"
        assert result.metadata.extracted_count > 0, "Should extract some records"
        assert result.metadata.data_type == "water_systems", "Data type should match"

        # Verify JSON output was created
        json_path = Path(f.name)
        assert json_path.exists(), "JSON file should be created"

        # Verify JSON content
        with open(json_path) as json_file:
            data = json.load(json_file)
            assert "all_water_systems" in data, "Should have water systems data"
            assert "extraction_summary" in data, "Should have extraction summary"

        json_path.unlink()  # Clean up

    print("✅ Basic extraction test passed")


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_csv_output():
    """Test CSV output functionality"""
    print("🧪 Testing CSV output functionality...")

    extractor = MockNativeSDWISExtractorAdapter()
    progress = SilentProgressAdapter()
    browser_session_factory = MockBrowserSession
    config = MockConfigAdapter()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        csv_output = CSVOutputAdapter(use_pandas=False)  # Test without pandas

        service = ExtractionService(
            extractor=extractor,
            browser_session_factory=browser_session_factory,
            progress=progress,
            output=csv_output,
            config=config
        )

        query = ExtractionQuery(data_type="legal_entities")
        result = await service.perform_extraction(query, f.name)

        assert result.success, "CSV extraction should succeed"

        # Verify CSV file was created
        csv_path = Path(f.name)
        assert csv_path.exists(), "CSV file should be created"

        # Verify CSV content
        with open(csv_path) as csv_file:
            content = csv_file.read()
            assert len(content) > 0, "CSV file should not be empty"
            # Should contain headers
            assert "Entity Name" in content or "Name" in content, "Should contain data headers"

        csv_path.unlink()  # Clean up

    print("✅ CSV output test passed")


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_query_validation():
    """Test query validation"""
    print("🧪 Testing query validation...")

    extractor = MockNativeSDWISExtractorAdapter()
    progress = SilentProgressAdapter()
    browser_session_factory = MockBrowserSession
    config = MockConfigAdapter()
    json_output = JSONOutputAdapter()

    service = ExtractionService(
        extractor=extractor,
        browser_session_factory=browser_session_factory,
        progress=progress,
        output=json_output,
        config=config
    )

    # Valid query
    valid_query = ExtractionQuery(data_type="water_systems")
    assert await service.validate_extraction_query(valid_query), "Valid query should pass validation"

    # Check supported data types
    supported_types = await service.get_supported_data_types()
    assert "water_systems" in supported_types, "Should support water systems"
    assert "legal_entities" in supported_types, "Should support legal entities"

    print("✅ Query validation test passed")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_batch_extraction():
    """Test batch extraction functionality"""
    print("🧪 Testing batch extraction...")

    from modules.core.services import BatchExtractionService

    extractor = MockNativeSDWISExtractorAdapter()
    progress = SilentProgressAdapter()
    browser_session_factory = MockBrowserSession
    config = MockConfigAdapter()
    json_output = JSONOutputAdapter()

    service = BatchExtractionService(
        extractor=extractor,
        browser_session_factory=browser_session_factory,
        progress=progress,
        output=json_output,
        config=config
    )

    # Create multiple queries
    queries = [
        ExtractionQuery(data_type="water_systems"),
        ExtractionQuery(data_type="legal_entities"),
    ]

    results = await service.perform_batch_extraction(queries)

    assert len(results) == 2, "Should return results for both queries"
    assert all(result.success for result in results), "All extractions should succeed"
    assert results[0].metadata.data_type == "water_systems", "First result should be water systems"
    assert results[1].metadata.data_type == "legal_entities", "Second result should be legal entities"

    print("✅ Batch extraction test passed")


async def main():
    """Run all tests"""
    print("🚀 Starting modular architecture tests...\n")

    try:
        await test_basic_extraction()
        await test_csv_output()
        await test_query_validation()
        await test_batch_extraction()

        print("\n🎉 All tests passed! The modular architecture is working correctly.")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
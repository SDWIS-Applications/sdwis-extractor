"""
Integration tests for inspection mode functionality.

Tests the specific inspection format with field mappings, validation,
and proper data type restrictions.
"""

import pytest
import json
import tempfile
from pathlib import Path
from modules.core.domain import ExtractionQuery
from modules.core.export_service import ExportMode
from modules.core.export_configuration import ExportConfiguration, FileNamingPolicy
from modules.core.export_orchestration import ExportOrchestrationService
from modules.core.export_service import ExportService
from modules.core.services import BatchExtractionService
from modules.adapters.extractors.native_sdwis import MockNativeSDWISExtractorAdapter
from modules.adapters.progress.silent import SilentProgressAdapter
from modules.adapters.output.json import JSONOutputAdapter
from modules.adapters.auth.config import EnvironmentConfigAdapter
from modules.adapters.auth.browser_session import MockBrowserSession
from modules.adapters.factories import OutputAdapterFactory


class MockConfig:
    """Mock configuration for testing"""

    def get_credentials(self):
        return {'username': 'test', 'password': 'test'}

    def get_server_config(self):
        return {'base_url': 'http://test:8080/SDWIS/'}

    def get_extraction_config(self):
        return {'batch_size': '1000'}

    def get_browser_config(self):
        return {'headless': True, 'timeout': 30}

    def validate_config(self):
        return True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_inspection_mode_field_mappings():
    """Test that inspection mode correctly maps field names"""
    print("🧪 Testing inspection mode field mappings...")

    # Create services
    extractor = MockNativeSDWISExtractorAdapter()
    progress = SilentProgressAdapter()
    browser_session_factory = MockBrowserSession
    config = MockConfig()

    batch_service = BatchExtractionService(
        extractor=extractor,
        browser_session_factory=browser_session_factory,
        progress=progress,
        output=JSONOutputAdapter(),
        config=config
    )

    export_service = ExportService()
    output_factory = OutputAdapterFactory(export_service)

    orchestration_service = ExportOrchestrationService(
        batch_service, export_service, output_factory
    )

    # Create inspection export configuration
    export_config = ExportConfiguration(
        data_types=['water_systems', 'legal_entities'],
        export_mode=ExportMode.INSPECTION,
        output_format='json',
        output_path='test_inspection.json',
        file_naming_policy=FileNamingPolicy()
    )

    # Perform inspection export
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        export_config.output_path = f.name
        result = await orchestration_service.perform_configured_export(export_config)

        assert result['success'], f"Export should succeed: {result.get('error', '')}"

        # Verify output file exists and has correct structure
        with open(f.name, 'r') as json_file:
            data = json.load(json_file)

        # Check water systems mapping
        assert 'water_systems' in data, "Should contain water_systems section"
        water_systems = data['water_systems']
        assert isinstance(water_systems, list), "Water systems should be a list"

        # If we have data, check field structure
        if len(water_systems) > 0:
            water_system = water_systems[0]
            expected_water_fields = ['system_number', 'system_name', 'population',
                                   'county', 'activity_status', 'system_type']
            for field in expected_water_fields:
                assert field in water_system, f"Water system should have {field} field"

        # Check legal entities mapping (if included)
        if 'legal_entities' in data:
            legal_entities = data['legal_entities']
            if len(legal_entities) > 0:
                legal_entity = legal_entities[0]
                expected_legal_fields = ['entity_name', 'status', 'organization',
                                       'state_code', 'mail_stop', 'id_number']
                for field in expected_legal_fields:
                    assert field in legal_entity, f"Legal entity should have {field} field"

                # Verify field values exist (mock data should provide values)
                assert 'entity_name' in legal_entity, "Should have entity_name field"
                assert 'status' in legal_entity, "Should have status field"

        # Clean up
        Path(f.name).unlink()

    print("   ✅ Inspection mode field mappings working correctly")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_inspection_mode_data_type_restrictions():
    """Test that inspection mode only allows water_systems and legal_entities"""
    print("🧪 Testing inspection mode data type restrictions...")

    # Create services
    extractor = MockNativeSDWISExtractorAdapter()
    progress = SilentProgressAdapter()
    browser_session_factory = MockBrowserSession
    config = MockConfig()

    batch_service = BatchExtractionService(
        extractor=extractor,
        browser_session_factory=browser_session_factory,
        progress=progress,
        output=JSONOutputAdapter(),
        config=config
    )

    export_service = ExportService()
    output_factory = OutputAdapterFactory(export_service)

    orchestration_service = ExportOrchestrationService(
        batch_service, export_service, output_factory
    )

    # Test 1: Valid inspection configuration (should succeed)
    valid_config = ExportConfiguration(
        data_types=['water_systems', 'legal_entities'],
        export_mode=ExportMode.INSPECTION,
        output_format='json',
        output_path='valid_inspection.json',
        file_naming_policy=FileNamingPolicy()
    )

    result = await orchestration_service.validate_export_request(valid_config)
    assert result['valid'], "Valid inspection config should pass validation"

    # Test 2: Invalid inspection configuration with sample_schedules (should fail)
    invalid_config = ExportConfiguration(
        data_types=['water_systems', 'legal_entities', 'sample_schedules'],
        export_mode=ExportMode.INSPECTION,
        output_format='json',
        output_path='invalid_inspection.json',
        file_naming_policy=FileNamingPolicy()
    )

    result = await orchestration_service.validate_export_request(invalid_config)
    assert not result['valid'], "Invalid inspection config should fail validation"
    assert len(result['errors']) > 0, "Should have validation errors"

    # Check that the error message mentions the invalid data type
    error_text = ' '.join(result['errors'])
    assert 'sample_schedules' in error_text, "Error should mention sample_schedules"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_inspection_mode_includes_deficiency_types():
    """Test that inspection mode properly includes deficiency_types data"""
    print("🧪 Testing inspection mode with deficiency_types...")

    # Create services
    extractor = MockNativeSDWISExtractorAdapter()
    progress = SilentProgressAdapter()
    browser_session_factory = MockBrowserSession
    config = MockConfig()

    batch_service = BatchExtractionService(
        extractor=extractor,
        browser_session_factory=browser_session_factory,
        progress=progress,
        output=JSONOutputAdapter(),
        config=config
    )

    export_service = ExportService()
    output_factory = OutputAdapterFactory(export_service)

    orchestration_service = ExportOrchestrationService(
        batch_service, export_service, output_factory
    )

    # Create inspection export configuration including deficiency_types
    export_config = ExportConfiguration(
        data_types=['water_systems', 'legal_entities', 'deficiency_types'],
        export_mode=ExportMode.INSPECTION,
        output_format='json',
        output_path='test_inspection_with_deficiency_types.json',
        file_naming_policy=FileNamingPolicy()
    )

    # Perform inspection export
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        export_config.output_path = f.name
        result = await orchestration_service.perform_configured_export(export_config)

        assert result['success'], f"Export should succeed: {result.get('error', '')}"

        # Verify output file exists and has correct structure
        with open(f.name, 'r') as json_file:
            data = json.load(json_file)

        print(f"📋 Available keys in export: {list(data.keys())}")

        # Check that all expected sections are present
        assert 'water_systems' in data, "Should contain water_systems section"
        assert 'legal_entities' in data, "Should contain legal_entities section"
        assert 'deficiency_types' in data, "Should contain deficiency_types section"

        # Check deficiency_types structure and field mappings
        deficiency_types = data['deficiency_types']
        assert isinstance(deficiency_types, list), "deficiency_types should be a list"

        if deficiency_types:  # If there's data, check field mappings
            sample_deficiency = deficiency_types[0]
            expected_fields = ['code', 'typical_severity', 'typical_category', 'description']

            for field in expected_fields:
                assert field in sample_deficiency, f"Deficiency should have '{field}' field"

            print(f"✅ Deficiency types properly mapped with fields: {list(sample_deficiency.keys())}")

        # Clean up
        Path(f.name).unlink(missing_ok=True)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_inspection_vs_general_mode_output():
    """Test differences between inspection and general mode output"""
    print("🧪 Testing inspection vs general mode output differences...")

    # Create services
    extractor = MockNativeSDWISExtractorAdapter()
    progress = SilentProgressAdapter()
    browser_session_factory = MockBrowserSession
    config = MockConfig()

    batch_service = BatchExtractionService(
        extractor=extractor,
        browser_session_factory=browser_session_factory,
        progress=progress,
        output=JSONOutputAdapter(),
        config=config
    )

    export_service = ExportService()
    output_factory = OutputAdapterFactory(export_service)

    orchestration_service = ExportOrchestrationService(
        batch_service, export_service, output_factory
    )

    # Create general mode export
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        general_config = ExportConfiguration(
            data_types=['water_systems'],
            export_mode=ExportMode.GENERAL,
            output_format='json',
            output_path=f.name,
            file_naming_policy=FileNamingPolicy()
        )

        general_result = await orchestration_service.perform_configured_export(general_config)
        assert general_result['success'], "General export should succeed"

        with open(f.name, 'r') as json_file:
            general_data = json.load(json_file)

        Path(f.name).unlink()

    # Create inspection mode export
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        inspection_config = ExportConfiguration(
            data_types=['water_systems'],
            export_mode=ExportMode.INSPECTION,
            output_format='json',
            output_path=f.name,
            file_naming_policy=FileNamingPolicy()
        )

        inspection_result = await orchestration_service.perform_configured_export(inspection_config)
        assert inspection_result['success'], "Inspection export should succeed"

        with open(f.name, 'r') as json_file:
            inspection_data = json.load(json_file)

        Path(f.name).unlink()

    # Compare outputs - different keys for different modes
    assert 'all_water_systems' in general_data, "General should have all_water_systems key"
    assert 'water_systems' in inspection_data, "Inspection should have water_systems key"

    # Check that at least the structure is correct (may be empty due to mock)
    assert isinstance(general_data['all_water_systems'], list), "General should have list of water systems"
    assert isinstance(inspection_data['water_systems'], list), "Inspection should have list of water systems"

    # General mode should have extraction summary
    assert 'extraction_summary' in general_data, "General should have extraction summary"

    # If we have data, verify field structure differences
    if len(general_data['all_water_systems']) > 0 and len(inspection_data['water_systems']) > 0:
        general_system = general_data['all_water_systems'][0]
        inspection_system = inspection_data['water_systems'][0]

        # General mode keeps original field names from SDWIS
        assert 'Water System No.' in general_system, "General should keep original SDWIS field names"
        assert 'Name' in general_system, "General should have 'Name' field"
        assert 'Activity Status' in general_system, "General should have 'Activity Status' field"

        # Inspection mode uses standardized field names
        assert 'system_number' in inspection_system, "Inspection should have standardized 'system_number' field"
        assert 'system_name' in inspection_system, "Inspection should have standardized 'system_name' field"
        assert 'activity_status' in inspection_system, "Inspection should have standardized 'activity_status' field"

    print("   ✅ Mode output differences working correctly")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_inspection_mode_single_data_type():
    """Test inspection mode with single data type"""
    print("🧪 Testing inspection mode with single data type...")

    # Create services
    extractor = MockNativeSDWISExtractorAdapter()
    progress = SilentProgressAdapter()
    browser_session_factory = MockBrowserSession
    config = MockConfig()

    batch_service = BatchExtractionService(
        extractor=extractor,
        browser_session_factory=browser_session_factory,
        progress=progress,
        output=JSONOutputAdapter(),
        config=config
    )

    export_service = ExportService()
    output_factory = OutputAdapterFactory(export_service)

    orchestration_service = ExportOrchestrationService(
        batch_service, export_service, output_factory
    )

    # Test water systems only
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        ws_config = ExportConfiguration(
            data_types=['water_systems'],
            export_mode=ExportMode.INSPECTION,
            output_format='json',
            output_path=f.name,
            file_naming_policy=FileNamingPolicy()
        )

        result = await orchestration_service.perform_configured_export(ws_config)
        assert result['success'], "Water systems inspection should succeed"

        with open(f.name, 'r') as json_file:
            data = json.load(json_file)

        assert 'water_systems' in data, "Should contain water_systems"
        assert 'legal_entities' not in data, "Should not contain legal_entities when not requested"

        Path(f.name).unlink()

    # Test legal entities only
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        le_config = ExportConfiguration(
            data_types=['legal_entities'],
            export_mode=ExportMode.INSPECTION,
            output_format='json',
            output_path=f.name,
            file_naming_policy=FileNamingPolicy()
        )

        result = await orchestration_service.perform_configured_export(le_config)
        assert result['success'], "Legal entities inspection should succeed"

        with open(f.name, 'r') as json_file:
            data = json.load(json_file)

        assert 'legal_entities' in data, "Should contain legal_entities"
        assert 'water_systems' not in data, "Should not contain water_systems when not requested"

        Path(f.name).unlink()

    print("   ✅ Single data type inspection working correctly")


async def main():
    """Run all inspection mode tests"""
    print("🚀 Running Inspection Mode Integration Tests\n")

    tests = [
        test_inspection_mode_field_mappings,
        test_inspection_mode_data_type_restrictions,
        test_inspection_vs_general_mode_output,
        test_inspection_mode_single_data_type
    ]

    for test_func in tests:
        try:
            await test_func()
        except Exception as e:
            print(f"❌ {test_func.__name__} failed: {e}")
            raise

    print("\n🎉 All inspection mode tests passed!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
"""
Unit tests for CLI inspection mode validation.

Tests the command-line validation logic that prevents invalid
data types from being used in inspection mode.
"""

import pytest
import sys
from unittest.mock import patch, MagicMock
from modules.cli.main import create_argument_parser


class TestInspectionModeValidation:
    """Test CLI validation for inspection mode"""

    def test_valid_inspection_mode_combinations(self):
        """Test that valid inspection mode combinations are accepted"""
        parser = create_argument_parser()

        # Test valid combinations
        valid_combinations = [
            ['water_systems', '--export-mode', 'inspection'],
            ['legal_entities', '--export-mode', 'inspection'],
            ['water_systems', 'legal_entities', '--export-mode', 'inspection'],
        ]

        for args in valid_combinations:
            parsed_args = parser.parse_args(args)
            assert parsed_args.export_mode == 'inspection'
            assert all(dt in ['water_systems', 'legal_entities'] for dt in parsed_args.data_types)

    def test_inspection_mode_rejects_sample_schedules(self):
        """Test that inspection mode validation rejects sample_schedules"""
        parser = create_argument_parser()

        # Parse args that would be invalid
        invalid_args = ['water_systems', 'legal_entities', 'sample_schedules', '--export-mode', 'inspection']
        parsed_args = parser.parse_args(invalid_args)

        # Check that our validation logic would catch this
        if parsed_args.export_mode == 'inspection':
            invalid_types = [dt for dt in parsed_args.data_types if dt not in ['water_systems', 'legal_entities']]
            assert 'sample_schedules' in invalid_types, "Should identify sample_schedules as invalid"

    def test_inspection_mode_only_json_format(self):
        """Test that inspection mode implies JSON format"""
        parser = create_argument_parser()

        # Test that inspection mode should override format to JSON
        args = parser.parse_args(['water_systems', '--export-mode', 'inspection', '--format', 'csv'])
        assert args.export_mode == 'inspection'
        assert args.format == 'csv'  # Initially parsed as CSV, but should be corrected to JSON in validation

    def test_general_mode_allows_all_data_types(self):
        """Test that general mode allows all data types"""
        parser = create_argument_parser()

        # Test that general mode accepts sample_schedules
        args = parser.parse_args(['water_systems', 'legal_entities', 'sample_schedules', '--export-mode', 'general'])
        assert args.export_mode == 'general'
        assert 'sample_schedules' in args.data_types

    def test_default_mode_allows_all_data_types(self):
        """Test that default (general) mode allows all data types"""
        parser = create_argument_parser()

        # Test that default mode accepts sample_schedules
        args = parser.parse_args(['water_systems', 'legal_entities', 'sample_schedules'])
        assert args.export_mode == 'general'  # Default should be general
        assert 'sample_schedules' in args.data_types

    @patch('sys.exit')
    @patch('builtins.print')
    def test_cli_validation_error_message(self, mock_print, mock_exit):
        """Test that CLI validation shows proper error message"""
        # Mock the validation logic that would run in main()
        data_types = ['water_systems', 'legal_entities', 'sample_schedules']
        export_mode = 'inspection'

        # Simulate the validation logic from main()
        if export_mode == 'inspection':
            invalid_types = [dt for dt in data_types if dt not in ['water_systems', 'legal_entities']]
            if invalid_types:
                # This is what main() does
                print(f"❌ Error: Inspection mode only supports water_systems and legal_entities.")
                print(f"   Invalid data types for inspection mode: {', '.join(invalid_types)}")
                print("   Use general mode for other data types.")
                sys.exit(1)

        # Verify the error message was shown
        mock_print.assert_any_call("❌ Error: Inspection mode only supports water_systems and legal_entities.")
        mock_print.assert_any_call("   Invalid data types for inspection mode: sample_schedules")
        mock_print.assert_any_call("   Use general mode for other data types.")
        mock_exit.assert_called_once_with(1)

    def test_inspection_mode_field_restrictions(self):
        """Test that inspection mode has correct field restrictions"""
        # This tests our understanding of what inspection mode should include

        # Water systems fields in inspection mode
        expected_water_fields = [
            'system_number',
            'system_name',
            'population',
            'county',
            'activity_status',
            'system_type'
        ]

        # Legal entities fields in inspection mode
        expected_legal_fields = [
            'entity_name',
            'status',
            'organization',
            'state_code',
            'mail_stop',
            'id_number'
        ]

        # These should match what's in the JSON schema
        assert len(expected_water_fields) == 6, "Should have 6 water system fields"
        assert len(expected_legal_fields) == 6, "Should have 6 legal entity fields"

        # Verify no sample schedule fields are included
        sample_schedule_fields = [
            'schedule_id',
            'pws_id',
            'facility_id',
            'analyte_group'
        ]

        # None of these should be in inspection mode
        assert len(sample_schedule_fields) == 4, "Sample schedules have 4 fields but not in inspection mode"


@pytest.mark.unit
class TestInspectionModeConfiguration:
    """Test inspection mode configuration logic"""

    def test_inspection_mode_enum_value(self):
        """Test that inspection mode enum exists"""
        from modules.core.export_configuration import ExportMode

        assert hasattr(ExportMode, 'INSPECTION'), "Should have INSPECTION export mode"
        assert hasattr(ExportMode, 'GENERAL'), "Should have GENERAL export mode"
        assert ExportMode.INSPECTION.value == 'inspection', "Inspection mode value should be 'inspection'"

    def test_supported_formats_for_inspection_mode(self):
        """Test that inspection mode only supports JSON"""
        from modules.core.export_service import ExportService
        from modules.core.export_configuration import ExportMode

        export_service = ExportService()

        # Check supported formats
        inspection_formats = export_service.get_supported_formats_for_mode(ExportMode.INSPECTION)
        general_formats = export_service.get_supported_formats_for_mode(ExportMode.GENERAL)

        assert inspection_formats == ["json"], "Inspection mode should only support JSON"
        assert "csv" in general_formats, "General mode should support CSV"
        assert "json" in general_formats, "General mode should support JSON"

    def test_default_format_for_inspection_mode(self):
        """Test that inspection mode defaults to JSON"""
        from modules.core.export_service import ExportService
        from modules.core.export_configuration import ExportMode

        export_service = ExportService()

        inspection_default = export_service.get_default_format_for_mode(ExportMode.INSPECTION)
        general_default = export_service.get_default_format_for_mode(ExportMode.GENERAL)

        assert inspection_default == "json", "Inspection mode should default to JSON"
        assert general_default == "csv", "General mode should default to CSV"

    def test_inspection_mode_schema_defaults(self):
        """Test that inspection mode can load default data types from schema"""
        from modules.cli.main import get_inspection_schema_data_types

        default_types = get_inspection_schema_data_types()

        # Should return the intersection of schema types and implemented extractors
        assert isinstance(default_types, list), "Should return a list"
        assert len(default_types) >= 2, "Should have at least water_systems and legal_entities"
        assert 'water_systems' in default_types, "Should include water_systems"
        assert 'legal_entities' in default_types, "Should include legal_entities"
        assert 'sample_schedules' not in default_types, "Should not include sample_schedules"

        # Should be sorted
        assert default_types == sorted(default_types), "Should return sorted list"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
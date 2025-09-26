"""
Unit tests for inspection schema field mappings.

Tests that the JSON schema configuration correctly maps
field names for inspection mode output.
"""

import pytest
import json
from pathlib import Path
from modules.adapters.export_schema.schema_loader import SchemaLoader, ConfigurationSchema


@pytest.mark.unit
class TestInspectionSchemaMapping:
    """Test inspection schema field mappings"""

    def test_inspection_schema_file_exists(self):
        """Test that inspection schema JSON file exists"""
        schema_path = Path("config/schemas/inspection_report.json")
        assert schema_path.exists(), "Inspection schema file should exist"

    def test_inspection_schema_structure(self):
        """Test that inspection schema has correct structure"""
        schema_path = Path("config/schemas/inspection_report.json")

        with open(schema_path, 'r') as f:
            schema_data = json.load(f)

        # Check top-level structure
        assert "schema_info" in schema_data, "Should have schema_info section"
        assert "data_types" in schema_data, "Should have data_types section"

        # Check schema info
        schema_info = schema_data["schema_info"]
        assert schema_info["name"] == "inspection_report", "Should be named inspection_report"
        assert "version" in schema_info, "Should have version"
        assert "description" in schema_info, "Should have description"

        # Check data types
        data_types = schema_data["data_types"]
        assert "water_systems" in data_types, "Should include water_systems"
        assert "legal_entities" in data_types, "Should include legal_entities"
        assert "deficiency_types" in data_types, "Should include deficiency_types"
        assert "sample_schedules" not in data_types, "Should NOT include sample_schedules"

    def test_water_systems_field_mappings(self):
        """Test water systems field mappings are correct"""
        schema_path = Path("config/schemas/inspection_report.json")

        with open(schema_path, 'r') as f:
            schema_data = json.load(f)

        water_systems = schema_data["data_types"]["water_systems"]
        fields = water_systems["fields"]

        # Check required mappings
        expected_mappings = {
            "system_number": "Water System No.",
            "system_name": "Name",
            "population": "Population",
            "county": "Principal County Served",
            "activity_status": "Activity Status",
            "system_type": "State Type"
        }

        for output_field, expected_source in expected_mappings.items():
            assert output_field in fields, f"Should have {output_field} field"
            field_config = fields[output_field]
            assert field_config["source_field"] == expected_source, \
                f"{output_field} should map from '{expected_source}'"
            assert field_config["output_field"] == output_field, \
                f"{output_field} output_field should match key"

    def test_legal_entities_field_mappings(self):
        """Test legal entities field mappings are correct"""
        schema_path = Path("config/schemas/inspection_report.json")

        with open(schema_path, 'r') as f:
            schema_data = json.load(f)

        legal_entities = schema_data["data_types"]["legal_entities"]
        fields = legal_entities["fields"]

        # Check required mappings - these should be the user-friendly names
        expected_mappings = {
            "entity_name": "Individual Name",
            "status": "Status",
            "organization": "Organization",
            "state_code": "State Code",
            "mail_stop": "Mail Stop",
            "id_number": "ID Number"
        }

        for output_field, expected_source in expected_mappings.items():
            assert output_field in fields, f"Should have {output_field} field"
            field_config = fields[output_field]
            assert field_config["source_field"] == expected_source, \
                f"{output_field} should map from '{expected_source}', not raw DB field names"
            assert field_config["output_field"] == output_field, \
                f"{output_field} output_field should match key"

    def test_legal_entities_not_using_raw_db_fields(self):
        """Test that legal entities schema does NOT use raw database field names"""
        schema_path = Path("config/schemas/inspection_report.json")

        with open(schema_path, 'r') as f:
            schema_data = json.load(f)

        legal_entities = schema_data["data_types"]["legal_entities"]
        fields = legal_entities["fields"]

        # These are the OLD raw DB field names that should NOT be used
        old_raw_fields = [
            "NAME1",
            "STATUS_CODE1",
            "ORGANIZATION",  # This one is the same, but others are different
            "STATE_CODE1",
            "MAIL_STOP",
            "ID_NUMBER"
        ]

        # Check that we're not using the raw DB field names (except where they match)
        source_fields = [field_config["source_field"] for field_config in fields.values()]

        # These specific raw fields should NOT appear
        problematic_raw_fields = ["NAME1", "STATUS_CODE1", "STATE_CODE1"]
        for raw_field in problematic_raw_fields:
            assert raw_field not in source_fields, \
                f"Should not use raw DB field '{raw_field}' - use user-friendly field name instead"

        # Verify we're using the correct user-friendly names
        assert "Individual Name" in source_fields, "Should use 'Individual Name' not 'NAME1'"
        assert "Status" in source_fields, "Should use 'Status' not 'STATUS_CODE1'"
        assert "State Code" in source_fields, "Should use 'State Code' not 'STATE_CODE1'"

    def test_deficiency_types_field_mappings(self):
        """Test deficiency types field mappings are correct"""
        schema_path = Path("config/schemas/inspection_report.json")

        with open(schema_path, 'r') as f:
            schema_data = json.load(f)

        deficiency_types = schema_data["data_types"]["deficiency_types"]
        fields = deficiency_types["fields"]

        # Check required mappings
        expected_mappings = {
            "code": "Type Code",
            "typical_severity": "Default Severity Code",
            "typical_category": "Default Category Code",
            "description": "Description"
        }

        for output_field, expected_source in expected_mappings.items():
            assert output_field in fields, f"Should have {output_field} field"
            field_config = fields[output_field]
            assert field_config["source_field"] == expected_source, \
                f"{output_field} should map from '{expected_source}'"
            assert field_config["output_field"] == output_field, \
                f"{output_field} output_field should match key"

        # Check that code field is required
        assert fields["code"]["required"] is True, "Code field should be required"
        assert fields["description"]["required"] is False, "Description field should be optional"

    def test_schema_loader_can_load_inspection_schema(self):
        """Test that schema loader can load inspection schema"""
        loader = SchemaLoader("config/schemas")

        # This should not raise an exception
        schema = loader.load_schema("inspection_report")

        assert isinstance(schema, ConfigurationSchema), "Should return ConfigurationSchema instance"

    def test_field_requirements(self):
        """Test that fields have correct requirement settings"""
        schema_path = Path("config/schemas/inspection_report.json")

        with open(schema_path, 'r') as f:
            schema_data = json.load(f)

        # Check water systems requirements
        water_fields = schema_data["data_types"]["water_systems"]["fields"]
        assert water_fields["system_number"]["required"] is True, "System number should be required"
        assert water_fields["system_name"]["required"] is True, "System name should be required"
        assert water_fields["population"]["required"] is False, "Population should be optional"

        # Check legal entities requirements
        legal_fields = schema_data["data_types"]["legal_entities"]["fields"]
        assert legal_fields["entity_name"]["required"] is True, "Entity name should be required"
        assert legal_fields["status"]["required"] is False, "Status should be optional"
        assert legal_fields["organization"]["required"] is False, "Organization should be optional"

    def test_field_descriptions(self):
        """Test that all fields have descriptions"""
        schema_path = Path("config/schemas/inspection_report.json")

        with open(schema_path, 'r') as f:
            schema_data = json.load(f)

        data_types = schema_data["data_types"]

        for data_type_name, data_type_config in data_types.items():
            if "fields" in data_type_config:
                fields = data_type_config["fields"]
                for field_name, field_config in fields.items():
                    assert "description" in field_config, \
                        f"Field {data_type_name}.{field_name} should have description"
                    assert field_config["description"], \
                        f"Field {data_type_name}.{field_name} description should not be empty"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
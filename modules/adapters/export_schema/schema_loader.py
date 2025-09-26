"""
Schema loader for export configurations.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List

from .base_schema import BaseExportSchema, SchemaValidationError, DataType, DataTypeSchema, SchemaField, FieldType


class SchemaLoader:
    """Loads and validates export schemas from configuration files"""

    def __init__(self, schema_directory: str = "config/schemas"):
        self.schema_directory = Path(schema_directory)

    def load_schema(self, schema_name: str) -> 'ConfigurationSchema':
        """
        Load schema from configuration file.

        Args:
            schema_name: Name of schema file (without .json extension)

        Returns:
            ConfigurationSchema instance

        Raises:
            SchemaValidationError: If schema file is invalid or not found
        """
        schema_file = self.schema_directory / f"{schema_name}.json"

        if not schema_file.exists():
            raise SchemaValidationError(f"Schema file not found: {schema_file}")

        try:
            with open(schema_file, 'r', encoding='utf-8') as f:
                schema_data = json.load(f)
        except json.JSONDecodeError as e:
            raise SchemaValidationError(f"Invalid JSON in schema file {schema_file}: {str(e)}")
        except Exception as e:
            raise SchemaValidationError(f"Error reading schema file {schema_file}: {str(e)}")

        return ConfigurationSchema(schema_name, schema_data)

    def list_available_schemas(self) -> List[str]:
        """Get list of available schema files"""
        if not self.schema_directory.exists():
            return []

        schema_files = []
        for file in self.schema_directory.glob("*.json"):
            schema_files.append(file.stem)

        return sorted(schema_files)


class ConfigurationSchema(BaseExportSchema):
    """Schema loaded from configuration file"""

    def __init__(self, name: str, schema_data: Dict[str, Any]):
        self.schema_data = schema_data
        self._validate_schema_structure(schema_data)

        # Extract version from schema info
        version = schema_data.get("schema_info", {}).get("version", "1.0")

        super().__init__(name, version)

    def _validate_schema_structure(self, schema_data: Dict[str, Any]):
        """Validate the schema data structure"""
        if "schema_info" not in schema_data:
            raise SchemaValidationError("Schema must contain 'schema_info' section")

        if "data_types" not in schema_data:
            raise SchemaValidationError("Schema must contain 'data_types' section")

        schema_info = schema_data["schema_info"]
        required_info_fields = ["name", "description"]
        for field in required_info_fields:
            if field not in schema_info:
                raise SchemaValidationError(f"Schema info must contain '{field}' field")

    def _initialize_schema(self):
        """Initialize schema from configuration data"""
        data_types_config = self.schema_data.get("data_types", {})

        for data_type_str, config in data_types_config.items():
            try:
                data_type = DataType(data_type_str)
            except ValueError:
                # Skip unknown data types for forward compatibility
                continue

            schema_fields = []

            # Check if this is an "include all fields" schema
            if config.get("include_all_fields", False):
                # For general export schemas, we don't define specific fields
                # The transform_data method will handle this case
                pass
            else:
                # Process defined fields
                fields_config = config.get("fields", {})
                for field_name, field_config in fields_config.items():
                    schema_field = self._create_schema_field(field_name, field_config)
                    schema_fields.append(schema_field)

            data_type_schema = DataTypeSchema(
                data_type=data_type,
                fields=schema_fields,
                required=config.get("required", False),
                description=config.get("description")
            )

            self.add_data_type_schema(data_type_schema)

    def _create_schema_field(self, field_name: str, field_config: Dict[str, Any]) -> SchemaField:
        """Create SchemaField from configuration"""
        if "source_field" not in field_config:
            raise SchemaValidationError(f"Field '{field_name}' must have 'source_field'")

        if "output_field" not in field_config:
            raise SchemaValidationError(f"Field '{field_name}' must have 'output_field'")

        # Parse field type
        field_type_str = field_config.get("field_type", "string")
        try:
            field_type = FieldType(field_type_str)
        except ValueError:
            field_type = FieldType.STRING

        return SchemaField(
            source_field=field_config["source_field"],
            output_field=field_config["output_field"],
            field_type=field_type,
            required=field_config.get("required", False),
            description=field_config.get("description"),
            transform=field_config.get("transform"),
            default_value=field_config.get("default_value")
        )

    def is_include_all_fields_schema(self, data_type: DataType) -> bool:
        """Check if schema specifies to include all fields for a data type"""
        data_type_config = self.schema_data.get("data_types", {}).get(data_type.value, {})
        return data_type_config.get("include_all_fields", False)

    def transform_data(self, data: Dict[str, List[Dict[str, Any]]],
                      selected_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Transform extracted data according to schema"""
        # For inspection schemas, create hierarchical structure
        if self.name == "inspection_report":
            return self._transform_for_inspection(data, selected_types)
        else:
            return self._transform_for_general_export(data, selected_types)

    def _transform_for_inspection(self, data: Dict[str, List[Dict[str, Any]]],
                                 selected_types: Optional[List[str]]) -> Dict[str, Any]:
        """Transform data for inspection report format (hierarchical)"""
        result = {}

        # Use selected types or all available types
        types_to_process = selected_types or list(data.keys())

        for data_type_str in types_to_process:
            if data_type_str not in data:
                continue

            try:
                data_type = DataType(data_type_str)
            except ValueError:
                continue

            schema = self.get_data_type_schema(data_type)
            if not schema or not schema.fields:
                # If no schema or no fields defined, skip this data type
                continue

            # Transform records according to schema
            transformed_records = []
            for record in data[data_type_str]:
                transformed_record = {}
                for field in schema.fields:
                    source_value = record.get(field.source_field, field.default_value)

                    # Apply transformation if specified
                    if field.transform and source_value is not None:
                        source_value = self._apply_transformation(source_value, field.transform)

                    transformed_record[field.output_field] = source_value

                transformed_records.append(transformed_record)

            result[data_type_str] = transformed_records

        return result

    def _transform_for_general_export(self, data: Dict[str, List[Dict[str, Any]]],
                                     selected_types: Optional[List[str]]) -> Dict[str, Any]:
        """Transform data for general export (all fields, flat structure)"""
        result = {}

        # Use selected types or all available types
        types_to_process = selected_types or list(data.keys())

        for data_type_str in types_to_process:
            if data_type_str not in data:
                continue

            # For general export, include all fields as-is
            result[data_type_str] = data[data_type_str]

        return result

    def get_description(self) -> str:
        """Get schema description"""
        return self.schema_data.get("schema_info", {}).get("description", "")

    def get_schema_summary(self) -> Dict[str, Any]:
        """Get summary information about the schema"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.get_description(),
            "supported_types": [dt.value for dt in self.get_supported_data_types()],
            "export_mode": "hierarchical" if self.name == "inspection_report" else "flat"
        }
"""
Base export schema definitions and validation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from enum import Enum


class DataType(Enum):
    """Supported SDWIS data types"""
    WATER_SYSTEMS = "water_systems"
    LEGAL_ENTITIES = "legal_entities"
    SAMPLE_SCHEDULES = "sample_schedules"
    DEFICIENCY_TYPES = "deficiency_types"


class FieldType(Enum):
    """Field data types for validation"""
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    DATE = "date"
    ARRAY = "array"


@dataclass
class SchemaField:
    """Definition of a field in an export schema"""

    source_field: str                           # Original field name from extraction
    output_field: str                          # Field name in export
    field_type: FieldType = FieldType.STRING  # Expected data type
    required: bool = True                      # Whether field is required
    description: Optional[str] = None          # Field description
    transform: Optional[str] = None            # Optional transformation function name
    default_value: Any = None                  # Default value if missing

    def __post_init__(self):
        """Validate field configuration"""
        if not self.source_field or not self.output_field:
            raise SchemaValidationError("Both source_field and output_field are required")


@dataclass
class DataTypeSchema:
    """Schema definition for a specific data type"""

    data_type: DataType
    fields: List[SchemaField] = field(default_factory=list)
    required: bool = True           # Whether this data type is required in export
    description: Optional[str] = None

    def get_field_mapping(self) -> Dict[str, str]:
        """Get mapping from source field to output field"""
        return {f.source_field: f.output_field for f in self.fields}

    def get_required_fields(self) -> List[str]:
        """Get list of required source fields"""
        return [f.source_field for f in self.fields if f.required]


class SchemaValidationError(Exception):
    """Exception raised when schema validation fails"""
    pass


class BaseExportSchema(ABC):
    """Abstract base class for export schemas"""

    def __init__(self, name: str, version: str = "1.0"):
        self.name = name
        self.version = version
        self.data_types: Dict[DataType, DataTypeSchema] = {}
        self._initialize_schema()

    @abstractmethod
    def _initialize_schema(self):
        """Initialize schema with data type definitions"""
        pass

    def add_data_type_schema(self, schema: DataTypeSchema):
        """Add a data type schema"""
        self.data_types[schema.data_type] = schema

    def get_data_type_schema(self, data_type: Union[DataType, str]) -> Optional[DataTypeSchema]:
        """Get schema for a specific data type"""
        if isinstance(data_type, str):
            try:
                data_type = DataType(data_type)
            except ValueError:
                return None

        return self.data_types.get(data_type)

    def get_supported_data_types(self) -> List[DataType]:
        """Get list of supported data types"""
        return list(self.data_types.keys())

    def validate_data(self, data: Dict[str, List[Dict[str, Any]]]) -> bool:
        """Validate extracted data against schema"""
        try:
            for data_type_str, records in data.items():
                try:
                    data_type = DataType(data_type_str)
                except ValueError:
                    raise SchemaValidationError(f"Unsupported data type: {data_type_str}")

                schema = self.get_data_type_schema(data_type)
                if not schema:
                    if self._is_data_type_required(data_type):
                        raise SchemaValidationError(f"Required data type missing schema: {data_type_str}")
                    continue

                # Validate each record has required fields
                required_fields = schema.get_required_fields()
                for i, record in enumerate(records):
                    missing_fields = [f for f in required_fields if f not in record or record[f] is None]
                    if missing_fields:
                        raise SchemaValidationError(
                            f"Record {i} in {data_type_str} missing required fields: {missing_fields}"
                        )

            return True
        except SchemaValidationError:
            raise
        except Exception as e:
            raise SchemaValidationError(f"Schema validation error: {str(e)}")

    def _is_data_type_required(self, data_type: DataType) -> bool:
        """Check if data type is required"""
        schema = self.data_types.get(data_type)
        return schema.required if schema else False

    def transform_data(self, data: Dict[str, List[Dict[str, Any]]],
                      selected_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Transform extracted data according to schema"""
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
            if not schema:
                # If no schema, pass through as-is
                result[data_type_str] = data[data_type_str]
                continue

            # Transform records according to schema
            transformed_records = []
            field_mapping = schema.get_field_mapping()

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

    def _apply_transformation(self, value: Any, transform: str) -> Any:
        """Apply transformation to field value"""
        # Basic transformations - extend as needed
        if transform == "upper":
            return str(value).upper() if value else value
        elif transform == "lower":
            return str(value).lower() if value else value
        elif transform == "strip":
            return str(value).strip() if value else value
        elif transform == "int":
            try:
                return int(value) if value else 0
            except (ValueError, TypeError):
                return 0
        elif transform == "float":
            try:
                return float(value) if value else 0.0
            except (ValueError, TypeError):
                return 0.0
        else:
            # Unknown transformation, return as-is
            return value

    def get_schema_info(self) -> Dict[str, Any]:
        """Get schema information"""
        return {
            "name": self.name,
            "version": self.version,
            "supported_types": [dt.value for dt in self.get_supported_data_types()],
            "data_type_schemas": {
                dt.value: {
                    "required": schema.required,
                    "description": schema.description,
                    "field_count": len(schema.fields),
                    "required_fields": len(schema.get_required_fields())
                }
                for dt, schema in self.data_types.items()
            }
        }
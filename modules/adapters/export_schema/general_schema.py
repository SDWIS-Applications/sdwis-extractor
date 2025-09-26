"""
General Export Schema

Defines the schema for general data exports that include all available fields.
"""

from .base_schema import BaseExportSchema, DataType, DataTypeSchema


class GeneralExportSchema(BaseExportSchema):
    """Schema for general export format (all fields)"""

    def _initialize_schema(self):
        """Initialize general export schema to include all fields"""

        # Water Systems - include all fields
        water_systems_schema = DataTypeSchema(
            data_type=DataType.WATER_SYSTEMS,
            fields=[],  # Empty means include all fields from extraction
            required=False,
            description="Complete water system information"
        )
        self.add_data_type_schema(water_systems_schema)

        # Legal Entities - include all fields
        legal_entities_schema = DataTypeSchema(
            data_type=DataType.LEGAL_ENTITIES,
            fields=[],  # Empty means include all fields from extraction
            required=False,
            description="Complete legal entity information"
        )
        self.add_data_type_schema(legal_entities_schema)

        # Sample Schedules - include all fields
        sample_schedules_schema = DataTypeSchema(
            data_type=DataType.SAMPLE_SCHEDULES,
            fields=[],  # Empty means include all fields from extraction
            required=False,
            description="Complete sample schedule information"
        )
        self.add_data_type_schema(sample_schedules_schema)

        # Deficiency Types - include all fields
        deficiency_types_schema = DataTypeSchema(
            data_type=DataType.DEFICIENCY_TYPES,
            fields=[],  # Empty means include all fields from extraction
            required=False,
            description="Complete deficiency type information"
        )
        self.add_data_type_schema(deficiency_types_schema)

    def is_include_all_fields_schema(self, data_type: DataType) -> bool:
        """General export always includes all fields"""
        return True
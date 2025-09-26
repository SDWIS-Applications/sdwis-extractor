"""
Inspection Report Schema

Defines the schema for inspection report exports with specific field selections
and hierarchical structure.
"""

from .base_schema import BaseExportSchema, DataType, DataTypeSchema, SchemaField, FieldType


class InspectionReportSchema(BaseExportSchema):
    """Schema for inspection report format"""

    def _initialize_schema(self):
        """Initialize inspection report schema with specific field selections"""

        # Water Systems schema for inspection reports
        water_systems_fields = [
            SchemaField(
                source_field="Water System No.",
                output_field="system_number",
                field_type=FieldType.STRING,
                required=True,
                description="Unique water system identifier"
            ),
            SchemaField(
                source_field="Name",
                output_field="system_name",
                field_type=FieldType.STRING,
                required=True,
                description="Water system name"
            ),
            SchemaField(
                source_field="Population",
                output_field="population",
                field_type=FieldType.INTEGER,
                required=False,
                description="Population served"
            ),
            SchemaField(
                source_field="County",
                output_field="county",
                field_type=FieldType.STRING,
                required=False,
                description="County location"
            ),
            SchemaField(
                source_field="Activity Status",
                output_field="activity_status",
                field_type=FieldType.STRING,
                required=False,
                description="Current activity status"
            ),
            SchemaField(
                source_field="Types",
                output_field="system_type",
                field_type=FieldType.STRING,
                required=False,
                description="System type classification"
            )
        ]

        water_systems_schema = DataTypeSchema(
            data_type=DataType.WATER_SYSTEMS,
            fields=water_systems_fields,
            required=False,
            description="Water system information for inspections"
        )
        self.add_data_type_schema(water_systems_schema)

        # Legal Entities schema for inspection reports
        legal_entities_fields = [
            SchemaField(
                source_field="Individual Name",
                output_field="entity_name",
                field_type=FieldType.STRING,
                required=True,
                description="Primary entity name"
            ),
            SchemaField(
                source_field="Status",
                output_field="status",
                field_type=FieldType.STRING,
                required=False,
                description="Entity status code"
            ),
            SchemaField(
                source_field="Organization",
                output_field="organization",
                field_type=FieldType.STRING,
                required=False,
                description="Organization name"
            ),
            SchemaField(
                source_field="State Code",
                output_field="state_code",
                field_type=FieldType.STRING,
                required=False,
                description="State code identifier"
            ),
            SchemaField(
                source_field="Mail Stop",
                output_field="mail_stop",
                field_type=FieldType.STRING,
                required=False,
                description="Mail stop identifier"
            ),
            SchemaField(
                source_field="ID Number",
                output_field="id_number",
                field_type=FieldType.STRING,
                required=False,
                description="Entity ID number"
            )
        ]

        legal_entities_schema = DataTypeSchema(
            data_type=DataType.LEGAL_ENTITIES,
            fields=legal_entities_fields,
            required=False,
            description="Legal entity information for inspections"
        )
        self.add_data_type_schema(legal_entities_schema)

        # Sample Schedules schema for inspection reports
        sample_schedules_fields = [
            SchemaField(
                source_field="Schedule ID",
                output_field="schedule_id",
                field_type=FieldType.STRING,
                required=True,
                description="Schedule identifier"
            ),
            SchemaField(
                source_field="PWS ID",
                output_field="pws_id",
                field_type=FieldType.STRING,
                required=True,
                description="Public water system ID"
            ),
            SchemaField(
                source_field="Facility ID",
                output_field="facility_id",
                field_type=FieldType.STRING,
                required=False,
                description="Facility identifier"
            ),
            SchemaField(
                source_field="Analyte Group",
                output_field="analyte_group",
                field_type=FieldType.STRING,
                required=False,
                description="Analyte group classification"
            )
        ]

        sample_schedules_schema = DataTypeSchema(
            data_type=DataType.SAMPLE_SCHEDULES,
            fields=sample_schedules_fields,
            required=False,
            description="Sample schedule information for inspections"
        )
        self.add_data_type_schema(sample_schedules_schema)

        # Deficiency Types schema for inspection reports
        deficiency_types_fields = [
            SchemaField(
                source_field="Type Code",
                output_field="code",
                field_type=FieldType.STRING,
                required=True,
                description="Deficiency type code"
            ),
            SchemaField(
                source_field="Default Severity Code",
                output_field="typical_severity",
                field_type=FieldType.STRING,
                required=False,
                description="Typical severity classification"
            ),
            SchemaField(
                source_field="Default Category Code",
                output_field="typical_category",
                field_type=FieldType.STRING,
                required=False,
                description="Typical category classification"
            ),
            SchemaField(
                source_field="Description",
                output_field="description",
                field_type=FieldType.STRING,
                required=False,
                description="Deficiency description"
            )
        ]

        deficiency_types_schema = DataTypeSchema(
            data_type=DataType.DEFICIENCY_TYPES,
            fields=deficiency_types_fields,
            required=False,
            description="Deficiency type information for inspections"
        )
        self.add_data_type_schema(deficiency_types_schema)
"""
Data Type Format Mapper - Domain Service

Maps data types to their corresponding output keys and field selections.
This encapsulates domain knowledge about data type representations.
"""

from typing import Dict, List, Optional
from .export_configuration import ExportMode


class DataTypeFormatMapper:
    """Domain service for data type format mappings"""

    @staticmethod
    def get_output_key_for_type(data_type: str) -> str:
        """
        Get the output key name for a given data type.

        Args:
            data_type: The internal data type name

        Returns:
            The appropriate output key for JSON structure
        """
        mappings = {
            "water_systems": "all_water_systems",
            "legal_entities": "legal_entities",
            "sample_schedules": "sample_schedules",
            "deficiency_types": "deficiency_types"
        }

        return mappings.get(data_type, f"all_{data_type}")

    @staticmethod
    def get_inspection_fields(data_type: str) -> List[str]:
        """
        Get the fields that should be included in inspection mode exports.

        Args:
            data_type: The data type to get fields for

        Returns:
            List of field names to include in inspection export
        """
        field_mappings = {
            "water_systems": [
                "system_number",
                "name",
                "activity_status",
                "population",
                "county",
                "sources",
                "types"
            ],
            "legal_entities": [
                "entity_id",
                "name",
                "status",
                "organization",
                "state_code"
            ],
            "sample_schedules": [
                "schedule_id",
                "facility_name",
                "analyte_group",
                "frequency",
                "start_date"
            ]
        }

        return field_mappings.get(data_type, [])

    @staticmethod
    def get_field_mappings_for_mode(data_type: str, export_mode: ExportMode) -> Dict[str, str]:
        """
        Get field name mappings for a specific export mode.

        Args:
            data_type: The data type to get mappings for
            export_mode: The export mode (general or inspection)

        Returns:
            Dictionary mapping original field names to output field names
        """
        if export_mode == ExportMode.INSPECTION:
            # Inspection mode uses standardized field names
            inspection_mappings = {
                "water_systems": {
                    "Water System No.": "system_number",
                    "Name": "name",
                    "Activity Status": "activity_status",
                    "Population": "population",
                    "County": "county",
                    "Sources": "sources",
                    "Types": "types"
                },
                "legal_entities": {
                    "ID Number": "entity_id",
                    "Name": "name",
                    "Status": "status",
                    "Organization": "organization",
                    "State Code": "state_code"
                },
                "sample_schedules": {
                    "Schedule ID": "schedule_id",
                    "Facility Name": "facility_name",
                    "Analyte Group": "analyte_group",
                    "Frequency": "frequency",
                    "Start Date": "start_date"
                }
            }
            return inspection_mappings.get(data_type, {})
        else:
            # General mode preserves original field names
            return {}

    @staticmethod
    def should_include_metadata_wrapper(export_mode: ExportMode) -> bool:
        """
        Determine if the export should include a metadata wrapper.

        Args:
            export_mode: The export mode

        Returns:
            True if metadata wrapper should be included
        """
        return export_mode == ExportMode.GENERAL

    @staticmethod
    def get_hierarchical_structure_for_inspection(data_types: List[str]) -> Dict[str, str]:
        """
        Get the hierarchical structure keys for inspection mode multi-type exports.

        Args:
            data_types: List of data types being exported

        Returns:
            Dictionary mapping data types to their hierarchical keys
        """
        structure_mappings = {
            "water_systems": "water_systems",
            "legal_entities": "legal_entities",
            "sample_schedules": "sample_schedules",
            "deficiency_types": "deficiency_types"
        }

        return {
            data_type: structure_mappings.get(data_type, data_type)
            for data_type in data_types
        }
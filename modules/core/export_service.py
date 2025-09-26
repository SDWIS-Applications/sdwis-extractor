"""
Export Service - Core business logic for data export formatting.

Handles transformation of extracted data according to export schemas.
"""

from pathlib import Path
from typing import Dict, List, Any, Optional
from enum import Enum

from .domain import ExtractionResult
from ..adapters.export_schema import SchemaLoader, ConfigurationSchema, SchemaValidationError


class ExportMode(Enum):
    """Export mode enumeration"""
    GENERAL = "general"
    INSPECTION = "inspection"


class ExportService:
    """Service for handling data export transformations"""

    def __init__(self, schema_directory: Optional[str] = None):
        """
        Initialize export service.

        Args:
            schema_directory: Path to schema configuration files
        """
        if schema_directory is None:
            # Default to config/schemas relative to project root
            project_root = Path(__file__).parent.parent.parent
            schema_directory = project_root / "config" / "schemas"

        self.schema_loader = SchemaLoader(str(schema_directory))
        self._cached_schemas: Dict[str, ConfigurationSchema] = {}

    def get_available_export_modes(self) -> List[str]:
        """Get list of available export modes"""
        return [mode.value for mode in ExportMode]

    def get_available_schemas(self) -> List[str]:
        """Get list of available export schemas"""
        return self.schema_loader.list_available_schemas()

    def get_default_format_for_mode(self, export_mode: ExportMode) -> str:
        """Get default output format for export mode"""
        if export_mode == ExportMode.INSPECTION:
            return "json"  # Only JSON for hierarchical inspection data
        else:
            return "csv"   # CSV default for general exports

    def get_supported_formats_for_mode(self, export_mode: ExportMode) -> List[str]:
        """Get supported output formats for export mode"""
        if export_mode == ExportMode.INSPECTION:
            return ["json"]  # Only JSON for inspection mode
        else:
            return ["csv", "json"]  # Both formats for general mode

    def prepare_export_data(
        self,
        extraction_result: ExtractionResult,
        export_mode: ExportMode = ExportMode.GENERAL,
        selected_data_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Prepare extracted data for export according to specified mode.

        Args:
            extraction_result: Result from data extraction
            export_mode: Export mode (general or inspection)
            selected_data_types: Specific data types to include (optional)

        Returns:
            Transformed data ready for output adapter

        Raises:
            SchemaValidationError: If schema operations fail
        """
        try:
            # Get schema for export mode
            schema = self._get_schema_for_mode(export_mode)

            # Prepare data structure based on extraction result
            source_data = {
                extraction_result.metadata.data_type: extraction_result.data
            }

            # Transform data according to schema
            transformed_data = schema.transform_data(source_data, selected_data_types)

            # For inspection mode, ensure hierarchical structure
            if export_mode == ExportMode.INSPECTION:
                return self._ensure_inspection_structure(transformed_data)
            else:
                return transformed_data

        except Exception as e:
            raise SchemaValidationError(f"Export data preparation failed: {str(e)}")

    def prepare_multi_type_export_data(
        self,
        extraction_results: Dict[str, ExtractionResult],
        export_mode: ExportMode = ExportMode.GENERAL,
        selected_data_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Prepare multiple extraction results for combined export.

        Args:
            extraction_results: Dictionary of data_type -> ExtractionResult
            export_mode: Export mode (general or inspection)
            selected_data_types: Specific data types to include (optional)

        Returns:
            Transformed combined data ready for output adapter

        Raises:
            SchemaValidationError: If schema operations fail
        """
        try:
            # Get schema for export mode
            schema = self._get_schema_for_mode(export_mode)

            # Combine all extraction results into source data structure
            source_data = {}
            for data_type, result in extraction_results.items():
                if selected_data_types is None or data_type in selected_data_types:
                    source_data[data_type] = result.data

            # Transform data according to schema
            transformed_data = schema.transform_data(source_data, selected_data_types)

            # For inspection mode, ensure hierarchical structure
            if export_mode == ExportMode.INSPECTION:
                return self._ensure_inspection_structure(transformed_data)
            else:
                return transformed_data

        except Exception as e:
            raise SchemaValidationError(f"Multi-type export data preparation failed: {str(e)}")

    def validate_export_request(
        self,
        export_mode: ExportMode,
        output_format: str,
        data_types: List[str]
    ) -> bool:
        """
        Validate export request parameters.

        Args:
            export_mode: Requested export mode
            output_format: Requested output format
            data_types: Requested data types

        Returns:
            True if request is valid, False otherwise
        """
        try:
            # Check if format is supported for mode
            supported_formats = self.get_supported_formats_for_mode(export_mode)
            if output_format not in supported_formats:
                return False

            # Check if schema exists for mode
            schema = self._get_schema_for_mode(export_mode)

            # Check if requested data types are supported
            supported_types = [dt.value for dt in schema.get_supported_data_types()]
            for data_type in data_types:
                if data_type not in supported_types:
                    return False

            return True

        except Exception:
            return False

    def get_export_schema_info(self, export_mode: ExportMode) -> Dict[str, Any]:
        """Get information about export schema for specified mode"""
        try:
            schema = self._get_schema_for_mode(export_mode)
            return schema.get_schema_summary()
        except Exception as e:
            return {
                "error": f"Failed to load schema info: {str(e)}",
                "export_mode": export_mode.value
            }

    def _get_schema_for_mode(self, export_mode: ExportMode) -> ConfigurationSchema:
        """Get schema configuration for export mode"""
        if export_mode == ExportMode.INSPECTION:
            schema_name = "inspection_report"
        else:
            schema_name = "general_export"

        # Use cached schema if available
        if schema_name in self._cached_schemas:
            return self._cached_schemas[schema_name]

        # Load schema
        schema = self.schema_loader.load_schema(schema_name)
        self._cached_schemas[schema_name] = schema

        return schema

    def _ensure_inspection_structure(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure inspection data has proper hierarchical structure.

        The inspection application expects a specific structure with
        top-level keys for each data type.
        """
        # For inspection mode, the structure should already be correct
        # from the schema transformation, but we can add validation here

        # Ensure we have the expected top-level structure
        inspection_data = {}

        # Add data types that are present
        for data_type in ["water_systems", "legal_entities", "sample_schedules", "deficiency_types"]:
            if data_type in data:
                inspection_data[data_type] = data[data_type]
            # Don't add empty arrays for missing data types
            # Let the consumer decide how to handle missing data

        return inspection_data

    def get_field_mappings_for_mode(self, export_mode: ExportMode) -> Dict[str, Dict[str, str]]:
        """
        Get field mappings for export mode.

        Returns mapping of data_type -> {source_field: output_field}
        """
        try:
            schema = self._get_schema_for_mode(export_mode)
            mappings = {}

            for data_type in schema.get_supported_data_types():
                schema_def = schema.get_data_type_schema(data_type)
                if schema_def:
                    mappings[data_type.value] = schema_def.get_field_mapping()

            return mappings
        except Exception as e:
            raise SchemaValidationError(f"Failed to get field mappings: {str(e)}")

    def preview_export_structure(
        self,
        sample_data: Dict[str, List[Dict[str, Any]]],
        export_mode: ExportMode,
        max_records_per_type: int = 2
    ) -> Dict[str, Any]:
        """
        Preview what export structure would look like with sample data.

        Args:
            sample_data: Sample extraction data
            export_mode: Export mode to preview
            max_records_per_type: Maximum records to include in preview

        Returns:
            Preview of export structure
        """
        try:
            schema = self._get_schema_for_mode(export_mode)

            # Limit sample data for preview
            limited_sample = {}
            for data_type, records in sample_data.items():
                limited_sample[data_type] = records[:max_records_per_type]

            # Transform sample data
            preview_data = schema.transform_data(limited_sample)

            # For inspection mode, ensure hierarchical structure
            if export_mode == ExportMode.INSPECTION:
                preview_data = self._ensure_inspection_structure(preview_data)

            return {
                "export_mode": export_mode.value,
                "structure": preview_data,
                "schema_info": schema.get_schema_summary(),
                "note": f"Preview limited to {max_records_per_type} records per data type"
            }

        except Exception as e:
            return {
                "error": f"Preview generation failed: {str(e)}",
                "export_mode": export_mode.value
            }
"""
Enhanced JSON Output Adapter

Extends the existing JSON output adapter to support export modes and schema-based formatting.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from ...core.domain import ExtractionResult
from ...core.ports import OutputError
from ...core.export_service import ExportService, ExportMode
from ...core.data_type_mapper import DataTypeFormatMapper


class EnhancedJSONOutputAdapter:
    """Enhanced JSON output adapter with export mode support"""

    def __init__(
        self,
        export_service: ExportService,
        export_mode: ExportMode = ExportMode.GENERAL,
        indent: int = 2,
        ensure_ascii: bool = False
    ):
        self.export_mode = export_mode
        self.export_service = export_service
        self.indent = indent
        self.ensure_ascii = ensure_ascii

    def get_supported_formats(self) -> List[str]:
        """Get supported output formats"""
        return ["json"]

    def validate_destination(self, destination: str, format_type: str) -> bool:
        """Validate destination path"""
        if format_type != "json":
            return False

        try:
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)
            return True
        except (OSError, PermissionError):
            return False

    async def save_data(self, result: ExtractionResult, destination: str) -> bool:
        """
        Save extraction result as JSON file with export mode formatting.
        """
        try:
            # Transform data according to export mode
            if self.export_mode == ExportMode.INSPECTION:
                output_data = await self._format_for_inspection(result)
            else:
                output_data = await self._format_for_general(result)

            # Ensure directory exists
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write JSON file
            with open(destination, 'w', encoding='utf-8') as f:
                json.dump(
                    output_data,
                    f,
                    indent=self.indent,
                    ensure_ascii=self.ensure_ascii,
                    default=self._json_serializer
                )

            return True

        except Exception as e:
            raise OutputError(f"Failed to save JSON to {destination}: {str(e)}")

    async def _format_for_inspection(self, result: ExtractionResult) -> Dict[str, Any]:
        """Format data for inspection report (hierarchical JSON)"""
        # Use export service to transform data
        transformed_data = self.export_service.prepare_export_data(
            result,
            ExportMode.INSPECTION
        )

        # Inspection format is purely the transformed data
        # No additional metadata wrapper
        return transformed_data

    async def _format_for_general(self, result: ExtractionResult) -> Dict[str, Any]:
        """Format data for general export (flat JSON with metadata)"""
        # Use export service to transform data
        transformed_data = self.export_service.prepare_export_data(
            result,
            ExportMode.GENERAL
        )

        # Create general export format with metadata
        # This maintains compatibility with existing JSON structure
        data_type = result.metadata.data_type

        # Use domain service to get data key
        data_key = DataTypeFormatMapper.get_output_key_for_type(data_type)

        # Build output structure
        output_data = {
            data_key: transformed_data.get(data_type, []),
            "extraction_summary": {
                "total_extracted": result.metadata.extracted_count,
                "expected_total": result.metadata.total_available,
                "extraction_time": f"{result.metadata.extraction_time:.2f}s",
                "timestamp": result.metadata.extraction_timestamp.isoformat(),
                "success": result.success,
                "export_mode": self.export_mode.value
            }
        }

        # Add additional metadata if present
        if result.metadata.source_info:
            output_data["extraction_summary"]["source_info"] = result.metadata.source_info

        if result.metadata.pagination_info:
            output_data["extraction_summary"]["pagination_info"] = result.metadata.pagination_info

        # Include errors and warnings if present
        if result.errors:
            output_data["extraction_summary"]["errors"] = result.errors

        if result.warnings:
            output_data["extraction_summary"]["warnings"] = result.warnings

        return output_data

    async def save_multi_type_data(
        self,
        extraction_results: Dict[str, ExtractionResult],
        destination: str,
        selected_data_types: Optional[List[str]] = None
    ) -> bool:
        """
        Save multiple extraction results as single JSON file.

        Args:
            extraction_results: Dictionary of data_type -> ExtractionResult
            destination: Output file path
            selected_data_types: Optional list of data types to include

        Returns:
            True if save successful

        Raises:
            OutputError: If save operation fails
        """
        try:
            # Transform data according to export mode
            if self.export_mode == ExportMode.INSPECTION:
                output_data = await self._format_multi_type_for_inspection(
                    extraction_results, selected_data_types
                )
            else:
                output_data = await self._format_multi_type_for_general(
                    extraction_results, selected_data_types
                )

            # Ensure directory exists
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write JSON file
            with open(destination, 'w', encoding='utf-8') as f:
                json.dump(
                    output_data,
                    f,
                    indent=self.indent,
                    ensure_ascii=self.ensure_ascii,
                    default=self._json_serializer
                )

            return True

        except Exception as e:
            raise OutputError(f"Failed to save multi-type JSON to {destination}: {str(e)}")

    async def _format_multi_type_for_inspection(
        self,
        extraction_results: Dict[str, ExtractionResult],
        selected_data_types: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Format multiple results for inspection report"""
        transformed_data = self.export_service.prepare_multi_type_export_data(
            extraction_results,
            ExportMode.INSPECTION,
            selected_data_types
        )

        return transformed_data

    async def _format_multi_type_for_general(
        self,
        extraction_results: Dict[str, ExtractionResult],
        selected_data_types: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Format multiple results for general export"""
        transformed_data = self.export_service.prepare_multi_type_export_data(
            extraction_results,
            ExportMode.GENERAL,
            selected_data_types
        )

        # Create combined summary
        total_extracted = sum(result.metadata.extracted_count for result in extraction_results.values())
        total_available = sum(
            result.metadata.total_available or 0
            for result in extraction_results.values()
        )

        # Build combined output structure
        output_data = dict(transformed_data)  # Copy the data
        output_data["extraction_summary"] = {
            "total_extracted": total_extracted,
            "total_available": total_available if total_available > 0 else None,
            "data_types": list(extraction_results.keys()),
            "timestamp": datetime.now().isoformat(),
            "export_mode": self.export_mode.value
        }

        # Add individual data type summaries
        output_data["data_type_summaries"] = {}
        for data_type, result in extraction_results.items():
            output_data["data_type_summaries"][data_type] = {
                "extracted_count": result.metadata.extracted_count,
                "extraction_time": result.metadata.extraction_time,
                "success": result.success
            }

        return output_data

    def _json_serializer(self, obj):
        """Custom JSON serializer for datetime objects"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def create_enhanced_json_adapter(
    export_service: ExportService,
    export_mode: str = "general",
    **kwargs
) -> EnhancedJSONOutputAdapter:
    """
    Factory function to create enhanced JSON output adapter.

    Args:
        export_service: The export service to inject
        export_mode: Export mode ("general" or "inspection")
        **kwargs: Additional arguments for the adapter

    Returns:
        Configured enhanced JSON output adapter
    """
    mode = ExportMode.INSPECTION if export_mode == "inspection" else ExportMode.GENERAL

    return EnhancedJSONOutputAdapter(export_service=export_service, export_mode=mode, **kwargs)
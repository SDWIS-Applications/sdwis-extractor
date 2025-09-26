"""
JSON Output Adapter

Maintains compatibility with existing JSON output format while providing
the flexibility to include additional metadata.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List

from ...core.domain import ExtractionResult
from ...core.ports import OutputError


class JSONOutputAdapter:
    """JSON output adapter compatible with existing format"""

    def __init__(self, indent: int = 2, ensure_ascii: bool = False):
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
            # Check if directory exists or can be created
            path.parent.mkdir(parents=True, exist_ok=True)
            return True
        except (OSError, PermissionError):
            return False

    async def save_data(self, result: ExtractionResult, destination: str) -> bool:
        """
        Save extraction result as JSON file.

        Maintains compatibility with existing JSON format while optionally
        including additional metadata.
        """
        try:
            # Prepare output data in format compatible with existing extractors
            output_data = self._format_for_compatibility(result)

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

    def _format_for_compatibility(self, result: ExtractionResult) -> dict:
        """
        Format result for compatibility with existing JSON structure.

        The existing extractors produce JSON in this format:
        {
            "all_water_systems": [...],
            "extraction_summary": {
                "total_extracted": int,
                "expected_total": int,
                "extraction_time": str,
                "timestamp": str
            }
        }
        """
        data_type = result.metadata.data_type

        # Create data key based on data type
        if data_type == "water_systems":
            data_key = "all_water_systems"
        elif data_type == "legal_entities":
            data_key = "legal_entities"
        elif data_type == "sample_schedules":
            data_key = "sample_schedules"
        else:
            data_key = f"all_{data_type}"

        # Build output structure compatible with existing format
        output_data = {
            data_key: result.data,
            "extraction_summary": {
                "total_extracted": result.metadata.extracted_count,
                "expected_total": result.metadata.total_available,
                "extraction_time": f"{result.metadata.extraction_time:.2f}s",
                "timestamp": result.metadata.extraction_timestamp.isoformat(),
                "success": result.success
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

    def _json_serializer(self, obj):
        """Custom JSON serializer for datetime objects"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class DetailedJSONOutputAdapter(JSONOutputAdapter):
    """Extended JSON output with full metadata"""

    def _format_for_compatibility(self, result: ExtractionResult) -> dict:
        """Include all available metadata in the output"""
        base_output = super()._format_for_compatibility(result)

        # Add comprehensive metadata
        base_output["metadata"] = {
            "extraction_metadata": {
                "extracted_count": result.metadata.extracted_count,
                "extraction_time": result.metadata.extraction_time,
                "data_type": result.metadata.data_type,
                "extraction_timestamp": result.metadata.extraction_timestamp.isoformat(),
                "total_available": result.metadata.total_available,
                "source_info": result.metadata.source_info,
                "pagination_info": result.metadata.pagination_info
            },
            "result_metadata": {
                "success": result.success,
                "record_count": result.record_count,
                "has_errors": result.has_errors,
                "has_warnings": result.has_warnings,
                "errors": result.errors,
                "warnings": result.warnings
            }
        }

        return base_output


class CompactJSONOutputAdapter(JSONOutputAdapter):
    """Compact JSON output with minimal metadata"""

    def __init__(self):
        super().__init__(indent=None, ensure_ascii=True)

    def _format_for_compatibility(self, result: ExtractionResult) -> dict:
        """Minimal output format"""
        data_type = result.metadata.data_type

        if data_type == "water_systems":
            data_key = "all_water_systems"
        elif data_type == "legal_entities":
            data_key = "legal_entities"
        elif data_type == "sample_schedules":
            data_key = "sample_schedules"
        else:
            data_key = f"all_{data_type}"

        return {
            data_key: result.data,
            "count": result.metadata.extracted_count,
            "timestamp": result.metadata.extraction_timestamp.isoformat()
        }


def create_json_output_adapter(output_type: str = "standard", **kwargs) -> JSONOutputAdapter:
    """
    Factory function to create JSON output adapter.

    Args:
        output_type: Type of JSON output ("standard", "detailed", "compact")
        **kwargs: Additional arguments for the adapter

    Returns:
        Configured JSON output adapter
    """
    if output_type == "standard":
        return JSONOutputAdapter(**kwargs)
    elif output_type == "detailed":
        return DetailedJSONOutputAdapter()
    elif output_type == "compact":
        return CompactJSONOutputAdapter()
    else:
        raise ValueError(f"Unknown output type: {output_type}")
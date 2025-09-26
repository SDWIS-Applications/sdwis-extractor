"""
Export Configuration Domain Objects

Domain objects for managing export configuration including filename generation,
format detection, and output policies.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from enum import Enum

from .export_service import ExportMode
from .exceptions import ExportConfigurationError, InvalidOutputFormatError


@dataclass
class FileNamingPolicy:
    """Policy for generating output filenames"""

    include_timestamp: bool = True
    timestamp_format: str = "%Y%m%d_%H%M%S"
    include_data_type: bool = True
    inspection_prefix: str = "inspection_app_dataset"

    def generate_filename(
        self,
        data_type: Optional[str],
        format_type: str,
        export_mode: ExportMode
    ) -> str:
        """Generate filename according to policy"""
        timestamp = datetime.now().strftime(self.timestamp_format) if self.include_timestamp else ""

        if export_mode == ExportMode.INSPECTION:
            base_name = self.inspection_prefix
            if timestamp:
                base_name = f"{base_name}_{timestamp}"
            return f"{base_name}.json"  # Inspection always JSON
        else:
            # General mode
            parts = []
            if data_type and self.include_data_type:
                parts.append(data_type)
            if timestamp:
                parts.append(timestamp)

            base_name = "_".join(parts) if parts else "output"
            extension = self._get_extension_for_format(format_type)
            return f"{base_name}.{extension}"

    def _get_extension_for_format(self, format_type: str) -> str:
        """Get file extension for format"""
        format_extensions = {
            'json': 'json',
            'csv': 'csv',
            'tsv': 'tsv'
        }
        return format_extensions.get(format_type, 'csv')


@dataclass
class ExportConfiguration:
    """Complete export configuration"""

    data_types: List[str]
    export_mode: ExportMode = ExportMode.GENERAL
    output_format: Optional[str] = None  # Auto-detect if None
    output_path: Optional[str] = None    # Auto-generate if None
    file_naming_policy: FileNamingPolicy = field(default_factory=FileNamingPolicy)

    def detect_format_from_path(self) -> str:
        """Detect format from output path extension"""
        if not self.output_path:
            return self._get_default_format()

        path = Path(self.output_path)
        extension = path.suffix.lower()

        format_map = {
            '.json': 'json',
            '.csv': 'csv',
            '.tsv': 'tsv'
        }

        return format_map.get(extension, self._get_default_format())

    def _get_default_format(self) -> str:
        """Get default format based on export mode"""
        if self.export_mode == ExportMode.INSPECTION:
            return 'json'  # Inspection always JSON
        else:
            return 'csv'   # General defaults to CSV

    def resolve_output_format(self) -> str:
        """Resolve the final output format"""
        if self.output_format:
            return self.output_format
        return self.detect_format_from_path()

    def generate_output_paths(self) -> List[str]:
        """Generate output file paths for all data types"""
        format_type = self.resolve_output_format()

        if self.export_mode == ExportMode.INSPECTION:
            # Single combined file for inspection
            if self.output_path:
                return [self.output_path]
            else:
                filename = self.file_naming_policy.generate_filename(
                    None, format_type, self.export_mode
                )
                return [filename]
        else:
            # Separate files for general mode
            if len(self.data_types) == 1:
                # Single data type
                if self.output_path:
                    return [self.output_path]
                else:
                    filename = self.file_naming_policy.generate_filename(
                        self.data_types[0], format_type, self.export_mode
                    )
                    return [filename]
            else:
                # Multiple data types - generate separate files
                timestamp = datetime.now().strftime(self.file_naming_policy.timestamp_format)
                output_paths = []

                for data_type in self.data_types:
                    if self.output_path:
                        # User provided path - modify it for each data type
                        base_path = Path(self.output_path)
                        base_stem = base_path.stem
                        extension = base_path.suffix or f'.{format_type}'

                        filename = f"{base_stem}_{data_type}_{timestamp}{extension}"
                        output_path = str(base_path.parent / filename)
                    else:
                        # Auto-generate
                        filename = self.file_naming_policy.generate_filename(
                            data_type, format_type, self.export_mode
                        )
                        output_path = filename

                    output_paths.append(output_path)

                return output_paths

    def validate(self) -> bool:
        """Validate export configuration"""
        try:
            self.validate_or_raise()
            return True
        except ExportConfigurationError:
            return False

    def validate_or_raise(self) -> None:
        """Validate export configuration, raising domain exception on failure"""
        errors = self.get_validation_errors()
        if errors:
            raise ExportConfigurationError(
                "Export configuration validation failed",
                configuration_errors=errors
            )

    def get_validation_errors(self) -> List[str]:
        """Get detailed validation errors"""
        errors = []

        if not self.data_types:
            errors.append("No data types specified")

        if self.export_mode == ExportMode.INSPECTION:
            # Validate format
            resolved_format = self.resolve_output_format()
            if resolved_format != 'json':
                errors.append(f"Inspection mode only supports JSON format, got: {resolved_format}")

            # Validate data types - only allow data types with implemented extractors
            allowed_types = {'water_systems', 'legal_entities', 'deficiency_types'}  # Types with implemented extractors
            invalid_types = [dt for dt in self.data_types if dt not in allowed_types]
            if invalid_types:
                errors.append(
                    f"Inspection mode only supports {', '.join(sorted(allowed_types))}. "
                    f"Invalid data types: {', '.join(invalid_types)}"
                )

        # Validate output paths
        if self.output_path:
            try:
                path = Path(self.output_path)
                # Check if parent directory is accessible
                if not path.parent.exists() and not path.parent == Path('.'):
                    try:
                        path.parent.mkdir(parents=True, exist_ok=True)
                    except (OSError, PermissionError):
                        errors.append(f"Cannot create output directory: {path.parent}")
            except Exception as e:
                errors.append(f"Invalid output path: {self.output_path} ({str(e)})")

        return errors
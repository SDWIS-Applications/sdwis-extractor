"""
Enhanced CSV Output Adapter

Extends the existing CSV output adapter to support export modes and schema-based formatting.
"""

import csv
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from ...core.domain import ExtractionResult
from ...core.ports import OutputError
from ...core.export_service import ExportService, ExportMode


class EnhancedCSVOutputAdapter:
    """Enhanced CSV output adapter with export mode support"""

    def __init__(
        self,
        export_service: ExportService,
        export_mode: ExportMode = ExportMode.GENERAL,
        use_pandas: bool = True,
        include_metadata: bool = False,
        delimiter: str = ',',
        encoding: str = 'utf-8'
    ):
        self.export_mode = export_mode
        self.export_service = export_service
        self.use_pandas = use_pandas and PANDAS_AVAILABLE
        self.include_metadata = include_metadata
        self.delimiter = delimiter
        self.encoding = encoding

    def get_supported_formats(self) -> List[str]:
        """Get supported output formats"""
        return ["csv"]

    def validate_destination(self, destination: str, format_type: str) -> bool:
        """Validate destination path"""
        if format_type != "csv":
            return False

        try:
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)
            return True
        except (OSError, PermissionError):
            return False

    async def save_data(self, result: ExtractionResult, destination: str) -> bool:
        """Save extraction result as CSV file with export mode formatting"""
        try:
            # Transform data according to export mode
            transformed_data = self.export_service.prepare_export_data(
                result,
                self.export_mode
            )

            # Ensure directory exists
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)

            if self.use_pandas:
                return await self._save_with_pandas(result, transformed_data, destination)
            else:
                return await self._save_with_csv_module(result, transformed_data, destination)

        except Exception as e:
            raise OutputError(f"Failed to save CSV to {destination}: {str(e)}")

    async def _save_with_pandas(
        self,
        result: ExtractionResult,
        transformed_data: Dict[str, Any],
        destination: str
    ) -> bool:
        """Save using pandas DataFrame"""
        try:
            # Get the data for the specific data type
            data_type = result.metadata.data_type
            records = transformed_data.get(data_type, [])

            if not records:
                # Create empty DataFrame with metadata
                df = pd.DataFrame()
            else:
                # Flatten nested dictionaries if present
                flattened_data = [self._flatten_record(record) for record in records]
                df = pd.DataFrame(flattened_data)

            # Add metadata as additional rows if requested
            if self.include_metadata:
                metadata_rows = self._create_metadata_rows(result)
                if metadata_rows:
                    metadata_df = pd.DataFrame(metadata_rows)
                    # Add empty row separator
                    separator_df = pd.DataFrame([{}])
                    df = pd.concat([metadata_df, separator_df, df], ignore_index=True)

            # Save to CSV
            df.to_csv(
                destination,
                index=False,
                sep=self.delimiter,
                encoding=self.encoding,
                na_rep='',  # Replace NaN with empty string
                escapechar='\\'
            )

            return True

        except Exception as e:
            raise OutputError(f"Pandas CSV save failed: {str(e)}")

    async def _save_with_csv_module(
        self,
        result: ExtractionResult,
        transformed_data: Dict[str, Any],
        destination: str
    ) -> bool:
        """Save using Python csv module"""
        try:
            # Get the data for the specific data type
            data_type = result.metadata.data_type
            records = transformed_data.get(data_type, [])

            if not records:
                # Create empty CSV with metadata
                with open(destination, 'w', newline='', encoding=self.encoding) as csvfile:
                    writer = csv.writer(csvfile, delimiter=self.delimiter)
                    if self.include_metadata:
                        metadata_rows = self._create_metadata_rows(result)
                        for row in metadata_rows:
                            if row:  # Skip empty rows
                                writer.writerow([f"{k}={v}" for k, v in row.items()])
                return True

            # Flatten data and determine all possible fieldnames
            flattened_data = [self._flatten_record(record) for record in records]
            all_fields = set()
            for record in flattened_data:
                all_fields.update(record.keys())

            fieldnames = sorted(list(all_fields))

            with open(destination, 'w', newline='', encoding=self.encoding) as csvfile:
                writer = csv.DictWriter(
                    csvfile,
                    fieldnames=fieldnames,
                    delimiter=self.delimiter,
                    extrasaction='ignore'
                )

                # Write metadata first if requested
                if self.include_metadata:
                    metadata_rows = self._create_metadata_rows(result)
                    for row in metadata_rows:
                        if row:  # Skip empty rows
                            # Write metadata as key=value pairs in first column
                            metadata_line = {fieldnames[0]: ", ".join([f"{k}={v}" for k, v in row.items()])}
                            writer.writerow(metadata_line)
                    # Empty separator row
                    writer.writerow({})

                # Write header
                writer.writeheader()

                # Write data
                for record in flattened_data:
                    writer.writerow(record)

            return True

        except Exception as e:
            raise OutputError(f"CSV module save failed: {str(e)}")

    async def save_multi_type_data(
        self,
        extraction_results: Dict[str, ExtractionResult],
        destination: str,
        selected_data_types: Optional[List[str]] = None
    ) -> bool:
        """
        Save multiple extraction results as single CSV file.

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
            transformed_data = self.export_service.prepare_multi_type_export_data(
                extraction_results,
                self.export_mode,
                selected_data_types
            )

            # Combine all records with data type prefix
            combined_records = []
            for data_type, records in transformed_data.items():
                if selected_data_types is None or data_type in selected_data_types:
                    for record in records:
                        # Add data type as a field
                        record_with_type = {"data_type": data_type, **record}
                        combined_records.append(record_with_type)

            if not combined_records:
                # Create empty file
                Path(destination).touch()
                return True

            # Use pandas if available for multi-type export
            if self.use_pandas:
                df = pd.DataFrame(combined_records)
                df.to_csv(
                    destination,
                    index=False,
                    sep=self.delimiter,
                    encoding=self.encoding,
                    na_rep='',
                    escapechar='\\'
                )
            else:
                # Use csv module
                flattened_data = [self._flatten_record(record) for record in combined_records]
                all_fields = set()
                for record in flattened_data:
                    all_fields.update(record.keys())

                fieldnames = sorted(list(all_fields))

                with open(destination, 'w', newline='', encoding=self.encoding) as csvfile:
                    writer = csv.DictWriter(
                        csvfile,
                        fieldnames=fieldnames,
                        delimiter=self.delimiter,
                        extrasaction='ignore'
                    )

                    writer.writeheader()
                    for record in flattened_data:
                        writer.writerow(record)

            return True

        except Exception as e:
            raise OutputError(f"Failed to save multi-type CSV to {destination}: {str(e)}")

    def _flatten_record(self, record: Dict[str, Any], parent_key: str = '', separator: str = '_') -> Dict[str, Any]:
        """
        Flatten nested dictionary for CSV compatibility.
        """
        items = []
        for k, v in record.items():
            new_key = f"{parent_key}{separator}{k}" if parent_key else k

            if isinstance(v, dict):
                items.extend(self._flatten_record(v, new_key, separator).items())
            elif isinstance(v, list):
                # Convert lists to comma-separated strings
                items.append((new_key, ', '.join(str(item) for item in v)))
            else:
                items.append((new_key, v))

        return dict(items)

    def _create_metadata_rows(self, result: ExtractionResult) -> List[Dict[str, str]]:
        """Create metadata rows for inclusion in CSV"""
        metadata_rows = []

        # Basic extraction info
        metadata_rows.append({
            'Metadata': 'Extraction Summary',
            'Data Type': result.metadata.data_type,
            'Success': str(result.success),
            'Extracted Count': str(result.metadata.extracted_count),
            'Export Mode': self.export_mode.value
        })

        if result.metadata.total_available:
            metadata_rows.append({
                'Metadata': 'Total Available',
                'Value': str(result.metadata.total_available)
            })

        metadata_rows.append({
            'Metadata': 'Extraction Time',
            'Value': f"{result.metadata.extraction_time:.2f} seconds"
        })

        metadata_rows.append({
            'Metadata': 'Timestamp',
            'Value': result.metadata.extraction_timestamp.isoformat()
        })

        # Errors and warnings
        if result.errors:
            for i, error in enumerate(result.errors):
                metadata_rows.append({
                    'Metadata': f'Error {i+1}',
                    'Value': error
                })

        if result.warnings:
            for i, warning in enumerate(result.warnings):
                metadata_rows.append({
                    'Metadata': f'Warning {i+1}',
                    'Value': warning
                })

        # Empty row separator
        metadata_rows.append({})

        return metadata_rows


class EnhancedTSVOutputAdapter(EnhancedCSVOutputAdapter):
    """Enhanced tab-separated values output adapter"""

    def __init__(self, export_service: ExportService, **kwargs):
        kwargs['delimiter'] = '\t'
        super().__init__(export_service, **kwargs)

    def get_supported_formats(self) -> List[str]:
        """Get supported output formats"""
        return ["tsv"]

    def validate_destination(self, destination: str, format_type: str) -> bool:
        """Validate destination path"""
        if format_type != "tsv":
            return False
        return super().validate_destination(destination, "csv")


def create_enhanced_csv_adapter(
    export_service: ExportService,
    export_mode: str = "general",
    output_type: str = "standard",
    **kwargs
) -> EnhancedCSVOutputAdapter:
    """
    Factory function to create enhanced CSV output adapter.

    Args:
        export_service: The export service to inject
        export_mode: Export mode ("general" or "inspection")
        output_type: Type of CSV output ("standard", "with_metadata", "tsv")
        **kwargs: Additional arguments for the adapter

    Returns:
        Configured enhanced CSV output adapter
    """
    mode = ExportMode.INSPECTION if export_mode == "inspection" else ExportMode.GENERAL

    if output_type == "with_metadata":
        kwargs['include_metadata'] = True
    elif output_type == "tsv":
        return EnhancedTSVOutputAdapter(export_service=export_service, export_mode=mode, **kwargs)

    return EnhancedCSVOutputAdapter(export_service=export_service, export_mode=mode, **kwargs)
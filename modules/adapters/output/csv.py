"""
CSV Output Adapter

Provides CSV export functionality for spreadsheet compatibility.
"""

import csv
import os
from pathlib import Path
from typing import List, Dict, Any

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from ...core.domain import ExtractionResult
from ...core.ports import OutputError


class CSVOutputAdapter:
    """CSV output adapter for spreadsheet compatibility"""

    def __init__(
        self,
        use_pandas: bool = True,
        include_metadata: bool = False,
        delimiter: str = ',',
        encoding: str = 'utf-8'
    ):
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
        """Save extraction result as CSV file"""
        try:
            # Ensure directory exists
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)

            if self.use_pandas:
                return await self._save_with_pandas(result, destination)
            else:
                return await self._save_with_csv_module(result, destination)

        except Exception as e:
            raise OutputError(f"Failed to save CSV to {destination}: {str(e)}")

    async def _save_with_pandas(self, result: ExtractionResult, destination: str) -> bool:
        """Save using pandas DataFrame"""
        try:
            if not result.data:
                # Create empty DataFrame with metadata
                df = pd.DataFrame()
            else:
                # Flatten nested dictionaries if present
                flattened_data = [self._flatten_record(record) for record in result.data]
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

    async def _save_with_csv_module(self, result: ExtractionResult, destination: str) -> bool:
        """Save using Python csv module"""
        try:
            if not result.data:
                # Create empty CSV with headers
                with open(destination, 'w', newline='', encoding=self.encoding) as csvfile:
                    writer = csv.writer(csvfile, delimiter=self.delimiter)
                    if self.include_metadata:
                        metadata_rows = self._create_metadata_rows(result)
                        for row in metadata_rows:
                            if row:  # Skip empty rows
                                writer.writerow([f"{k}={v}" for k, v in row.items()])
                return True

            # Flatten data and determine all possible fieldnames
            flattened_data = [self._flatten_record(record) for record in result.data]
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

    def _flatten_record(self, record: Dict[str, Any], parent_key: str = '', separator: str = '_') -> Dict[str, Any]:
        """
        Flatten nested dictionary for CSV compatibility.

        Args:
            record: Dictionary to flatten
            parent_key: Parent key for nested items
            separator: Separator for nested keys

        Returns:
            Flattened dictionary
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
            'Extracted Count': str(result.metadata.extracted_count)
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


class TSVOutputAdapter(CSVOutputAdapter):
    """Tab-separated values output adapter"""

    def __init__(self, **kwargs):
        kwargs['delimiter'] = '\t'
        super().__init__(**kwargs)

    def get_supported_formats(self) -> List[str]:
        """Get supported output formats"""
        return ["tsv"]

    def validate_destination(self, destination: str, format_type: str) -> bool:
        """Validate destination path"""
        if format_type != "tsv":
            return False
        return super().validate_destination(destination, "csv")


def create_csv_output_adapter(
    output_type: str = "standard",
    **kwargs
) -> CSVOutputAdapter:
    """
    Factory function to create CSV output adapter.

    Args:
        output_type: Type of CSV output ("standard", "with_metadata", "tsv")
        **kwargs: Additional arguments for the adapter

    Returns:
        Configured CSV output adapter
    """
    if output_type == "standard":
        return CSVOutputAdapter(**kwargs)
    elif output_type == "with_metadata":
        return CSVOutputAdapter(include_metadata=True, **kwargs)
    elif output_type == "tsv":
        return TSVOutputAdapter(**kwargs)
    else:
        raise ValueError(f"Unknown output type: {output_type}")
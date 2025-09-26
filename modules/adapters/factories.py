"""
Output Adapter Factory

Infrastructure layer factory for creating output adapters with proper dependency injection.
This factory enables the core layer to create adapters without importing concrete implementations.
"""

from typing import Optional, Dict, Any
from ..core.ports import OutputPort
from ..core.export_service import ExportService, ExportMode
from ..core.exceptions import InvalidOutputFormatError, ErrorTranslator, ErrorBoundary
from .output.enhanced_json import EnhancedJSONOutputAdapter
from .output.enhanced_csv import EnhancedCSVOutputAdapter


class OutputAdapterFactory:
    """Factory for creating output adapters with proper dependency injection"""

    def __init__(self, export_service: ExportService):
        """
        Initialize factory with required dependencies.

        Args:
            export_service: The export service to inject into adapters
        """
        self.export_service = export_service

    def create_adapter(
        self,
        format_type: str,
        export_mode: ExportMode = ExportMode.GENERAL,
        **kwargs
    ) -> OutputPort:
        """
        Create an output adapter for the specified format.

        Args:
            format_type: The output format ("json", "csv", "tsv")
            export_mode: The export mode (general or inspection)
            **kwargs: Additional adapter-specific configuration

        Returns:
            Configured output adapter instance

        Raises:
            InvalidOutputFormatError: If format_type is not supported
        """
        with ErrorBoundary("OutputAdapterFactory.create_adapter",
                          {"format_type": format_type, "export_mode": export_mode.value}):
            try:
                if format_type == "json":
                    return EnhancedJSONOutputAdapter(
                        export_service=self.export_service,
                        export_mode=export_mode,
                        **kwargs
                    )
                elif format_type == "csv":
                    return EnhancedCSVOutputAdapter(
                        export_service=self.export_service,
                        export_mode=export_mode,
                        delimiter=',',
                        **kwargs
                    )
                elif format_type == "tsv":
                    return EnhancedCSVOutputAdapter(
                        export_service=self.export_service,
                        export_mode=export_mode,
                        delimiter='\t',
                        **kwargs
                    )
                else:
                    raise InvalidOutputFormatError(format_type, self.get_supported_formats())
            except Exception as e:
                if isinstance(e, InvalidOutputFormatError):
                    raise
                # Translate infrastructure errors to domain errors
                raise ErrorTranslator.translate_output_error(e, format_type, self.get_supported_formats())

    def get_supported_formats(self) -> list[str]:
        """Get list of supported output formats"""
        return ["json", "csv", "tsv"]

    def create_json_adapter(
        self,
        export_mode: ExportMode = ExportMode.GENERAL,
        **kwargs
    ) -> EnhancedJSONOutputAdapter:
        """Create specifically configured JSON adapter"""
        return EnhancedJSONOutputAdapter(
            export_service=self.export_service,
            export_mode=export_mode,
            **kwargs
        )

    def create_csv_adapter(
        self,
        export_mode: ExportMode = ExportMode.GENERAL,
        include_metadata: bool = False,
        **kwargs
    ) -> EnhancedCSVOutputAdapter:
        """Create specifically configured CSV adapter"""
        return EnhancedCSVOutputAdapter(
            export_service=self.export_service,
            export_mode=export_mode,
            include_metadata=include_metadata,
            delimiter=',',
            **kwargs
        )

    def create_tsv_adapter(
        self,
        export_mode: ExportMode = ExportMode.GENERAL,
        include_metadata: bool = False,
        **kwargs
    ) -> EnhancedCSVOutputAdapter:
        """Create specifically configured TSV adapter"""
        return EnhancedCSVOutputAdapter(
            export_service=self.export_service,
            export_mode=export_mode,
            include_metadata=include_metadata,
            delimiter='\t',
            **kwargs
        )
"""
Factory Port Interfaces

Defines port interfaces for factory patterns, enabling complete abstraction
of adapter creation and dependency management.
"""

from typing import Protocol, List, Dict, Any, Optional
from .ports import OutputPort
from .export_service import ExportMode


class OutputAdapterFactoryPort(Protocol):
    """Port interface for output adapter factories"""

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
        ...

    def get_supported_formats(self) -> List[str]:
        """Get list of supported output formats"""
        ...

    def create_json_adapter(
        self,
        export_mode: ExportMode = ExportMode.GENERAL,
        **kwargs
    ) -> OutputPort:
        """Create specifically configured JSON adapter"""
        ...

    def create_csv_adapter(
        self,
        export_mode: ExportMode = ExportMode.GENERAL,
        include_metadata: bool = False,
        **kwargs
    ) -> OutputPort:
        """Create specifically configured CSV adapter"""
        ...


class AdapterRegistryPort(Protocol):
    """Port interface for adapter registries"""

    def register_output_adapter_factory(self, factory_name: str, factory_instance: OutputAdapterFactoryPort) -> None:
        """Register an output adapter factory instance"""
        ...

    def get_output_adapter_factory(self, factory_name: str = "default") -> OutputAdapterFactoryPort:
        """Get registered output adapter factory"""
        ...

    def create_output_adapter_via_factory(
        self,
        format_type: str,
        factory_name: str = "default",
        **kwargs
    ) -> OutputPort:
        """Create output adapter using registered factory"""
        ...

    def list_supported_output_formats(self) -> List[str]:
        """Get list of all supported output formats"""
        ...


class ExportOrchestrationPort(Protocol):
    """Port interface for export orchestration services"""

    async def perform_configured_export(
        self,
        export_config: 'ExportConfiguration'
    ) -> Dict[str, Any]:
        """
        Perform export operation based on configuration.

        Args:
            export_config: Complete export configuration

        Returns:
            Dictionary with operation results
        """
        ...

    async def validate_export_request(
        self,
        export_config: 'ExportConfiguration'
    ) -> Dict[str, Any]:
        """Validate export request and provide feedback"""
        ...


class DataTypeMapperPort(Protocol):
    """Port interface for data type mapping services"""

    def get_output_key_for_type(self, data_type: str) -> str:
        """Get the output key name for a given data type"""
        ...

    def get_inspection_fields(self, data_type: str) -> List[str]:
        """Get the fields that should be included in inspection mode exports"""
        ...

    def get_field_mappings_for_mode(self, data_type: str, export_mode: ExportMode) -> Dict[str, str]:
        """Get field name mappings for a specific export mode"""
        ...

    def should_include_metadata_wrapper(self, export_mode: ExportMode) -> bool:
        """Determine if the export should include a metadata wrapper"""
        ...


class ValidationPort(Protocol):
    """Port interface for validation services"""

    def validate_export_configuration(self, config: 'ExportConfiguration') -> Dict[str, Any]:
        """
        Validate export configuration with detailed feedback.

        Returns:
            Dictionary with validation results including errors, warnings, and suggestions
        """
        ...

    def suggest_configuration_corrections(self, errors: List[str]) -> List[str]:
        """Suggest corrections for configuration errors"""
        ...

    def validate_data_type_compatibility(self, data_types: List[str], export_mode: ExportMode) -> Dict[str, Any]:
        """Validate data type compatibility with export mode"""
        ...


class EventPublisherPort(Protocol):
    """Port interface for domain event publishing"""

    async def publish_export_started(self, event: 'ExportStartedEvent') -> None:
        """Publish export started event"""
        ...

    async def publish_export_progress(self, event: 'ExportProgressEvent') -> None:
        """Publish export progress event"""
        ...

    async def publish_export_completed(self, event: 'ExportCompletedEvent') -> None:
        """Publish export completed event"""
        ...

    async def publish_export_failed(self, event: 'ExportFailedEvent') -> None:
        """Publish export failed event"""
        ...


class SchemaManagerPort(Protocol):
    """Port interface for schema management services"""

    def load_schema(self, schema_name: str, version: Optional[str] = None) -> Dict[str, Any]:
        """Load export schema by name and version"""
        ...

    def validate_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate schema structure and content"""
        ...

    def migrate_schema(self, schema: Dict[str, Any], from_version: str, to_version: str) -> Dict[str, Any]:
        """Migrate schema from one version to another"""
        ...

    def get_available_schemas(self) -> List[Dict[str, Any]]:
        """Get list of available schemas with metadata"""
        ...

    def get_schema_versions(self, schema_name: str) -> List[str]:
        """Get available versions for a schema"""
        ...
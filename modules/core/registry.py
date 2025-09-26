"""
Adapter registry for dynamic discovery and management of SDWIS adapters.

Provides a centralized registry for managing different types of adapters
(extractors, output formats, authentication methods, etc.) with automatic
discovery and factory patterns.
"""

from typing import Dict, List, Type, Callable, Optional, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .ports import ExtractionPort, OutputPort, ProgressReportingPort, AuthenticatedBrowserSessionPort


@dataclass
class AdapterInfo:
    """Metadata about a registered adapter"""
    name: str
    adapter_type: str
    factory: Callable
    description: str
    supported_features: List[str]
    dependencies: List[str]
    priority: int = 0  # Higher priority adapters are preferred


class AdapterRegistryError(Exception):
    """Exception raised when adapter registry operations fail"""
    pass


class AdapterRegistry:
    """
    Centralized registry for all SDWIS adapters.

    Supports dynamic discovery, factory patterns, and adapter metadata management.
    """

    def __init__(self):
        self._extractors: Dict[str, AdapterInfo] = {}
        self._output_adapters: Dict[str, AdapterInfo] = {}
        self._output_adapter_factories: Dict[str, Any] = {}  # Factory instances
        self._progress_adapters: Dict[str, AdapterInfo] = {}
        self._browser_session_factories: Dict[str, AdapterInfo] = {}
        self._config_adapters: Dict[str, AdapterInfo] = {}

    # Extractor Registration
    def register_extractor(
        self,
        data_type: str,
        factory: Callable[[], ExtractionPort],
        name: Optional[str] = None,
        description: str = "",
        supported_features: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
        priority: int = 0
    ) -> None:
        """
        Register an extractor adapter.

        Args:
            data_type: Type of data this extractor handles
            factory: Factory function that creates the extractor
            name: Human-readable name
            description: Description of the extractor
            supported_features: List of features this extractor supports
            dependencies: List of required dependencies
            priority: Priority for selection (higher = preferred)
        """
        info = AdapterInfo(
            name=name or data_type,
            adapter_type="extractor",
            factory=factory,
            description=description,
            supported_features=supported_features or [],
            dependencies=dependencies or [],
            priority=priority
        )
        self._extractors[data_type] = info

    def get_extractor(self, data_type: str) -> ExtractionPort:
        """
        Get an extractor for the specified data type.

        Args:
            data_type: Type of data to extract

        Returns:
            Configured extractor instance

        Raises:
            AdapterRegistryError: If no extractor found for data type
        """
        if data_type not in self._extractors:
            available = list(self._extractors.keys())
            raise AdapterRegistryError(
                f"No extractor registered for data type '{data_type}'. "
                f"Available types: {available}"
            )

        adapter_info = self._extractors[data_type]
        try:
            return adapter_info.factory()
        except Exception as e:
            raise AdapterRegistryError(
                f"Failed to create extractor for '{data_type}': {e}"
            )

    def list_supported_data_types(self) -> List[str]:
        """Get list of all supported data types"""
        return sorted(self._extractors.keys())

    def get_extractor_info(self, data_type: str) -> Optional[AdapterInfo]:
        """Get metadata about a registered extractor"""
        return self._extractors.get(data_type)

    # Output Adapter Registration
    def register_output_adapter(
        self,
        format_name: str,
        factory: Callable[..., OutputPort],
        name: Optional[str] = None,
        description: str = "",
        supported_features: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
        priority: int = 0
    ) -> None:
        """Register an output format adapter"""
        info = AdapterInfo(
            name=name or format_name,
            adapter_type="output",
            factory=factory,
            description=description,
            supported_features=supported_features or [],
            dependencies=dependencies or [],
            priority=priority
        )
        self._output_adapters[format_name] = info

    def get_output_adapter(self, format_name: str, **kwargs) -> OutputPort:
        """
        Get an output adapter for the specified format.

        Args:
            format_name: Output format name
            **kwargs: Configuration parameters for the adapter

        Returns:
            Configured output adapter instance

        Raises:
            AdapterRegistryError: If no adapter found for format
        """
        if format_name not in self._output_adapters:
            available = list(self._output_adapters.keys())
            raise AdapterRegistryError(
                f"No output adapter registered for format '{format_name}'. "
                f"Available formats: {available}"
            )

        adapter_info = self._output_adapters[format_name]
        try:
            return adapter_info.factory(**kwargs)
        except Exception as e:
            raise AdapterRegistryError(
                f"Failed to create output adapter for '{format_name}': {e}"
            )

    def list_supported_output_formats(self) -> List[str]:
        """Get list of all supported output formats"""
        return sorted(self._output_adapters.keys())

    # Output Adapter Factory Management
    def register_output_adapter_factory(self, factory_name: str, factory_instance: Any) -> None:
        """Register an output adapter factory instance"""
        self._output_adapter_factories[factory_name] = factory_instance

    def get_output_adapter_factory(self, factory_name: str = "default") -> Any:
        """Get registered output adapter factory"""
        if factory_name not in self._output_adapter_factories:
            raise AdapterRegistryError(f"Output adapter factory '{factory_name}' not registered")
        return self._output_adapter_factories[factory_name]

    def create_output_adapter_via_factory(
        self,
        format_type: str,
        factory_name: str = "default",
        **kwargs
    ) -> OutputPort:
        """Create output adapter using registered factory"""
        factory = self.get_output_adapter_factory(factory_name)
        return factory.create_adapter(format_type, **kwargs)

    # Progress Adapter Registration
    def register_progress_adapter(
        self,
        progress_type: str,
        factory: Callable[..., ProgressReportingPort],
        name: Optional[str] = None,
        description: str = "",
        supported_features: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
        priority: int = 0
    ) -> None:
        """Register a progress reporting adapter"""
        info = AdapterInfo(
            name=name or progress_type,
            adapter_type="progress",
            factory=factory,
            description=description,
            supported_features=supported_features or [],
            dependencies=dependencies or [],
            priority=priority
        )
        self._progress_adapters[progress_type] = info

    def get_progress_adapter(self, progress_type: str, **kwargs) -> ProgressReportingPort:
        """Get a progress reporting adapter"""
        if progress_type not in self._progress_adapters:
            available = list(self._progress_adapters.keys())
            raise AdapterRegistryError(
                f"No progress adapter registered for type '{progress_type}'. "
                f"Available types: {available}"
            )

        adapter_info = self._progress_adapters[progress_type]
        try:
            return adapter_info.factory(**kwargs)
        except Exception as e:
            raise AdapterRegistryError(
                f"Failed to create progress adapter for '{progress_type}': {e}"
            )

    def list_supported_progress_types(self) -> List[str]:
        """Get list of all supported progress types"""
        return sorted(self._progress_adapters.keys())

    # Browser Session Factory Registration
    def register_browser_session_factory(
        self,
        session_type: str,
        factory: Callable[..., AuthenticatedBrowserSessionPort],
        name: Optional[str] = None,
        description: str = "",
        supported_features: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
        priority: int = 0
    ) -> None:
        """Register a browser session factory"""
        info = AdapterInfo(
            name=name or session_type,
            adapter_type="browser_session",
            factory=factory,
            description=description,
            supported_features=supported_features or [],
            dependencies=dependencies or [],
            priority=priority
        )
        self._browser_session_factories[session_type] = info

    def get_browser_session_factory(self, session_type: str) -> Callable[..., AuthenticatedBrowserSessionPort]:
        """Get a browser session factory"""
        if session_type not in self._browser_session_factories:
            available = list(self._browser_session_factories.keys())
            raise AdapterRegistryError(
                f"No browser session factory registered for type '{session_type}'. "
                f"Available types: {available}"
            )

        return self._browser_session_factories[session_type].factory

    def list_supported_browser_session_types(self) -> List[str]:
        """Get list of all supported browser session types"""
        return sorted(self._browser_session_factories.keys())

    # Configuration Adapter Registration
    def register_config_adapter(
        self,
        config_type: str,
        factory: Callable[..., Any],
        name: Optional[str] = None,
        description: str = "",
        supported_features: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
        priority: int = 0
    ) -> None:
        """Register a configuration adapter"""
        info = AdapterInfo(
            name=name or config_type,
            adapter_type="config",
            factory=factory,
            description=description,
            supported_features=supported_features or [],
            dependencies=dependencies or [],
            priority=priority
        )
        self._config_adapters[config_type] = info

    def get_config_adapter(self, config_type: str, **kwargs) -> Any:
        """Get a configuration adapter"""
        if config_type not in self._config_adapters:
            available = list(self._config_adapters.keys())
            raise AdapterRegistryError(
                f"No config adapter registered for type '{config_type}'. "
                f"Available types: {available}"
            )

        adapter_info = self._config_adapters[config_type]
        try:
            return adapter_info.factory(**kwargs)
        except Exception as e:
            raise AdapterRegistryError(
                f"Failed to create config adapter for '{config_type}': {e}"
            )

    def list_supported_config_types(self) -> List[str]:
        """Get list of all supported config types"""
        return sorted(self._config_adapters.keys())

    # Utility Methods
    def get_all_registered_adapters(self) -> Dict[str, List[AdapterInfo]]:
        """Get all registered adapters organized by type"""
        return {
            "extractors": list(self._extractors.values()),
            "output_adapters": list(self._output_adapters.values()),
            "progress_adapters": list(self._progress_adapters.values()),
            "browser_session_factories": list(self._browser_session_factories.values()),
            "config_adapters": list(self._config_adapters.values())
        }

    def validate_dependencies(self, adapter_name: str, adapter_type: str) -> List[str]:
        """
        Validate that adapter dependencies are available.

        Returns:
            List of missing dependencies (empty if all satisfied)
        """
        # This is a placeholder for dependency validation
        # In a full implementation, this would check for required packages,
        # system resources, etc.
        return []

    def get_recommended_adapters(self, criteria: Dict[str, Any]) -> Dict[str, AdapterInfo]:
        """
        Get recommended adapters based on criteria.

        Args:
            criteria: Selection criteria (features, performance, etc.)

        Returns:
            Dictionary mapping adapter types to recommended adapters
        """
        recommendations = {}

        # Simple priority-based selection for now
        # Could be enhanced with more sophisticated selection logic
        if self._extractors:
            best_extractor = max(self._extractors.values(), key=lambda x: x.priority)
            recommendations["extractor"] = best_extractor

        if self._output_adapters:
            best_output = max(self._output_adapters.values(), key=lambda x: x.priority)
            recommendations["output"] = best_output

        if self._progress_adapters:
            best_progress = max(self._progress_adapters.values(), key=lambda x: x.priority)
            recommendations["progress"] = best_progress

        return recommendations


# Global registry instance
default_registry = AdapterRegistry()


def get_default_registry() -> AdapterRegistry:
    """Get the default global adapter registry"""
    return default_registry


def register_default_adapters() -> None:
    """Register all built-in adapters with the default registry"""
    # Import here to avoid circular imports
    from ..adapters.extractors.native_sdwis import (
        NativeSDWISExtractorAdapter, MockNativeSDWISExtractorAdapter
    )
    from ..adapters.output.json import (
        create_json_output_adapter, JSONOutputAdapter, DetailedJSONOutputAdapter, CompactJSONOutputAdapter
    )
    from ..adapters.output.csv import create_csv_output_adapter
    from ..adapters.progress.cli import create_cli_progress_adapter
    from ..adapters.progress.silent import SilentProgressAdapter
    from ..adapters.auth.browser_session import SDWISAuthenticatedBrowserSession, MockBrowserSession
    from ..adapters.auth.config import EnvironmentConfigAdapter

    registry = default_registry

    # Register extractors
    registry.register_extractor(
        "water_systems",
        lambda: NativeSDWISExtractorAdapter(),
        name="Water Systems Extractor",
        description="Extracts water system data from SDWIS",
        supported_features=["pagination", "filtering", "batch_processing"],
        dependencies=["playwright"],
        priority=10
    )

    registry.register_extractor(
        "legal_entities",
        lambda: NativeSDWISExtractorAdapter(),
        name="Legal Entities Extractor",
        description="Extracts legal entity data from SDWIS",
        supported_features=["full_name_continuation", "exclusion_patterns", "batch_processing"],
        dependencies=["playwright"],
        priority=10
    )


    registry.register_extractor(
        "deficiency_types",
        lambda: NativeSDWISExtractorAdapter(),
        name="Deficiency Types Extractor",
        description="Extracts deficiency types from SDWIS Site Visit module",
        supported_features=["site_visit_navigation", "deficiency_table_extraction"],
        dependencies=["playwright"],
        priority=10
    )

    # Mock extractors
    registry.register_extractor(
        "mock_water_systems",
        lambda: MockNativeSDWISExtractorAdapter(),
        name="Mock Water Systems Extractor",
        description="Mock extractor for testing",
        supported_features=["testing", "no_network"],
        dependencies=[],
        priority=0
    )

    registry.register_extractor(
        "mock_legal_entities",
        lambda: MockNativeSDWISExtractorAdapter(),
        name="Mock Legal Entities Extractor",
        description="Mock extractor for testing",
        supported_features=["testing", "no_network"],
        dependencies=[],
        priority=0
    )


    registry.register_extractor(
        "mock_deficiency_types",
        lambda: MockNativeSDWISExtractorAdapter(),
        name="Mock Deficiency Types Extractor",
        description="Mock extractor for testing",
        supported_features=["testing", "no_network"],
        dependencies=[],
        priority=0
    )

    # Register output adapters
    registry.register_output_adapter(
        "json",
        lambda **kwargs: create_json_output_adapter(**kwargs),
        name="JSON Output",
        description="Standard JSON format output",
        supported_features=["metadata", "human_readable"],
        priority=10
    )

    registry.register_output_adapter(
        "csv",
        lambda **kwargs: create_csv_output_adapter(**kwargs),
        name="CSV Output",
        description="Comma-separated values format",
        supported_features=["tabular", "excel_compatible"],
        dependencies=["pandas"],
        priority=8
    )

    # Register progress adapters
    registry.register_progress_adapter(
        "cli",
        lambda cli_progress_type="simple", use_rich=True, **kwargs: create_cli_progress_adapter(
            progress_type=cli_progress_type, use_rich=use_rich, **kwargs
        ),
        name="CLI Progress",
        description="Command-line progress reporting",
        supported_features=["rich_formatting", "progress_bars"],
        priority=10
    )

    registry.register_progress_adapter(
        "silent",
        lambda **kwargs: SilentProgressAdapter(),
        name="Silent Progress",
        description="No progress output",
        supported_features=["automation", "no_output"],
        priority=5
    )

    # Register browser session factories
    registry.register_browser_session_factory(
        "sdwis",
        lambda **kwargs: SDWISAuthenticatedBrowserSession(**kwargs),
        name="SDWIS Browser Session",
        description="Real SDWIS browser session with Playwright",
        supported_features=["authentication", "session_reuse", "screenshots"],
        dependencies=["playwright"],
        priority=10
    )

    registry.register_browser_session_factory(
        "mock",
        lambda **kwargs: MockBrowserSession(),
        name="Mock Browser Session",
        description="Mock session for testing",
        supported_features=["testing", "no_network"],
        priority=0
    )

    # Register config adapters
    registry.register_config_adapter(
        "environment",
        lambda **kwargs: EnvironmentConfigAdapter(**kwargs),
        name="Environment Config",
        description="Configuration from environment variables",
        supported_features=["validation", "defaults"],
        priority=10
    )
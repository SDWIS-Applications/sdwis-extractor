"""
Core domain layer

Contains the pure business logic, domain models, and port interfaces
that are independent of infrastructure concerns.
"""

from .domain import (
    ExtractionQuery,
    ExtractionResult,
    ExtractionMetadata,
    ProgressUpdate,
    PaginationConfig
)

from .services import (
    ExtractionService,
    BatchExtractionService
)

from .export_service import ExportService, ExportMode
from .export_configuration import ExportConfiguration, FileNamingPolicy
from .export_orchestration import ExportOrchestrationService

from .ports import (
    ExtractionPort,
    AuthenticationValidationPort,
    AuthenticatedBrowserSessionPort,
    ProgressReportingPort,
    OutputPort,
    ConfigurationPort,
    ExtractionError,
    AuthenticationError,
    BrowserSessionError,
    OutputError,
    ConfigurationError
)

__all__ = [
    # Domain models
    'ExtractionQuery',
    'ExtractionResult',
    'ExtractionMetadata',
    'ProgressUpdate',
    'PaginationConfig',

    # Services
    'ExtractionService',
    'BatchExtractionService',
    'ExportService',
    'ExportOrchestrationService',

    # Export domain objects
    'ExportConfiguration',
    'FileNamingPolicy',
    'ExportMode',

    # Ports
    'ExtractionPort',
    'AuthenticationValidationPort',
    'AuthenticatedBrowserSessionPort',
    'ProgressReportingPort',
    'OutputPort',
    'ConfigurationPort',

    # Exceptions
    'ExtractionError',
    'AuthenticationError',
    'BrowserSessionError',
    'OutputError',
    'ConfigurationError'
]
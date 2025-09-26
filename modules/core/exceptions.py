"""
Domain-Specific Exceptions

Defines domain-specific exceptions and error boundaries for the SDWIS automation system.
These exceptions provide clear error semantics and enable proper error translation at
architectural boundaries.
"""

from typing import List, Optional, Dict, Any


# Base domain exception hierarchy
class SDWISDomainError(Exception):
    """Base exception for all SDWIS domain errors"""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.context = context or {}
        self.domain = "SDWIS"


class ExtractionError(SDWISDomainError):
    """Base exception for data extraction errors"""

    def __init__(self, message: str, data_type: Optional[str] = None, **context):
        super().__init__(message, context)
        self.data_type = data_type


class ExportError(SDWISDomainError):
    """Base exception for data export errors"""

    def __init__(self, message: str, export_mode: Optional[str] = None, **context):
        super().__init__(message, context)
        self.export_mode = export_mode


# Specific domain exceptions
class InvalidDataTypeError(ExtractionError):
    """Raised when an unsupported data type is requested"""

    def __init__(self, data_type: str, supported_types: Optional[List[str]] = None):
        message = f"Unsupported data type: '{data_type}'"
        if supported_types:
            message += f". Supported types: {', '.join(supported_types)}"
        super().__init__(message, data_type=data_type, supported_types=supported_types)


class InvalidOutputFormatError(ExportError):
    """Raised when an unsupported output format is requested"""

    def __init__(self, format_type: str, supported_formats: Optional[List[str]] = None):
        message = f"Unsupported output format: '{format_type}'"
        if supported_formats:
            message += f". Supported formats: {', '.join(supported_formats)}"
        super().__init__(message, format_type=format_type, supported_formats=supported_formats)


class ExportConfigurationError(ExportError):
    """Raised when export configuration is invalid"""

    def __init__(self, message: str, configuration_errors: Optional[List[str]] = None):
        super().__init__(message, configuration_errors=configuration_errors)
        self.configuration_errors = configuration_errors or []


class SchemaValidationError(ExportError):
    """Raised when export schema validation fails"""

    def __init__(self, message: str, schema_path: Optional[str] = None, validation_errors: Optional[List[str]] = None):
        super().__init__(message, schema_path=schema_path, validation_errors=validation_errors)
        self.schema_path = schema_path
        self.validation_errors = validation_errors or []


class AuthenticationError(SDWISDomainError):
    """Raised when authentication fails"""

    def __init__(self, message: str, username: Optional[str] = None, **context):
        super().__init__(message, context)
        self.username = username


class SessionError(SDWISDomainError):
    """Raised when browser session operations fail"""

    def __init__(self, message: str, session_id: Optional[str] = None, **context):
        super().__init__(message, context)
        self.session_id = session_id


class PaginationError(ExtractionError):
    """Raised when pagination operations fail"""

    def __init__(self, message: str, current_page: Optional[int] = None, **context):
        super().__init__(message, current_page=current_page, **context)
        self.current_page = current_page


class DataTransformationError(ExportError):
    """Raised when data transformation fails"""

    def __init__(self, message: str, field_name: Optional[str] = None, **context):
        super().__init__(message, field_name=field_name, **context)
        self.field_name = field_name


# Infrastructure boundary exceptions
class InfrastructureError(Exception):
    """Base exception for infrastructure-level errors that need translation"""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error


class NetworkError(InfrastructureError):
    """Network-level errors that need domain translation"""
    pass


class FileSystemError(InfrastructureError):
    """File system errors that need domain translation"""
    pass


class BrowserError(InfrastructureError):
    """Browser automation errors that need domain translation"""
    pass


# Error translation utilities
class ErrorTranslator:
    """Utility for translating infrastructure exceptions to domain exceptions"""

    @staticmethod
    def translate_output_error(error: Exception, format_type: str, supported_formats: List[str]) -> ExportError:
        """Translate generic output errors to domain-specific exceptions"""
        if isinstance(error, ValueError) and "format" in str(error).lower():
            return InvalidOutputFormatError(format_type, supported_formats)
        elif isinstance(error, (OSError, PermissionError)):
            return ExportError(f"Failed to write {format_type} output: {str(error)}",
                             format_type=format_type, original_error=error)
        else:
            return ExportError(f"Export failed: {str(error)}",
                             format_type=format_type, original_error=error)

    @staticmethod
    def translate_extraction_error(error: Exception, data_type: str) -> ExtractionError:
        """Translate generic extraction errors to domain-specific exceptions"""
        if "authentication" in str(error).lower():
            return AuthenticationError(f"Authentication failed for {data_type} extraction: {str(error)}",
                                     data_type=data_type)
        elif "session" in str(error).lower():
            return SessionError(f"Session error during {data_type} extraction: {str(error)}",
                              data_type=data_type)
        elif "pagination" in str(error).lower():
            return PaginationError(f"Pagination failed during {data_type} extraction: {str(error)}",
                                 data_type=data_type)
        else:
            return ExtractionError(f"Extraction failed for {data_type}: {str(error)}",
                                 data_type=data_type, original_error=error)

    @staticmethod
    def translate_validation_error(error: Exception, context: str = "") -> ExportConfigurationError:
        """Translate validation errors to domain-specific exceptions"""
        message = f"Configuration validation failed"
        if context:
            message += f" for {context}"
        message += f": {str(error)}"

        return ExportConfigurationError(message, original_error=error)


# Context managers for error boundary handling
class ErrorBoundary:
    """Context manager for handling and translating errors at architectural boundaries"""

    def __init__(self, boundary_name: str, context: Optional[Dict[str, Any]] = None):
        self.boundary_name = boundary_name
        self.context = context or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type and not issubclass(exc_type, SDWISDomainError):
            # Log infrastructure error for debugging
            print(f"Infrastructure error at {self.boundary_name}: {exc_val}")
            # Could add proper logging here
        return False  # Don't suppress exceptions
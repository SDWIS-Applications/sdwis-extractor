"""
Enhanced validation framework for SDWIS automation.

Provides detailed validation with clear error messages and suggestions
for configuration, extraction queries, and domain objects.
"""

from dataclasses import dataclass
from typing import List, Optional, Any, Dict, Union
import re
from urllib.parse import urlparse

from .domain import ExtractionQuery, PaginationConfig


@dataclass
class ValidationError:
    """Represents a validation error with detailed context"""
    field: str
    value: Any
    message: str
    suggestion: Optional[str] = None
    code: Optional[str] = None

    def __str__(self) -> str:
        result = f"Invalid {self.field}: {self.message}"
        if self.suggestion:
            result += f" (Suggestion: {self.suggestion})"
        return result


@dataclass
class ValidationResult:
    """Result of validation operation"""
    valid: bool
    errors: List[ValidationError]
    warnings: List[str]

    @property
    def success(self) -> bool:
        return self.valid

    def get_error_summary(self) -> str:
        """Get human-readable summary of all errors"""
        if not self.errors:
            return "No validation errors"

        summary = f"Found {len(self.errors)} validation error(s):\n"
        for i, error in enumerate(self.errors, 1):
            summary += f"  {i}. {error}\n"

        if self.warnings:
            summary += f"\nWarnings ({len(self.warnings)}):\n"
            for i, warning in enumerate(self.warnings, 1):
                summary += f"  {i}. {warning}\n"

        return summary.strip()


class InvalidExtractionQueryError(Exception):
    """Exception raised when extraction query validation fails"""

    def __init__(self, validation_result: ValidationResult):
        self.validation_result = validation_result
        super().__init__(validation_result.get_error_summary())


class InvalidConfigurationError(Exception):
    """Exception raised when configuration validation fails"""

    def __init__(self, validation_result: ValidationResult):
        self.validation_result = validation_result
        super().__init__(validation_result.get_error_summary())


class ConfigurationValidator:
    """Validates SDWIS configuration with detailed error reporting"""

    def validate_credentials(self, credentials: Dict[str, str]) -> ValidationResult:
        """
        Validate credential configuration.

        Args:
            credentials: Dictionary containing username, password

        Returns:
            ValidationResult with detailed feedback
        """
        errors = []
        warnings = []

        # Check required fields
        required_fields = ['username', 'password']
        for field in required_fields:
            if not credentials.get(field):
                errors.append(ValidationError(
                    field=field,
                    value=credentials.get(field),
                    message="is required",
                    suggestion=f"Set SDWIS_{field.upper()} environment variable",
                    code="MISSING_CREDENTIAL"
                ))

        # Validate username format
        username = credentials.get('username', '')
        if username:
            if len(username) < 2:
                errors.append(ValidationError(
                    field="username",
                    value=username,
                    message="must be at least 2 characters long",
                    suggestion="Check your SDWIS username",
                    code="INVALID_USERNAME_LENGTH"
                ))

            if not re.match(r'^[a-zA-Z0-9_.-]+$', username):
                errors.append(ValidationError(
                    field="username",
                    value=username,
                    message="contains invalid characters",
                    suggestion="Username should only contain letters, numbers, dots, hyphens, and underscores",
                    code="INVALID_USERNAME_FORMAT"
                ))

        # Validate password
        password = credentials.get('password', '')
        if password:
            if len(password) < 4:
                warnings.append("Password is very short - SDWIS typically requires longer passwords")

            if password in ['password', '123456', 'admin']:
                warnings.append("Password appears to be a common default - ensure you're using your actual SDWIS credentials")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def validate_server_config(self, config: Dict[str, str]) -> ValidationResult:
        """
        Validate server configuration.

        Args:
            config: Dictionary containing server settings

        Returns:
            ValidationResult with detailed feedback
        """
        errors = []
        warnings = []

        # Validate base URL
        base_url = config.get('base_url', '')
        if not base_url:
            errors.append(ValidationError(
                field="base_url",
                value=base_url,
                message="is required",
                suggestion="Set SDWIS_URL environment variable (e.g., 'http://sdwis:8080/SDWIS/')",
                code="MISSING_BASE_URL"
            ))
        else:
            # Parse URL
            try:
                parsed = urlparse(base_url)

                if not parsed.scheme:
                    errors.append(ValidationError(
                        field="base_url",
                        value=base_url,
                        message="missing protocol (http/https)",
                        suggestion="Add 'http://' or 'https://' to the beginning",
                        code="MISSING_PROTOCOL"
                    ))

                if not parsed.netloc:
                    errors.append(ValidationError(
                        field="base_url",
                        value=base_url,
                        message="missing hostname",
                        suggestion="Include hostname (e.g., 'sdwis:8080' or 'localhost:8080')",
                        code="MISSING_HOSTNAME"
                    ))

                if parsed.scheme not in ['http', 'https']:
                    errors.append(ValidationError(
                        field="base_url",
                        value=base_url,
                        message=f"unsupported protocol '{parsed.scheme}'",
                        suggestion="Use 'http' or 'https'",
                        code="INVALID_PROTOCOL"
                    ))

                # Check path
                if not base_url.rstrip('/').endswith('/SDWIS'):
                    warnings.append("Base URL should typically end with '/SDWIS/' for standard SDWIS installations")

                # Check for common mistakes
                if 'localhost' in parsed.netloc and not parsed.port:
                    warnings.append("Using localhost without port - ensure SDWIS is running on port 80 or specify port (e.g., 'localhost:8080')")

            except Exception as e:
                errors.append(ValidationError(
                    field="base_url",
                    value=base_url,
                    message=f"invalid URL format: {e}",
                    suggestion="Use format: 'http://hostname:port/SDWIS/'",
                    code="INVALID_URL_FORMAT"
                ))

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def validate_extraction_config(self, config: Dict[str, Any]) -> ValidationResult:
        """
        Validate extraction-specific configuration.

        Args:
            config: Dictionary containing extraction settings

        Returns:
            ValidationResult with detailed feedback
        """
        errors = []
        warnings = []

        # Validate batch size
        batch_size = config.get('batch_size')
        if batch_size is not None:
            try:
                batch_size_int = int(batch_size)
                if batch_size_int < 1:
                    errors.append(ValidationError(
                        field="batch_size",
                        value=batch_size,
                        message="must be at least 1",
                        suggestion="Use a positive integer (typical values: 100-1000)",
                        code="INVALID_BATCH_SIZE"
                    ))
                elif batch_size_int > 10000:
                    warnings.append(f"Batch size {batch_size_int} is very large - this may cause memory issues")
                elif batch_size_int > 5000:
                    warnings.append(f"Batch size {batch_size_int} is large - consider smaller batches if you experience timeouts")
            except ValueError:
                errors.append(ValidationError(
                    field="batch_size",
                    value=batch_size,
                    message="must be a number",
                    suggestion="Use integer values like 100, 500, or 1000",
                    code="INVALID_BATCH_SIZE_FORMAT"
                ))

        # Validate timeout settings
        timeout = config.get('timeout_ms')
        if timeout is not None:
            try:
                timeout_int = int(timeout)
                if timeout_int < 1000:
                    warnings.append(f"Timeout {timeout_int}ms is very short - may cause failures on slow networks")
                elif timeout_int > 300000:  # 5 minutes
                    warnings.append(f"Timeout {timeout_int}ms is very long - consider shorter timeouts for better error detection")
            except ValueError:
                errors.append(ValidationError(
                    field="timeout_ms",
                    value=timeout,
                    message="must be a number (milliseconds)",
                    suggestion="Use values like 30000 (30 seconds) or 60000 (1 minute)",
                    code="INVALID_TIMEOUT_FORMAT"
                ))

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def validate_complete_configuration(
        self,
        credentials: Dict[str, str],
        server_config: Dict[str, str],
        extraction_config: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate complete configuration with cross-field validation.

        Args:
            credentials: Credential configuration
            server_config: Server configuration
            extraction_config: Extraction configuration

        Returns:
            Combined validation result
        """
        # Validate each section
        cred_result = self.validate_credentials(credentials)
        server_result = self.validate_server_config(server_config)
        extract_result = self.validate_extraction_config(extraction_config)

        # Combine results
        all_errors = cred_result.errors + server_result.errors + extract_result.errors
        all_warnings = cred_result.warnings + server_result.warnings + extract_result.warnings

        return ValidationResult(
            valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings
        )


class ExtractionQueryValidator:
    """Validates extraction queries with detailed error reporting"""

    SUPPORTED_DATA_TYPES = {'water_systems', 'legal_entities', 'sample_schedules'}

    def validate_query(self, query: ExtractionQuery) -> ValidationResult:
        """
        Validate an extraction query.

        Args:
            query: ExtractionQuery to validate

        Returns:
            ValidationResult with detailed feedback
        """
        errors = []
        warnings = []

        # Validate data type
        if query.data_type not in self.SUPPORTED_DATA_TYPES:
            errors.append(ValidationError(
                field="data_type",
                value=query.data_type,
                message=f"unsupported data type",
                suggestion=f"Use one of: {', '.join(sorted(self.SUPPORTED_DATA_TYPES))}",
                code="UNSUPPORTED_DATA_TYPE"
            ))

        # Validate pagination config
        if query.pagination:
            pagination_result = self._validate_pagination_config(query.pagination)
            errors.extend(pagination_result.errors)
            warnings.extend(pagination_result.warnings)

        # Validate filters
        filter_result = self._validate_filters(query.data_type, query.filters)
        errors.extend(filter_result.errors)
        warnings.extend(filter_result.warnings)

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def _validate_pagination_config(self, pagination: PaginationConfig) -> ValidationResult:
        """Validate pagination configuration"""
        errors = []
        warnings = []

        if pagination.max_pages is not None:
            if pagination.max_pages < 1:
                errors.append(ValidationError(
                    field="max_pages",
                    value=pagination.max_pages,
                    message="must be at least 1",
                    suggestion="Use positive integers or None for unlimited",
                    code="INVALID_MAX_PAGES"
                ))
            elif pagination.max_pages > 100:
                warnings.append(f"max_pages={pagination.max_pages} is very large - consider smaller batches for testing")

        if pagination.page_size is not None:
            if pagination.page_size < 1:
                errors.append(ValidationError(
                    field="page_size",
                    value=pagination.page_size,
                    message="must be at least 1",
                    suggestion="Use positive integers (typical: 100-1000)",
                    code="INVALID_PAGE_SIZE"
                ))
            elif pagination.page_size > 5000:
                warnings.append(f"page_size={pagination.page_size} is very large - may cause timeouts")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def _validate_filters(self, data_type: str, filters: Dict[str, Any]) -> ValidationResult:
        """Validate data-type-specific filters"""
        errors = []
        warnings = []

        # Validate exclusion patterns (for legal_entities)
        if data_type == 'legal_entities' and 'exclusion_patterns' in filters:
            patterns = filters['exclusion_patterns']
            if not isinstance(patterns, list):
                errors.append(ValidationError(
                    field="exclusion_patterns",
                    value=type(patterns).__name__,
                    message="must be a list of regex patterns",
                    suggestion="Use format: ['pattern1', 'pattern2']",
                    code="INVALID_EXCLUSION_PATTERNS_TYPE"
                ))
            else:
                for i, pattern in enumerate(patterns):
                    try:
                        re.compile(pattern)
                    except re.error as e:
                        errors.append(ValidationError(
                            field=f"exclusion_patterns[{i}]",
                            value=pattern,
                            message=f"invalid regex pattern: {e}",
                            suggestion="Check regex syntax",
                            code="INVALID_REGEX_PATTERN"
                        ))

        # Validate search parameters (for sample_schedules)
        if data_type == 'sample_schedules' and 'search_params' in filters:
            search_params = filters['search_params']
            if not isinstance(search_params, dict):
                errors.append(ValidationError(
                    field="search_params",
                    value=type(search_params).__name__,
                    message="must be a dictionary",
                    suggestion="Use format: {'key': 'value'}",
                    code="INVALID_SEARCH_PARAMS_TYPE"
                ))
            else:
                # Validate specific search parameters
                if 'pws_id' in search_params:
                    pws_id = search_params['pws_id']
                    if not re.match(r'^\d{7,8}$', str(pws_id)):
                        warnings.append(f"PWS ID '{pws_id}' doesn't match typical format (7-8 digits)")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
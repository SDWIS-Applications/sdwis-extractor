"""
Enhanced Validation Framework

Provides sophisticated validation capabilities with context-aware error messages,
suggestion systems, and extensible validation rules.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Protocol, Callable, Union
from abc import ABC, abstractmethod
from enum import Enum

from .export_configuration import ExportConfiguration, ExportMode
from .exceptions import ExportConfigurationError, InvalidDataTypeError, InvalidOutputFormatError


class ValidationSeverity(Enum):
    """Validation issue severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """Represents a validation issue with context and suggestions"""
    severity: ValidationSeverity
    message: str
    field: Optional[str] = None
    code: Optional[str] = None
    context: Dict[str, Any] = None
    suggestions: List[str] = None

    def __post_init__(self):
        if self.context is None:
            self.context = {}
        if self.suggestions is None:
            self.suggestions = []


@dataclass
class ValidationResult:
    """Result of a validation operation"""
    valid: bool
    issues: List[ValidationIssue]
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    @property
    def errors(self) -> List[ValidationIssue]:
        """Get only error and critical severity issues"""
        return [issue for issue in self.issues if issue.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]]

    @property
    def warnings(self) -> List[ValidationIssue]:
        """Get only warning severity issues"""
        return [issue for issue in self.issues if issue.severity == ValidationSeverity.WARNING]

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors or critical issues"""
        return len(self.errors) > 0

    def add_issue(self, issue: ValidationIssue) -> None:
        """Add a validation issue"""
        self.issues.append(issue)
        # Update overall validity based on errors
        self.valid = not self.has_errors


class ValidationRule(ABC):
    """Abstract base class for validation rules"""

    @abstractmethod
    def validate(self, value: Any, context: Dict[str, Any] = None) -> ValidationResult:
        """Validate a value and return result"""
        pass

    @abstractmethod
    def get_rule_name(self) -> str:
        """Get the name of this validation rule"""
        pass


class DataTypeValidationRule(ValidationRule):
    """Validates data type specifications"""

    def __init__(self, supported_data_types: List[str]):
        self.supported_data_types = supported_data_types

    def validate(self, value: List[str], context: Dict[str, Any] = None) -> ValidationResult:
        """Validate data types"""
        result = ValidationResult(valid=True, issues=[])
        context = context or {}

        if not value:
            result.add_issue(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message="No data types specified",
                field="data_types",
                code="EMPTY_DATA_TYPES",
                suggestions=["Specify at least one data type: " + ", ".join(self.supported_data_types)]
            ))

        for data_type in value:
            if data_type not in self.supported_data_types:
                result.add_issue(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message=f"Unsupported data type: '{data_type}'",
                    field="data_types",
                    code="INVALID_DATA_TYPE",
                    context={"invalid_type": data_type, "supported_types": self.supported_data_types},
                    suggestions=[
                        f"Use one of: {', '.join(self.supported_data_types)}",
                        f"Check spelling of '{data_type}'"
                    ]
                ))

        return result

    def get_rule_name(self) -> str:
        return "DataTypeValidation"


class ExportModeValidationRule(ValidationRule):
    """Validates export mode and format compatibility"""

    def __init__(self, supported_formats: Dict[str, List[str]]):
        self.supported_formats = supported_formats

    def validate(self, value: Dict[str, Any], context: Dict[str, Any] = None) -> ValidationResult:
        """Validate export mode and format compatibility"""
        result = ValidationResult(valid=True, issues=[])
        context = context or {}

        export_mode = value.get('export_mode')
        output_format = value.get('output_format')

        if not export_mode:
            result.add_issue(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                message="No export mode specified, defaulting to 'general'",
                field="export_mode",
                code="DEFAULT_EXPORT_MODE"
            ))
            return result

        # Inspection mode validation
        if export_mode == ExportMode.INSPECTION:
            if output_format and output_format != 'json':
                result.add_issue(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message=f"Inspection mode only supports JSON format, got: {output_format}",
                    field="output_format",
                    code="INVALID_INSPECTION_FORMAT",
                    context={"current_format": output_format, "required_format": "json"},
                    suggestions=[
                        "Change output format to 'json' for inspection mode",
                        "Use 'general' export mode for other formats"
                    ]
                ))

        # Check format support for mode
        if export_mode.value in self.supported_formats:
            supported = self.supported_formats[export_mode.value]
            if output_format and output_format not in supported:
                result.add_issue(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message=f"Format '{output_format}' not supported for {export_mode.value} mode",
                    field="output_format",
                    code="UNSUPPORTED_FORMAT_FOR_MODE",
                    context={"mode": export_mode.value, "format": output_format, "supported": supported},
                    suggestions=[f"Use one of: {', '.join(supported)}"]
                ))

        return result

    def get_rule_name(self) -> str:
        return "ExportModeValidation"


class OutputPathValidationRule(ValidationRule):
    """Validates output path specifications"""

    def validate(self, value: Optional[str], context: Dict[str, Any] = None) -> ValidationResult:
        """Validate output path"""
        result = ValidationResult(valid=True, issues=[])
        context = context or {}

        if not value:
            # No path specified is usually okay (auto-generation)
            result.add_issue(ValidationIssue(
                severity=ValidationSeverity.INFO,
                message="No output path specified, will auto-generate filename",
                field="output_path",
                code="AUTO_GENERATED_PATH"
            ))
            return result

        # Check path validity
        try:
            from pathlib import Path
            path = Path(value)

            # Check if parent directory is accessible
            if not path.parent.exists() and path.parent != Path('.'):
                result.add_issue(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message=f"Parent directory does not exist: {path.parent}",
                    field="output_path",
                    code="MISSING_PARENT_DIR",
                    context={"path": str(path), "parent": str(path.parent)},
                    suggestions=[
                        f"Create directory: {path.parent}",
                        "Use a path with existing parent directory"
                    ]
                ))

            # Check file extension consistency
            export_mode = context.get('export_mode')
            if export_mode == ExportMode.INSPECTION and path.suffix != '.json':
                result.add_issue(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message="Inspection mode typically uses .json extension",
                    field="output_path",
                    code="INCONSISTENT_EXTENSION",
                    suggestions=["Consider using .json extension for inspection reports"]
                ))

        except Exception as e:
            result.add_issue(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message=f"Invalid output path: {str(e)}",
                field="output_path",
                code="INVALID_PATH",
                context={"error": str(e)},
                suggestions=["Check path syntax and permissions"]
            ))

        return result

    def get_rule_name(self) -> str:
        return "OutputPathValidation"


class ExportConfigurationValidator:
    """Enhanced validator for export configurations"""

    def __init__(self):
        self.rules: List[ValidationRule] = [
            DataTypeValidationRule(["water_systems", "legal_entities", "sample_schedules"]),
            ExportModeValidationRule({
                "general": ["json", "csv", "tsv"],
                "inspection": ["json"]
            }),
            OutputPathValidationRule()
        ]
        self.custom_rules: Dict[str, ValidationRule] = {}

    def add_custom_rule(self, name: str, rule: ValidationRule) -> None:
        """Add a custom validation rule"""
        self.custom_rules[name] = rule

    def validate_configuration(self, config: ExportConfiguration) -> ValidationResult:
        """Perform comprehensive validation of export configuration"""
        result = ValidationResult(valid=True, issues=[])

        # Create validation context
        context = {
            'export_mode': config.export_mode,
            'output_format': config.resolve_output_format(),
            'data_types': config.data_types
        }

        # Apply built-in rules
        for rule in self.rules:
            rule_result = self._apply_rule(rule, config, context)
            result.issues.extend(rule_result.issues)

        # Apply custom rules
        for name, rule in self.custom_rules.items():
            rule_result = self._apply_rule(rule, config, context)
            result.issues.extend(rule_result.issues)

        # Update overall validity
        result.valid = not result.has_errors

        # Add metadata
        result.metadata = {
            'rules_applied': len(self.rules) + len(self.custom_rules),
            'total_issues': len(result.issues),
            'error_count': len(result.errors),
            'warning_count': len(result.warnings),
            'validation_context': context
        }

        return result

    def _apply_rule(self, rule: ValidationRule, config: ExportConfiguration, context: Dict[str, Any]) -> ValidationResult:
        """Apply a specific validation rule"""
        try:
            if isinstance(rule, DataTypeValidationRule):
                return rule.validate(config.data_types, context)
            elif isinstance(rule, ExportModeValidationRule):
                return rule.validate({
                    'export_mode': config.export_mode,
                    'output_format': config.resolve_output_format()
                }, context)
            elif isinstance(rule, OutputPathValidationRule):
                return rule.validate(config.output_path, context)
            else:
                # For custom rules, pass the entire config
                return rule.validate(config, context)
        except Exception as e:
            # If rule validation itself fails, create an error
            error_result = ValidationResult(valid=False, issues=[])
            error_result.add_issue(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message=f"Validation rule '{rule.get_rule_name()}' failed: {str(e)}",
                code="RULE_EXECUTION_ERROR",
                context={"rule": rule.get_rule_name(), "error": str(e)}
            ))
            return error_result

    def suggest_corrections(self, validation_result: ValidationResult) -> List[str]:
        """Generate actionable correction suggestions"""
        all_suggestions = []

        for issue in validation_result.issues:
            if issue.suggestions:
                all_suggestions.extend(issue.suggestions)

        # Remove duplicates while preserving order
        unique_suggestions = []
        for suggestion in all_suggestions:
            if suggestion not in unique_suggestions:
                unique_suggestions.append(suggestion)

        return unique_suggestions

    def validate_data_type_compatibility(self, data_types: List[str], export_mode: ExportMode) -> Dict[str, Any]:
        """Validate data type compatibility with export mode"""
        compatibility_result = {
            'compatible': True,
            'issues': [],
            'recommendations': []
        }

        if export_mode == ExportMode.INSPECTION:
            # Check if all data types support inspection fields
            unsupported_types = []
            for data_type in data_types:
                if data_type not in ["water_systems", "legal_entities"]:
                    unsupported_types.append(data_type)

            if unsupported_types:
                compatibility_result['compatible'] = False
                compatibility_result['issues'].append(
                    f"Data types not fully supported in inspection mode: {', '.join(unsupported_types)}"
                )
                compatibility_result['recommendations'].append(
                    "Consider using 'general' mode for comprehensive data extraction"
                )

        return compatibility_result


# Convenience functions
def validate_export_configuration(config: ExportConfiguration) -> ValidationResult:
    """Convenient function to validate export configuration"""
    validator = ExportConfigurationValidator()
    return validator.validate_configuration(config)


def get_validation_summary(validation_result: ValidationResult) -> str:
    """Get a human-readable validation summary"""
    if validation_result.valid:
        return f"✅ Configuration valid ({len(validation_result.issues)} info/warnings)"
    else:
        error_count = len(validation_result.errors)
        warning_count = len(validation_result.warnings)
        return f"❌ Configuration invalid: {error_count} errors, {warning_count} warnings"
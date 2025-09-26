"""
Configuration Schema Versioning System

Provides schema evolution, migration, and compatibility management for export configurations.
Enables seamless upgrades while maintaining backward compatibility.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable, Protocol
from pathlib import Path
from enum import Enum
import json
import copy

from .exceptions import SchemaValidationError
from .factory_ports import SchemaManagerPort


class VersioningStrategy(Enum):
    """Schema versioning strategies"""
    SEMANTIC = "semantic"  # Major.Minor.Patch (e.g., 1.0.0)
    TIMESTAMP = "timestamp"  # YYYYMMDD.HHMMSS
    INCREMENTAL = "incremental"  # 1, 2, 3, etc.


@dataclass
class SchemaVersion:
    """Represents a schema version with metadata"""
    version: str
    created_at: datetime
    description: str
    breaking_changes: bool = False
    deprecated_fields: List[str] = field(default_factory=list)
    new_fields: List[str] = field(default_factory=list)
    migration_notes: str = ""

    def is_compatible_with(self, other_version: str) -> bool:
        """Check if this version is compatible with another version"""
        if self.breaking_changes:
            # Compare major versions for semantic versioning
            if "." in self.version and "." in other_version:
                self_major = int(self.version.split(".")[0])
                other_major = int(other_version.split(".")[0])
                return self_major == other_major
        return True


@dataclass
class Schema:
    """Represents a configuration schema"""
    name: str
    version: SchemaVersion
    schema_data: Dict[str, Any]
    validation_rules: List[str] = field(default_factory=list)
    examples: List[Dict[str, Any]] = field(default_factory=list)

    def validate_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data against this schema"""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': []
        }

        # Basic schema validation
        required_fields = self.schema_data.get('required', [])
        for field_name in required_fields:
            if field_name not in data:
                validation_result['valid'] = False
                validation_result['errors'].append(f"Required field missing: {field_name}")

        # Check for deprecated fields
        if self.version.deprecated_fields:
            for field_name in self.version.deprecated_fields:
                if field_name in data:
                    validation_result['warnings'].append(
                        f"Field '{field_name}' is deprecated in version {self.version.version}"
                    )

        # Type validation
        properties = self.schema_data.get('properties', {})
        for field_name, field_spec in properties.items():
            if field_name in data:
                expected_type = field_spec.get('type')
                actual_value = data[field_name]

                if not self._validate_type(actual_value, expected_type):
                    validation_result['valid'] = False
                    validation_result['errors'].append(
                        f"Field '{field_name}' has incorrect type. Expected: {expected_type}, got: {type(actual_value).__name__}"
                    )

        return validation_result

    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Validate value type against expected type"""
        type_mapping = {
            'string': str,
            'integer': int,
            'number': (int, float),
            'boolean': bool,
            'array': list,
            'object': dict
        }

        if expected_type in type_mapping:
            return isinstance(value, type_mapping[expected_type])

        return True  # Unknown types pass validation


class SchemaMigrator:
    """Handles schema migrations between versions"""

    def __init__(self):
        self.migration_functions: Dict[str, Dict[str, Callable]] = {}

    def register_migration(self, schema_name: str, from_version: str, to_version: str,
                          migration_func: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        """Register a migration function between versions"""
        if schema_name not in self.migration_functions:
            self.migration_functions[schema_name] = {}

        key = f"{from_version}->{to_version}"
        self.migration_functions[schema_name][key] = migration_func

    def migrate(self, schema_name: str, data: Dict[str, Any], from_version: str, to_version: str) -> Dict[str, Any]:
        """Migrate data from one schema version to another"""
        if schema_name not in self.migration_functions:
            raise SchemaValidationError(f"No migrations registered for schema: {schema_name}")

        key = f"{from_version}->{to_version}"
        if key not in self.migration_functions[schema_name]:
            # Try to find a migration path
            migration_path = self._find_migration_path(schema_name, from_version, to_version)
            if not migration_path:
                raise SchemaValidationError(f"No migration path from {from_version} to {to_version}")

            # Apply sequential migrations
            current_data = copy.deepcopy(data)
            for step in migration_path:
                migration_func = self.migration_functions[schema_name][step]
                current_data = migration_func(current_data)

            return current_data
        else:
            # Direct migration available
            migration_func = self.migration_functions[schema_name][key]
            return migration_func(copy.deepcopy(data))

    def _find_migration_path(self, schema_name: str, from_version: str, to_version: str) -> Optional[List[str]]:
        """Find a path of migrations from source to target version"""
        # Simple implementation - could be enhanced with graph algorithms
        available_migrations = list(self.migration_functions[schema_name].keys())

        # For now, just check for direct path or simple two-step path
        direct_path = f"{from_version}->{to_version}"
        if direct_path in available_migrations:
            return [direct_path]

        # Try to find intermediate version
        for migration in available_migrations:
            if migration.startswith(from_version + "->"):
                intermediate = migration.split("->")[1]
                next_path = f"{intermediate}->{to_version}"
                if next_path in available_migrations:
                    return [migration, next_path]

        return None


class SchemaRegistry:
    """Registry for managing schema versions"""

    def __init__(self):
        self.schemas: Dict[str, Dict[str, Schema]] = {}
        self.migrator = SchemaMigrator()
        self.default_versions: Dict[str, str] = {}

    def register_schema(self, schema: Schema) -> None:
        """Register a schema version"""
        if schema.name not in self.schemas:
            self.schemas[schema.name] = {}

        self.schemas[schema.name][schema.version.version] = schema

    def get_schema(self, name: str, version: Optional[str] = None) -> Optional[Schema]:
        """Get a schema by name and version"""
        if name not in self.schemas:
            return None

        if version is None:
            # Get default version
            version = self.default_versions.get(name)
            if version is None:
                # Return latest version
                versions = sorted(self.schemas[name].keys())
                if versions:
                    version = versions[-1]

        return self.schemas[name].get(version)

    def get_available_versions(self, schema_name: str) -> List[str]:
        """Get all available versions for a schema"""
        if schema_name not in self.schemas:
            return []
        return sorted(self.schemas[schema_name].keys())

    def set_default_version(self, schema_name: str, version: str) -> None:
        """Set the default version for a schema"""
        self.default_versions[schema_name] = version

    def register_migration(self, schema_name: str, from_version: str, to_version: str,
                          migration_func: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        """Register a migration function"""
        self.migrator.register_migration(schema_name, from_version, to_version, migration_func)

    def migrate_data(self, schema_name: str, data: Dict[str, Any],
                    from_version: str, to_version: str) -> Dict[str, Any]:
        """Migrate data between schema versions"""
        return self.migrator.migrate(schema_name, data, from_version, to_version)


class ConfigurationSchemaManager:
    """Main schema management service"""

    def __init__(self, schema_directory: Optional[Path] = None):
        self.registry = SchemaRegistry()
        self.schema_directory = schema_directory or Path("config/schemas")
        self._initialize_default_schemas()

    def _initialize_default_schemas(self) -> None:
        """Initialize default export schemas"""
        # Export configuration schema v1.0.0
        export_schema_v1 = Schema(
            name="export_configuration",
            version=SchemaVersion(
                version="1.0.0",
                created_at=datetime.now(),
                description="Basic export configuration schema",
                breaking_changes=False
            ),
            schema_data={
                "type": "object",
                "required": ["data_types", "export_mode"],
                "properties": {
                    "data_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "enum": ["water_systems", "legal_entities", "sample_schedules"]
                    },
                    "export_mode": {
                        "type": "string",
                        "enum": ["general", "inspection"]
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["json", "csv", "tsv"]
                    },
                    "output_path": {
                        "type": "string"
                    }
                }
            }
        )

        # Export configuration schema v1.1.0 with additional fields
        export_schema_v1_1 = Schema(
            name="export_configuration",
            version=SchemaVersion(
                version="1.1.0",
                created_at=datetime.now(),
                description="Enhanced export configuration with file naming policies",
                breaking_changes=False,
                new_fields=["file_naming_policy", "validation_level"]
            ),
            schema_data={
                "type": "object",
                "required": ["data_types", "export_mode"],
                "properties": {
                    **export_schema_v1.schema_data["properties"],
                    "file_naming_policy": {
                        "type": "object",
                        "properties": {
                            "include_timestamp": {"type": "boolean"},
                            "timestamp_format": {"type": "string"},
                            "include_data_type": {"type": "boolean"}
                        }
                    },
                    "validation_level": {
                        "type": "string",
                        "enum": ["strict", "normal", "permissive"],
                        "default": "normal"
                    }
                }
            }
        )

        # Register schemas
        self.registry.register_schema(export_schema_v1)
        self.registry.register_schema(export_schema_v1_1)
        self.registry.set_default_version("export_configuration", "1.1.0")

        # Register migration from v1.0.0 to v1.1.0
        self.registry.register_migration(
            "export_configuration", "1.0.0", "1.1.0",
            self._migrate_export_config_v1_to_v1_1
        )

    def _migrate_export_config_v1_to_v1_1(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Migration function from export config v1.0.0 to v1.1.0"""
        migrated_data = copy.deepcopy(data)

        # Add default file naming policy
        if "file_naming_policy" not in migrated_data:
            migrated_data["file_naming_policy"] = {
                "include_timestamp": True,
                "timestamp_format": "%Y%m%d_%H%M%S",
                "include_data_type": True
            }

        # Add default validation level
        if "validation_level" not in migrated_data:
            migrated_data["validation_level"] = "normal"

        return migrated_data

    def load_schema(self, schema_name: str, version: Optional[str] = None) -> Dict[str, Any]:
        """Load export schema by name and version"""
        schema = self.registry.get_schema(schema_name, version)
        if not schema:
            raise SchemaValidationError(f"Schema not found: {schema_name} version {version}")

        return schema.schema_data

    def validate_schema(self, schema_name: str, data: Dict[str, Any], version: Optional[str] = None) -> Dict[str, Any]:
        """Validate data against schema"""
        schema = self.registry.get_schema(schema_name, version)
        if not schema:
            raise SchemaValidationError(f"Schema not found: {schema_name} version {version}")

        return schema.validate_data(data)

    def migrate_schema(self, schema_name: str, data: Dict[str, Any],
                      from_version: str, to_version: str) -> Dict[str, Any]:
        """Migrate data from one schema version to another"""
        return self.registry.migrate_data(schema_name, data, from_version, to_version)

    def get_available_schemas(self) -> List[Dict[str, Any]]:
        """Get list of available schemas with metadata"""
        schemas_info = []

        for schema_name, versions in self.registry.schemas.items():
            for version_str, schema in versions.items():
                schemas_info.append({
                    'name': schema.name,
                    'version': schema.version.version,
                    'description': schema.version.description,
                    'created_at': schema.version.created_at,
                    'breaking_changes': schema.version.breaking_changes,
                    'new_fields': schema.version.new_fields,
                    'deprecated_fields': schema.version.deprecated_fields,
                    'is_default': self.registry.default_versions.get(schema_name) == version_str
                })

        return schemas_info

    def get_schema_versions(self, schema_name: str) -> List[str]:
        """Get available versions for a schema"""
        return self.registry.get_available_versions(schema_name)


# Global schema manager instance
_schema_manager: Optional[ConfigurationSchemaManager] = None


def get_schema_manager() -> ConfigurationSchemaManager:
    """Get the global schema manager instance"""
    global _schema_manager
    if _schema_manager is None:
        _schema_manager = ConfigurationSchemaManager()
    return _schema_manager


# Convenience functions
def validate_configuration_schema(config_data: Dict[str, Any], version: Optional[str] = None) -> Dict[str, Any]:
    """Validate export configuration against schema"""
    manager = get_schema_manager()
    return manager.validate_schema("export_configuration", config_data, version)


def migrate_configuration(config_data: Dict[str, Any], from_version: str, to_version: str) -> Dict[str, Any]:
    """Migrate export configuration between versions"""
    manager = get_schema_manager()
    return manager.migrate_schema("export_configuration", config_data, from_version, to_version)
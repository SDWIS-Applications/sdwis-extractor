#!/usr/bin/env python3
"""
SDWIS Data Extractor CLI

Command-line interface for the modular SDWIS data extraction system.
Provides a unified interface for extracting water systems, legal entities,
and sample schedules.
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Load environment variables at the entry point
load_dotenv()

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.core.domain import ExtractionQuery, PaginationConfig
from modules.core.services import ExtractionService, BatchExtractionService
from modules.core.registry import get_default_registry, register_default_adapters, AdapterRegistryError
from modules.core.validation import ExtractionQueryValidator, InvalidExtractionQueryError
from modules.core.export_service import ExportService, ExportMode
from modules.core.export_configuration import ExportConfiguration, FileNamingPolicy
from modules.core.export_orchestration import ExportOrchestrationService
from modules.adapters.auth.http_validator import SDWISHttpAuthValidator
from modules.adapters.auth.sdwis_session import EnvironmentConfigAdapter
from modules.adapters.auth.browser_session import SDWISAuthenticatedBrowserSession, MockBrowserSession
from modules.adapters.extractors.native_sdwis import NativeSDWISExtractorAdapter, MockNativeSDWISExtractorAdapter
from modules.adapters.factories import OutputAdapterFactory


class CLIConfigAdapter:
    """Configuration adapter that wraps base config and applies CLI overrides"""

    def __init__(self, base_config, browser_config_override):
        self.base_config = base_config
        self.browser_config_override = browser_config_override

    def get_credentials(self):
        return self.base_config.get_credentials()

    def get_server_config(self):
        return self.base_config.get_server_config()

    def get_extraction_config(self):
        return self.base_config.get_extraction_config()

    def get_browser_config(self):
        return self.browser_config_override

    def validate_config(self):
        return self.base_config.validate_config()


class MockConfigAdapter:
    """Mock configuration adapter for testing"""

    def get_credentials(self):
        return {'username': 'test', 'password': 'test'}

    def get_server_config(self):
        return {'base_url': 'http://test:8080/SDWIS/'}

    def get_extraction_config(self):
        return {'batch_size': '1000'}

    def get_browser_config(self):
        return {'headless': True, 'timeout': 30000}

    def validate_config(self):
        return True


def create_progress_adapter_from_registry(registry, args):
    """Create progress adapter using registry"""
    progress_type = "silent" if args.quiet else "cli"

    if progress_type == "cli":
        return registry.get_progress_adapter(
            progress_type,
            cli_progress_type=args.progress_type,
            use_rich=not args.no_rich
        )
    else:
        return registry.get_progress_adapter(progress_type)


def create_output_adapter_from_registry(registry, args):
    """Create output adapter using registry"""
    format_name = args.format
    export_mode = args.export_mode

    # Validation: inspection mode only supports JSON - fix args.format before config creation
    if export_mode == 'inspection' and format_name != 'json':
        print("⚠️  Inspection mode only supports JSON format. Switching to JSON.")
        format_name = 'json'
        args.format = 'json'  # Update args so config creation uses correct format


    if format_name == "json":
        kwargs = {
            'indent': 2,
            'ensure_ascii': False
        }
        # Use enhanced JSON adapter
        from ..adapters.output.enhanced_json import create_enhanced_json_adapter
        return create_enhanced_json_adapter(export_mode=export_mode, **kwargs)

    elif format_name in ['csv', 'tsv']:
        csv_type = 'tsv' if format_name == 'tsv' else args.csv_type
        kwargs = {
            'use_pandas': True,
            'include_metadata': (csv_type == 'with_metadata'),
            'encoding': 'utf-8'
        }
        # Use enhanced CSV adapter
        from ..adapters.output.enhanced_csv import create_enhanced_csv_adapter
        return create_enhanced_csv_adapter(export_mode=export_mode, output_type=csv_type, **kwargs)

    # Fallback to registry for other formats
    return registry.get_output_adapter(format_name, **kwargs)


def get_inspection_schema_data_types() -> List[str]:
    """Get supported data types from inspection schema that have implemented extractors"""
    try:
        from ..adapters.export_schema.schema_loader import SchemaLoader
        loader = SchemaLoader("config/schemas")
        schema = loader.load_schema("inspection_report")

        # Only include data types that we have implemented extractors for
        implemented_extractors = {'water_systems', 'legal_entities', 'deficiency_types'}
        # Convert DataType enum values to strings
        schema_types = {dt.value for dt in schema.data_types.keys()}

        # Return intersection of schema types and implemented extractors
        return sorted(list(implemented_extractors.intersection(schema_types)))
    except Exception as e:
        # Fallback to hardcoded list if schema loading fails
        print(f"⚠️  Warning: Could not load inspection schema ({e}), using fallback defaults")
        return ['water_systems', 'legal_entities', 'deficiency_types']


def create_config_adapter_from_registry(registry, args):
    """Create configuration adapter using registry"""
    if args.mock:
        return MockConfigAdapter()
    else:
        return registry.get_config_adapter("environment", validate_on_access=False)


def create_export_configuration_from_args(args) -> ExportConfiguration:
    """Create export configuration from CLI arguments (pure adapter function)"""
    # Determine export mode
    export_mode = ExportMode.INSPECTION if args.export_mode == 'inspection' else ExportMode.GENERAL

    # Resolve format: CLI arg overrides extension detection, but None allows extension detection
    # Special case: inspection mode always requires JSON format
    if export_mode == ExportMode.INSPECTION:
        output_format = 'json'
    else:
        output_format = None if args.format == 'csv' and args.output else args.format

    return ExportConfiguration(
        data_types=args.data_types,
        export_mode=export_mode,
        output_format=output_format,  # Explicitly 'json' for inspection mode
        output_path=args.output,
        file_naming_policy=FileNamingPolicy()
    )


def get_browser_config_from_args(args, config_adapter):
    """Extract browser configuration from CLI args and config adapter."""
    # Start with config adapter defaults
    browser_config = config_adapter.get_browser_config()

    # Override with CLI arguments
    if args.headless:
        browser_config['headless'] = True
    elif args.no_headless:
        browser_config['headless'] = False

    return browser_config


def create_orchestration_service(registry, args, export_service: ExportService) -> ExportOrchestrationService:
    """Create orchestration service with proper adapters"""
    # Create progress adapter
    progress_adapter = create_progress_adapter_from_registry(registry, args)

    # Create config adapter with CLI overrides
    base_config_adapter = create_config_adapter_from_registry(registry, args)
    browser_config = get_browser_config_from_args(args, base_config_adapter)
    config_adapter = CLIConfigAdapter(base_config_adapter, browser_config)

    # Create authentication components
    if args.mock:
        http_validator = None
        browser_session_factory = registry.get_browser_session_factory("mock")
    else:
        http_validator = SDWISHttpAuthValidator()
        browser_session_factory = registry.get_browser_session_factory("sdwis")

    # Create extractor adapter (for first data type - batch service will handle multiples)
    primary_data_type = args.data_types[0]
    extractor_data_type = f"mock_{primary_data_type}" if args.mock else primary_data_type

    try:
        extractor_adapter = registry.get_extractor(extractor_data_type)
    except AdapterRegistryError:
        extractor_adapter = registry.get_extractor(primary_data_type)

    # Configure extractor if it supports configuration
    if hasattr(extractor_adapter, 'configure') and not args.mock:
        extractor_adapter.configure(
            browser_headless=True,
            progress_reporter=progress_adapter
        )

    # Create dummy output adapter for batch service (orchestration handles real output)
    from ..adapters.output.json import JSONOutputAdapter
    dummy_output_adapter = JSONOutputAdapter()

    # Create batch extraction service
    batch_service = BatchExtractionService(
        extractor=extractor_adapter,
        browser_session_factory=browser_session_factory,
        progress=progress_adapter,
        output=dummy_output_adapter,  # Orchestration service overrides this
        config=config_adapter,
        http_validator=http_validator
    )

    # Create output adapter factory and register it
    output_adapter_factory = OutputAdapterFactory(export_service)
    registry.register_output_adapter_factory("default", output_adapter_factory)

    # Get factory from registry for clean abstraction
    registered_factory = registry.get_output_adapter_factory("default")

    return ExportOrchestrationService(batch_service, export_service, registered_factory)


async def main():
    """Main CLI entry point"""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Apply defaults for inspection mode if no data types specified
    if args.export_mode == 'inspection' and not args.data_types:
        args.data_types = get_inspection_schema_data_types()
        print(f"📋 Inspection mode: Using default data types from schema: {', '.join(args.data_types)}")

    # Validate that at least one data type is specified
    if not args.data_types:
        print("❌ Error: No data types specified. Please specify at least one data type or use --export-mode inspection for defaults.")
        sys.exit(1)

    # Validate data types are valid choices
    valid_choices = ['water_systems', 'legal_entities', 'deficiency_types', 'sample_schedules']
    invalid_choices = [dt for dt in args.data_types if dt not in valid_choices]
    if invalid_choices:
        print(f"❌ Error: Invalid data types: {', '.join(invalid_choices)}")
        print(f"   Valid choices: {', '.join(valid_choices)}")
        sys.exit(1)

    # Early validation: inspection mode only supports implemented extractors with schema support
    if args.export_mode == 'inspection':
        supported_types = get_inspection_schema_data_types()
        invalid_types = [dt for dt in args.data_types if dt not in supported_types]
        if invalid_types:
            print(f"❌ Error: Inspection mode only supports {', '.join(supported_types)}.")
            print(f"   Invalid data types for inspection mode: {', '.join(invalid_types)}")
            print("   Use general mode for other data types.")
            sys.exit(1)

    try:
        # Initialize adapter registry
        registry = get_default_registry()
        register_default_adapters()

        # Create export configuration from CLI args (pure domain logic)
        export_config = create_export_configuration_from_args(args)

        # Quick connection test before proceeding
        if not args.mock:
            print("🔍 Testing connection to SDWIS server...")
            config_adapter = create_config_adapter_from_registry(registry, args)
            server_config = config_adapter.get_server_config()

            try:
                from ..adapters.auth.http_validator import SDWISHttpAuthValidator
                validator = SDWISHttpAuthValidator(base_url=server_config['base_url'], timeout_seconds=5)

                is_reachable = await validator.check_connectivity()
                if not is_reachable:
                    print("❌ SDWIS server is not reachable")
                    print(f"💡 Check hostname settings ({server_config['base_url']}) and network connection")
                    sys.exit(1)
                print("✅ SDWIS server is reachable")

            except Exception as e:
                print(f"❌ Connection test failed: {str(e)}")
                print(f"💡 Check hostname settings ({server_config['base_url']}) and network connection")
                sys.exit(1)

        # Validate configuration
        export_service = ExportService()
        orchestration_service = create_orchestration_service(registry, args, export_service)

        validation_result = await orchestration_service.validate_export_request(export_config)

        if not validation_result['valid']:
            print("❌ Export configuration validation failed:")
            for error in validation_result['errors']:
                print(f"   • {error}")
            if not args.verbose:
                print("\n💡 Use --verbose for more details")
            sys.exit(1)

        # Show validation warnings
        if validation_result.get('warnings') and not args.quiet:
            print("⚠️  Export configuration warnings:")
            for warning in validation_result['warnings']:
                print(f"   • {warning}")
            print()

        # Show preview if not quiet
        if not args.quiet:
            preview = validation_result['preview']
            print(f"📋 Export Preview:")
            print(f"   Data types: {', '.join(preview['data_types'])}")
            print(f"   Export mode: {preview['export_mode']}")
            print(f"   Output format: {preview['output_format']}")
            print(f"   Output files: {len(preview['output_paths'])}")
            for path in preview['output_paths']:
                print(f"      • {path}")
            print()

        # Perform configured export using orchestration service
        result = await orchestration_service.perform_configured_export(export_config)

        # Print results
        print_export_results(result, args)

        # Exit with appropriate code
        sys.exit(0 if result.get('success', False) else 1)

    except KeyboardInterrupt:
        print("\n🛑 Extraction cancelled by user")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser"""
    parser = argparse.ArgumentParser(
        description='SDWIS Data Extractor - Extract data from SDWIS web application',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Extract all water systems to CSV (default)
  python -m modules.cli.main water_systems -o water_systems.csv

  # Extract water systems to JSON for general use
  python -m modules.cli.main water_systems -o water_systems.json --format json

  # Extract data for inspection report (hierarchical JSON)
  python -m modules.cli.main water_systems -o inspection.json --export-mode inspection

  # Extract legal entities with exclusion patterns
  python -m modules.cli.main legal_entities -o entities.csv \\
    --exclude-pattern ".*ADDRESS.*" --exclude-pattern "^[A-Z]{2}\\d+$"

  # Extract deficiency types from Site Visit module
  python -m modules.cli.main deficiency_types -o deficiency_types.csv

  # Test with mock data
  python -m modules.cli.main water_systems --mock -o test.csv
        '''
    )

    # Positional arguments - support multiple data types
    parser.add_argument(
        'data_types',
        nargs='*',  # Allow zero or more (defaults can be applied)
        help='Type(s) of data to extract: water_systems, legal_entities, deficiency_types. Can specify multiple for batch extraction. If --export-mode inspection is used without data types, defaults to all types defined in inspection schema.'
    )

    # Output options
    parser.add_argument(
        '-o', '--output',
        default=None,
        help='Output file path (default: auto-generated with timestamp based on data type and format)'
    )

    parser.add_argument(
        '--format',
        choices=['json', 'csv', 'tsv'],
        default='csv',
        help='Output format (default: csv)'
    )

    parser.add_argument(
        '--export-mode',
        choices=['general', 'inspection'],
        default='general',
        help='Export mode: general (all fields) or inspection (selected fields, hierarchical JSON) (default: general)'
    )

    parser.add_argument(
        '--json-type',
        choices=['standard', 'detailed', 'compact'],
        default='standard',
        help='JSON output type (default: standard)'
    )

    parser.add_argument(
        '--csv-type',
        choices=['standard', 'with_metadata', 'tsv'],
        default='standard',
        help='CSV output type (default: standard)'
    )

    # Extraction options
    parser.add_argument(
        '--exclude-pattern',
        action='append',
        dest='exclusion_patterns',
        help='Exclusion regex pattern (can be used multiple times)'
    )

    parser.add_argument(
        '--search-param',
        action='append',
        dest='search_params',
        help='Search parameter as key=value (can be used multiple times)'
    )

    parser.add_argument(
        '--max-pages',
        type=int,
        help='Maximum number of pages to extract (for pagination)'
    )

    parser.add_argument(
        '--page-size',
        type=int,
        help='Page size for pagination'
    )

    # Progress and display options
    parser.add_argument(
        '--progress-type',
        choices=['auto', 'rich', 'simple', 'silent'],
        default='auto',
        help='Type of progress display (default: auto)'
    )

    parser.add_argument(
        '--no-rich',
        action='store_true',
        help='Disable rich terminal formatting'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress non-essential output'
    )

    # Testing and development options
    parser.add_argument(
        '--mock',
        action='store_true',
        help='Use mock data for testing (no actual SDWIS connection)'
    )

    parser.add_argument(
        '--headless',
        action='store_true',
        default=None,
        help='Run browser in headless mode (default: false, use --headless to enable)'
    )

    parser.add_argument(
        '--no-headless',
        action='store_true',
        help='Run browser with GUI visible (explicit override of environment/config)'
    )

    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate the query without extracting data'
    )

    parser.add_argument(
        '--check-auth',
        action='store_true',
        help='Check authentication status and exit'
    )

    parser.add_argument(
        '--list-adapters',
        action='store_true',
        help='List all available adapters and exit'
    )

    parser.add_argument(
        '--validate-config',
        action='store_true',
        help='Validate configuration with detailed feedback'
    )

    return parser


def print_export_results(result: Dict[str, Any], args):
    """Print export operation results"""
    if args.quiet:
        return

    if result.get('success'):
        results = result.get('results', [])
        output_paths = result.get('output_paths', [])

        print(f"✅ Export completed successfully!")

        for i, export_result in enumerate(results):
            if export_result.get('success'):
                count = export_result.get('count', 0)
                data_type = export_result.get('data_type', 'unknown')
                time_taken = export_result.get('extraction_time', 0)

                if data_type == 'inspection_report':
                    included_types = export_result.get('included_types', [])
                    print(f"📊 Inspection Report: {count} total records")
                    print(f"   Included types: {', '.join(included_types)}")
                else:
                    print(f"📊 {data_type.replace('_', ' ').title()}: {count} records")

                print(f"   ⏱️  Extraction time: {time_taken:.2f}s")

                if i < len(output_paths):
                    print(f"   📁 Output: {output_paths[i]}")

                # Print warnings/errors
                warnings = export_result.get('warnings', [])
                errors = export_result.get('errors', [])

                if warnings:
                    print(f"   ⚠️  {len(warnings)} warnings")
                    if args.verbose:
                        for warning in warnings:
                            print(f"      • {warning}")

                if errors:
                    print(f"   🚨 {len(errors)} errors")
                    for error in errors:
                        print(f"      • {error}")
            else:
                print(f"❌ {export_result.get('data_type', 'unknown')} extraction failed")

            print()  # Empty line between results

    else:
        print(f"❌ Export failed")

        if 'errors' in result:
            print("Validation errors:")
            for error in result['errors']:
                print(f"   • {error}")

        if 'error' in result:
            print(f"Error: {result['error']}")


# Removed old functions that are no longer needed in hexagonal architecture
# create_extraction_query - replaced by create_export_configuration_from_args
# print_results - replaced by print_export_results


# Removed: create_output_adapter function - now using registry


def print_results(result, args):
    """Print extraction results to console"""
    if args.quiet:
        return

    if result.success:
        print(f"✅ Successfully extracted {result.metadata.extracted_count} {args.data_type} records")

        if result.metadata.total_available:
            coverage = (result.metadata.extracted_count / result.metadata.total_available) * 100

            if result.metadata.extracted_count == result.metadata.total_available:
                print(f"📊 Coverage: {result.metadata.extracted_count}/{result.metadata.total_available} ({coverage:.1f}%) ✓ Complete")
            elif result.metadata.extracted_count < result.metadata.total_available:
                missing = result.metadata.total_available - result.metadata.extracted_count
                print(f"⚠️  Coverage: {result.metadata.extracted_count}/{result.metadata.total_available} ({coverage:.1f}%) - Missing {missing} records")
            else:
                extra = result.metadata.extracted_count - result.metadata.total_available
                print(f"⚠️  Coverage: {result.metadata.extracted_count}/{result.metadata.total_available} ({coverage:.1f}%) - {extra} extra records")

        print(f"⏱️  Extraction time: {result.metadata.extraction_time:.2f} seconds")

        if hasattr(result.metadata, 'pagination_info') and result.metadata.pagination_info:
            batches = result.metadata.pagination_info.get('batches_processed', 0)
            if batches > 1:
                print(f"📄 Processed {batches} batches")
    else:
        print(f"❌ Extraction failed for {args.data_type}")

    # Print warnings
    if result.warnings and not args.quiet:
        print(f"⚠️  {len(result.warnings)} warnings:")
        for warning in result.warnings:
            print(f"   • {warning}")

    # Print errors
    if result.errors:
        print(f"🚨 {len(result.errors)} errors:")
        for error in result.errors:
            print(f"   • {error}")

    if args.verbose and result.metadata.source_info:
        print(f"📋 Source info: {result.metadata.source_info}")


class nullcontext:
    """Null context manager for Python < 3.7 compatibility"""
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


async def validate_only_mode(service, query):
    """Handle validate-only mode"""
    is_valid = await service.validate_extraction_query(query)

    if is_valid:
        print("✅ Query validation successful")
        supported_types = await service.get_supported_data_types()
        print(f"📋 Supported data types: {', '.join(supported_types)}")
    else:
        print("❌ Query validation failed")

    return is_valid


async def check_auth_mode(service):
    """Handle check-auth mode using HTTP validation"""
    print("🔐 Testing authentication with SDWIS server...")

    # Check if service has HTTP validator
    if not service.http_validator:
        print("❌ HTTP authentication validation not available in mock mode")
        return False

    try:
        # Check connectivity first
        connectivity = await service.http_validator.check_connectivity()
        if not connectivity:
            print("❌ SDWIS server is not reachable")
            print("💡 Check your SDWIS_URL setting and network connectivity")
            return False

        print("📡 SDWIS server is reachable")

        # Validate credentials
        credentials = service.config.get_credentials()
        is_valid = await service.http_validator.validate_credentials(credentials)

        if is_valid:
            print("✅ Authentication successful")
            print(f"   Username: {credentials['username']}")
            return True
        else:
            print("❌ Authentication failed - invalid credentials")
            print("💡 Check your SDWIS_USERNAME and SDWIS_PASSWORD")
            return False
    except Exception as e:
        print(f"❌ Authentication test failed: {e}")
        print("💡 Set SDWIS_USERNAME and SDWIS_PASSWORD environment variables")
        return False


def list_adapters_mode():
    """Handle list-adapters mode"""
    print("📋 Available SDWIS Adapters\n")

    registry = get_default_registry()
    register_default_adapters()

    all_adapters = registry.get_all_registered_adapters()

    for adapter_type, adapters in all_adapters.items():
        if not adapters:
            continue

        print(f"🔧 {adapter_type.replace('_', ' ').title()}:")
        for adapter in sorted(adapters, key=lambda x: -x.priority):
            print(f"   • {adapter.name}")
            if adapter.description:
                print(f"     {adapter.description}")
            if adapter.supported_features:
                print(f"     Features: {', '.join(adapter.supported_features)}")
            if adapter.dependencies:
                print(f"     Dependencies: {', '.join(adapter.dependencies)}")
            print()
        print()


def validate_config_mode():
    """Handle validate-config mode"""
    print("🔍 Validating SDWIS Configuration\n")

    registry = get_default_registry()
    register_default_adapters()

    try:
        config_adapter = registry.get_config_adapter("environment", validate_on_access=False)
        validation_result = config_adapter.validate_config_detailed()

        if validation_result.valid:
            print("✅ Configuration is valid")
        else:
            print("❌ Configuration validation failed:")
            print(validation_result.get_error_summary())

        return validation_result.valid

    except Exception as e:
        print(f"❌ Configuration validation error: {e}")
        return False


if __name__ == "__main__":
    # Handle special modes before main execution
    if len(sys.argv) > 1:
        # Handle list-adapters mode
        if '--list-adapters' in sys.argv:
            list_adapters_mode()
            sys.exit(0)

        # Handle validate-config mode
        if '--validate-config' in sys.argv:
            is_valid = validate_config_mode()
            sys.exit(0 if is_valid else 1)

        if '--validate-only' in sys.argv:
            # Quick validation mode
            parser = create_argument_parser()
            args = parser.parse_args()

            export_config = create_export_configuration_from_args(args)
            config_adapter = EnvironmentConfigAdapter()

            if args.mock:
                extractor_adapter = MockNativeSDWISExtractorAdapter()
                http_validator = None
                browser_session_factory = lambda: MockBrowserSession()
            else:
                extractor_adapter = NativeSDWISExtractorAdapter()
                http_validator = SDWISHttpAuthValidator()
                browser_session_factory = lambda: SDWISAuthenticatedBrowserSession()

            from modules.adapters.progress.silent import SilentProgressAdapter
            from modules.adapters.output.json import JSONOutputAdapter

            service = ExtractionService(
                extractor=extractor_adapter,
                browser_session_factory=browser_session_factory,
                progress=SilentProgressAdapter(),
                output=JSONOutputAdapter(),
                config=config_adapter,
                http_validator=http_validator
            )

            # Create extraction query from export config (use first data type)
            query = ExtractionQuery(
                data_type=export_config.data_types[0],
                filters={},
                pagination=PaginationConfig(auto_paginate=True),
                metadata={
                    'export_mode': export_config.export_mode.value,
                    'output_format': export_config.resolve_output_format()
                }
            )
            is_valid = asyncio.run(validate_only_mode(service, query))
            sys.exit(0 if is_valid else 1)

        elif '--check-auth' in sys.argv:
            # Quick auth check mode
            config_adapter = EnvironmentConfigAdapter()

            # Check if mock mode is specified
            if '--mock' in sys.argv:
                http_validator = None
                browser_session_factory = lambda: MockBrowserSession()
                extractor_adapter = MockNativeSDWISExtractorAdapter()
            else:
                http_validator = SDWISHttpAuthValidator()
                browser_session_factory = lambda: SDWISAuthenticatedBrowserSession()
                extractor_adapter = NativeSDWISExtractorAdapter()

            from modules.adapters.progress.silent import SilentProgressAdapter
            from modules.adapters.output.json import JSONOutputAdapter

            service = ExtractionService(
                extractor=extractor_adapter,
                browser_session_factory=browser_session_factory,
                progress=SilentProgressAdapter(),
                output=JSONOutputAdapter(),
                config=config_adapter,
                http_validator=http_validator
            )

            is_authenticated = asyncio.run(check_auth_mode(service))
            sys.exit(0 if is_authenticated else 1)

    # Run main CLI
    asyncio.run(main())
"""
Export Orchestration Service

Core service for orchestrating complex export operations including multi-type
extractions, format resolution, and output coordination.
"""

from typing import List, Dict, Any, Optional
import asyncio
from datetime import datetime

from .domain import ExtractionQuery, ExtractionResult, PaginationConfig
from .export_configuration import ExportConfiguration, ExportMode
from .export_service import ExportService
from .services import BatchExtractionService
from .ports import (
    ExtractionPort, OutputPort, ProgressReportingPort, ConfigurationPort,
    AuthenticatedBrowserSessionPort, AuthenticationValidationPort
)
from .factory_ports import OutputAdapterFactoryPort, EventPublisherPort
from .exceptions import ExportError, ErrorTranslator, ErrorBoundary
from .domain_events import (
    EventBuilder, ExportStartedEvent, ExportCompletedEvent,
    ExportFailedEvent, EventSeverity, InMemoryEventBus
)
from uuid import uuid4


class ExportOrchestrationService:
    """
    Service for orchestrating complex export operations.

    Coordinates between extraction, transformation, and output services
    while maintaining hexagonal architecture principles.
    """

    def __init__(
        self,
        batch_extraction_service: BatchExtractionService,
        export_service: ExportService,
        output_adapter_factory: OutputAdapterFactoryPort,
        event_publisher: Optional[EventPublisherPort] = None
    ):
        self.batch_extraction_service = batch_extraction_service
        self.export_service = export_service
        self.output_adapter_factory = output_adapter_factory
        self.event_publisher = event_publisher or InMemoryEventBus()
        self._enable_events = True  # Domain events enabled

    async def perform_configured_export(
        self,
        export_config: ExportConfiguration
    ) -> Dict[str, Any]:
        """
        Perform export operation based on configuration.

        Args:
            export_config: Complete export configuration

        Returns:
            Dictionary with operation results
        """
        # Validate configuration with enhanced error handling
        try:
            export_config.validate_or_raise()
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'errors': getattr(e, 'configuration_errors', [str(e)]),
                'export_config': export_config
            }

        try:
            # Generate aggregate ID for this export operation
            aggregate_id = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{id(export_config)}"

            # Publish export started event
            if self._enable_events:
                await self.event_publisher.publish(
                    EventBuilder.create_export_started(
                        aggregate_id=aggregate_id,
                        data_types=export_config.data_types,
                        export_mode=export_config.export_mode.value,
                        output_format=export_config.resolve_output_format(),
                        context={'configuration': export_config.__dict__}
                    )
                )

            # Create extraction queries
            queries = self._create_extraction_queries(export_config)

            # Resolve output paths
            output_paths = export_config.generate_output_paths()

            # Perform extractions
            if export_config.export_mode == ExportMode.INSPECTION and len(export_config.data_types) > 1:
                # Special handling for multi-type inspection
                results = await self._perform_inspection_multi_type_export(
                    queries, output_paths[0], export_config
                )
            else:
                # Standard batch extraction
                results = await self._perform_standard_batch_export(
                    queries, output_paths, export_config
                )

            # Calculate totals for completion event
            total_records = sum(r.get('count', 0) for r in results if r and isinstance(r, dict))
            execution_time = sum(r.get('extraction_time', 0) for r in results if r and isinstance(r, dict))

            # Publish export completed event
            if self._enable_events:
                completed_event = ExportCompletedEvent(
                    event_id=str(uuid4()),
                    timestamp=datetime.now(),
                    event_type='ExportCompleted',
                    aggregate_id=aggregate_id,
                    severity=EventSeverity.INFO,
                    context={'results': results},
                    data_types=export_config.data_types,
                    export_mode=export_config.export_mode.value,
                    output_paths=output_paths,
                    total_records=total_records,
                    execution_time_seconds=execution_time
                )
                await self.event_publisher.publish(completed_event)

            return {
                'success': True,
                'results': results,
                'output_paths': output_paths,
                'export_config': export_config,
                'aggregate_id': aggregate_id
            }

        except Exception as e:
            # Translate infrastructure errors to domain errors
            domain_error = ErrorTranslator.translate_extraction_error(e, str(export_config.data_types))

            # Publish export failed event
            if self._enable_events:
                await self.event_publisher.publish(
                    EventBuilder.create_export_failed(
                        aggregate_id=aggregate_id if 'aggregate_id' in locals() else 'unknown',
                        data_types=export_config.data_types,
                        export_mode=export_config.export_mode.value,
                        error_message=str(domain_error),
                        error_type=type(e).__name__,
                        context={'original_error': str(e)}
                    )
                )

            return {
                'success': False,
                'error': str(domain_error),
                'export_config': export_config,
                'original_error': str(e),
                'aggregate_id': aggregate_id if 'aggregate_id' in locals() else 'unknown'
            }

    def _create_extraction_queries(
        self,
        export_config: ExportConfiguration
    ) -> List[ExtractionQuery]:
        """Create extraction queries from configuration"""
        queries = []

        for data_type in export_config.data_types:
            query = ExtractionQuery(
                data_type=data_type,
                filters={},  # TODO: Support filters from config
                pagination=PaginationConfig(auto_paginate=True),
                metadata={
                    'export_mode': export_config.export_mode.value,
                    'output_format': export_config.resolve_output_format()
                }
            )
            queries.append(query)

        return queries

    async def _perform_standard_batch_export(
        self,
        queries: List[ExtractionQuery],
        output_paths: List[str],
        export_config: ExportConfiguration
    ) -> List[Dict[str, Any]]:
        """Perform standard batch extraction with individual outputs"""

        # Extract data first (without output - we'll handle output ourselves)
        extraction_results = await self.batch_extraction_service.perform_batch_extraction(queries)

        # Now save each result to its corresponding output path
        results = []
        for i, (result, output_path) in enumerate(zip(extraction_results, output_paths)):
            try:
                # Create appropriate output adapter using factory
                output_adapter = self.output_adapter_factory.create_adapter(
                    export_config.resolve_output_format(),
                    export_config.export_mode
                )

                # Save the data
                save_success = await output_adapter.save_data(result, output_path)

                results.append({
                    'data_type': result.metadata.data_type,
                    'success': result.success and save_success,
                    'count': result.metadata.extracted_count,
                    'output_path': output_path,
                    'extraction_time': result.metadata.extraction_time,
                    'errors': result.errors,
                    'warnings': result.warnings
                })

            except Exception as e:
                results.append({
                    'data_type': result.metadata.data_type,
                    'success': False,
                    'count': result.metadata.extracted_count,
                    'output_path': output_path,
                    'extraction_time': result.metadata.extraction_time,
                    'errors': result.errors + [f"Output save failed: {str(e)}"],
                    'warnings': result.warnings
                })

        return results

    async def _perform_inspection_multi_type_export(
        self,
        queries: List[ExtractionQuery],
        output_path: str,
        export_config: ExportConfiguration
    ) -> List[Dict[str, Any]]:
        """Perform multi-type inspection export to single hierarchical JSON"""

        # Extract all data types
        extraction_results = await self.batch_extraction_service.perform_batch_extraction(queries)

        # Create JSON adapter for inspection mode using factory
        json_adapter = self.output_adapter_factory.create_json_adapter(
            export_mode=ExportMode.INSPECTION
        )

        # Prepare multi-type extraction results dictionary
        extraction_results_dict = {}
        for result in extraction_results:
            extraction_results_dict[result.metadata.data_type] = result

        # Save combined inspection report
        success = await json_adapter.save_multi_type_data(
            extraction_results_dict,
            output_path,
            export_config.data_types
        )

        # Return summary
        total_count = sum(result.metadata.extracted_count for result in extraction_results)
        all_errors = []
        all_warnings = []

        for result in extraction_results:
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)

        return [{
            'data_type': 'inspection_report',
            'success': success and all(result.success for result in extraction_results),
            'count': total_count,
            'output_path': output_path,
            'extraction_time': sum(result.metadata.extraction_time for result in extraction_results),
            'included_types': export_config.data_types,
            'errors': all_errors,
            'warnings': all_warnings
        }]


    async def validate_export_request(
        self,
        export_config: ExportConfiguration
    ) -> Dict[str, Any]:
        """Validate export request and provide feedback"""
        errors = export_config.get_validation_errors()
        warnings = []

        # Check export service compatibility
        try:
            supported_formats = self.export_service.get_supported_formats_for_mode(
                export_config.export_mode
            )
            resolved_format = export_config.resolve_output_format()

            if resolved_format not in supported_formats:
                errors.append(
                    f"Format '{resolved_format}' not supported for {export_config.export_mode.value} mode. "
                    f"Supported formats: {supported_formats}"
                )
        except Exception as e:
            warnings.append(f"Could not validate format compatibility: {e}")

        # Generate preview of what will be exported
        output_paths = export_config.generate_output_paths()

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'preview': {
                'data_types': export_config.data_types,
                'export_mode': export_config.export_mode.value,
                'output_format': export_config.resolve_output_format(),
                'output_paths': output_paths
            }
        }
"""
Core business logic services for SDWIS data extraction.

This module contains the pure business logic that orchestrates the extraction
process using the defined ports. It's independent of any infrastructure concerns.
"""

import time
from typing import Optional

from .domain import (
    ExtractionMetadata, ExtractionQuery, ExtractionResult, ProgressUpdate
)
from .ports import (
    AuthenticationValidationPort, AuthenticatedBrowserSessionPort, ConfigurationPort, ExtractionPort,
    OutputPort, ProgressReportingPort,
    AuthenticationError, ConfigurationError, ExtractionError
)
from .session_manager import BrowserSessionManager, managed_browser_session


class ExtractionService:
    """
    Core extraction business logic.

    This service orchestrates the complete extraction workflow using injected
    adapters for different infrastructure concerns.
    """

    def __init__(
        self,
        extractor: ExtractionPort,
        browser_session_factory: callable,  # Factory function that creates AuthenticatedBrowserSessionPort
        progress: ProgressReportingPort,
        output: OutputPort,
        config: ConfigurationPort,
        http_validator: Optional[AuthenticationValidationPort] = None,
        reuse_session: bool = False
    ):
        self.extractor = extractor
        self.browser_session_factory = browser_session_factory
        self.progress = progress
        self.output = output
        self.config = config
        self.http_validator = http_validator
        self.reuse_session = reuse_session
        self._shared_browser_session: Optional[AuthenticatedBrowserSessionPort] = None

    async def perform_extraction(
        self,
        query: ExtractionQuery,
        output_destination: Optional[str] = None
    ) -> ExtractionResult:
        """
        Main extraction workflow.

        Args:
            query: ExtractionQuery specifying what to extract
            output_destination: Optional path to save results

        Returns:
            ExtractionResult with extracted data and metadata

        Raises:
            AuthenticationError: If authentication fails
            ExtractionError: If extraction fails
            ConfigurationError: If configuration is invalid
        """
        start_time = time.time()
        service_times = {}

        browser_session = None
        try:
            # Initialize progress reporting
            step_start = time.time()
            steps = 4 if self.http_validator else 3  # optional http validation, browser session, extract, output
            self.progress.set_total_steps(steps)
            service_times['init_progress'] = time.time() - step_start
            print(f"⏱️  Service init progress: {service_times['init_progress']:.3f}s")

            # Optional Step 1: HTTP validation for fast fail
            if self.http_validator:
                step_start = time.time()
                self.progress.increment_step("Validating credentials")
                credentials = self.config.get_credentials()
                if not await self.http_validator.validate_credentials(credentials):
                    raise AuthenticationError("Credential validation failed")
                service_times['http_validation'] = time.time() - step_start
                print(f"⏱️  Service HTTP validation: {service_times['http_validation']:.3f}s")

            # Step 2: Create or reuse authenticated browser session
            step_start = time.time()
            if self.reuse_session and self._shared_browser_session and self._shared_browser_session.is_authenticated():
                self.progress.increment_step("Reusing authenticated browser session")
                browser_session = self._shared_browser_session
            else:
                self.progress.increment_step("Creating authenticated browser session")
                browser_session = await self._create_authenticated_session()
                if self.reuse_session:
                    self._shared_browser_session = browser_session
            service_times['create_session'] = time.time() - step_start
            print(f"⏱️  Service create session: {service_times['create_session']:.3f}s")

            # Step 3: Perform extraction with browser session
            step_start = time.time()
            self.progress.increment_step("Extracting data from SDWIS")
            result = await self.extractor.extract_data(query, browser_session)
            service_times['extraction'] = time.time() - step_start
            print(f"⏱️  Service extraction call: {service_times['extraction']:.3f}s")

            # Update timing metadata but preserve extractor's internal timing
            total_service_time = time.time() - start_time
            print(f"⏱️  Total service time: {total_service_time:.3f}s")
            print(f"⏱️  Extractor reported time: {result.metadata.extraction_time:.3f}s")

            # Don't overwrite extractor timing - it's more granular
            if result.metadata.extraction_time == 0.0:
                result.metadata.extraction_time = total_service_time

            # Step 4: Save output if requested
            if output_destination:
                step_start = time.time()
                self.progress.increment_step("Saving extracted data")
                await self._save_extraction_result(result, output_destination)
                service_times['save_output'] = time.time() - step_start
                print(f"⏱️  Service save output: {service_times['save_output']:.3f}s")
            else:
                self.progress.update_progress(100, "Extraction completed successfully")

            return result

        except Exception as e:
            # Create error result
            error_result = ExtractionResult(
                success=False,
                data=[],
                metadata=ExtractionMetadata(
                    extracted_count=0,
                    extraction_time=time.time() - start_time,
                    data_type=query.data_type
                ),
                errors=[str(e)]
            )

            if output_destination:
                # Still attempt to save error result for debugging
                try:
                    await self._save_extraction_result(error_result, output_destination)
                except Exception as save_error:
                    error_result.errors.append(f"Failed to save error result: {save_error}")

            return error_result
        finally:
            # Clean up browser session (only if not reusing)
            if browser_session and not self.reuse_session:
                try:
                    await browser_session.close()
                except Exception:
                    pass  # Ignore cleanup errors

    async def validate_extraction_query(self, query: ExtractionQuery) -> bool:
        """
        Validate an extraction query without performing the extraction.

        Args:
            query: ExtractionQuery to validate

        Returns:
            True if query is valid, False otherwise
        """
        try:
            await self._validate_extraction_query(query)
            return True
        except Exception:
            return False

    async def get_supported_data_types(self) -> list[str]:
        """
        Get list of data types supported by the configured extractor.

        Returns:
            List of supported data type strings
        """
        return self.extractor.get_supported_data_types()

    async def check_authentication_status(self) -> bool:
        """
        Check if credentials are valid using HTTP-only validation.

        Returns:
            True if credentials are valid, False otherwise
        """
        if not self.http_validator:
            return True  # Can't validate without HTTP validator

        try:
            credentials = self.config.get_credentials()
            return await self.http_validator.validate_credentials(credentials)
        except Exception:
            return False

    async def cleanup_session(self) -> None:
        """
        Close shared browser session and clean up resources.

        This should be called when done with all extractions if session reuse is enabled.
        """
        if self._shared_browser_session:
            try:
                await self._shared_browser_session.close()
            except Exception:
                pass  # Ignore cleanup errors
            finally:
                self._shared_browser_session = None

    def managed_session(self, auto_reset: bool = False) -> BrowserSessionManager:
        """
        Create a context manager for browser session lifecycle.

        Usage:
            async with service.managed_session() as session:
                result1 = await extractor1.extract_data(query1, session)
                result2 = await extractor2.extract_data(query2, session)
                # Session automatically cleaned up

        Args:
            auto_reset: Whether to automatically reset navigation between operations

        Returns:
            BrowserSessionManager context manager
        """
        return BrowserSessionManager(
            browser_session_factory=self.browser_session_factory,
            config=self.config,
            auto_reset=auto_reset
        )

    async def _create_authenticated_session(self) -> AuthenticatedBrowserSessionPort:
        """
        Create and authenticate a browser session.

        Returns:
            Authenticated browser session

        Raises:
            AuthenticationError: If authentication fails
            ConfigurationError: If credentials are not available
        """
        try:
            credentials = self.config.get_credentials()
        except Exception as e:
            raise ConfigurationError(f"Failed to get credentials: {e}")

        try:
            browser_session = self.browser_session_factory()
            browser_config = self.config.get_browser_config()
            authenticated_session = await browser_session.authenticate(credentials, browser_config)

            if not authenticated_session.is_authenticated():
                raise AuthenticationError("Authentication succeeded but session is invalid")

            return authenticated_session
        except Exception as e:
            if isinstance(e, (AuthenticationError, ConfigurationError)):
                raise
            raise AuthenticationError(f"Failed to create authenticated browser session: {e}")

    async def _validate_extraction_query(self, query: ExtractionQuery) -> None:
        """
        Validate that the extraction query is valid and can be executed.

        Args:
            query: ExtractionQuery to validate

        Raises:
            ExtractionError: If query is invalid
        """
        # Validate configuration
        if not self.config.validate_config():
            raise ExtractionError("Invalid configuration")

        # Validate with extractor
        if not await self.extractor.validate_query(query):
            raise ExtractionError(f"Query validation failed for data type: {query.data_type}")

        # Validate data type is supported
        supported_types = self.extractor.get_supported_data_types()
        if query.data_type not in supported_types:
            raise ExtractionError(
                f"Data type '{query.data_type}' not supported. "
                f"Supported types: {supported_types}"
            )

    async def _save_extraction_result(
        self,
        result: ExtractionResult,
        destination: str
    ) -> None:
        """
        Save extraction result to specified destination.

        Args:
            result: ExtractionResult to save
            destination: Output destination

        Raises:
            ExtractionError: If save operation fails
        """
        try:
            success = await self.output.save_data(result, destination)
            if not success:
                raise ExtractionError(f"Failed to save data to {destination}")
        except Exception as e:
            raise ExtractionError(f"Save operation failed: {e}")


class BatchExtractionService(ExtractionService):
    """
    Extended service for batch extraction operations.

    Handles multiple extraction queries in sequence or parallel.
    Automatically enables session reuse for efficiency.
    """

    def __init__(self, *args, **kwargs):
        # Enable session reuse by default for batch operations
        kwargs.setdefault('reuse_session', True)
        super().__init__(*args, **kwargs)

    async def perform_batch_extraction(
        self,
        queries: list[ExtractionQuery],
        output_destinations: Optional[list[str]] = None
    ) -> list[ExtractionResult]:
        """
        Perform multiple extractions in sequence.

        Args:
            queries: List of ExtractionQuery objects
            output_destinations: Optional list of output destinations (same length as queries)

        Returns:
            List of ExtractionResult objects
        """
        if output_destinations and len(output_destinations) != len(queries):
            raise ValueError("output_destinations must be same length as queries")

        results = []
        total_queries = len(queries)

        for i, query in enumerate(queries):
            destination = output_destinations[i] if output_destinations else None

            self.progress.update_progress(
                int((i / total_queries) * 100),
                f"Processing query {i + 1} of {total_queries}: {query.data_type}"
            )

            result = await self.perform_extraction(query, destination)
            results.append(result)

            # Add batch context to source_info
            if not hasattr(result.metadata, 'source_info') or not result.metadata.source_info:
                result.metadata.source_info = {}
            result.metadata.source_info.update({
                "batch_index": i,
                "batch_total": total_queries,
                "batch_id": f"batch_{int(time.time())}"
            })

        self.progress.update_progress(100, f"Completed {total_queries} extractions")

        # Clean up shared session after all extractions
        if self.reuse_session and total_queries > 1:
            try:
                await self.cleanup_session()
            except Exception:
                pass  # Ignore cleanup errors

        return results
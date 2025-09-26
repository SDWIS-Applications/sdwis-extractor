"""
Native SDWIS Extractor Adapter

Uses the new purpose-built extractors instead of wrapping existing ones.
Provides clean integration with the modular architecture.
"""

import os
from typing import List, Dict, Any, Optional

from ...core.domain import ExtractionQuery, ExtractionResult, ExtractionMetadata
from ...core.ports import ExtractionPort, ExtractionError, ProgressReportingPort, AuthenticatedBrowserSessionPort

from .water_systems import WaterSystemsExtractor
from .legal_entities import LegalEntitiesExtractor
# from .sample_schedules import SampleSchedulesExtractor  # TODO: Add when extractor is ready
from .deficiency_types import DeficiencyTypesExtractor


class NativeSDWISExtractorAdapter:
    """Native SDWIS extractor using purpose-built extractors"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        browser_headless: bool = True,
        timeout_ms: int = 30000,
        progress_reporter: Optional[ProgressReportingPort] = None
    ):
        self.base_url = base_url or os.getenv('SDWIS_URL', 'http://sdwis:8080/SDWIS/')
        self.browser_headless = browser_headless
        self.timeout_ms = timeout_ms
        self.progress = progress_reporter

        # Initialize extractors
        self._extractors = {
            'water_systems': WaterSystemsExtractor(
                base_url=self.base_url,
                browser_headless=self.browser_headless,
                timeout_ms=self.timeout_ms,
                progress_reporter=self.progress
            ),
            'legal_entities': LegalEntitiesExtractor(
                base_url=self.base_url,
                browser_headless=self.browser_headless,
                timeout_ms=self.timeout_ms,
                progress_reporter=self.progress
            ),
            'deficiency_types': DeficiencyTypesExtractor(
                base_url=self.base_url,
                browser_headless=self.browser_headless,
                timeout_ms=self.timeout_ms,
                progress_reporter=self.progress
            )
        }

    def get_supported_data_types(self) -> List[str]:
        """Get list of supported data types"""
        return list(self._extractors.keys())

    async def validate_query(self, query: ExtractionQuery) -> bool:
        """Validate extraction query"""
        if query.data_type not in self._extractors:
            return False

        extractor = self._extractors[query.data_type]
        return await extractor.validate_query(query)

    async def extract_data(self, query: ExtractionQuery, browser_session: AuthenticatedBrowserSessionPort) -> ExtractionResult:
        """Extract data using the appropriate native extractor"""
        if query.data_type not in self._extractors:
            return ExtractionResult(
                success=False,
                data=[],
                metadata=ExtractionMetadata(
                    extracted_count=0,
                    extraction_time=0.0,
                    data_type=query.data_type
                ),
                errors=[f"Unsupported data type: {query.data_type}"]
            )

        extractor = self._extractors[query.data_type]

        try:
            # Execute extraction with browser session
            result = await extractor.extract_data(query, browser_session)

            # Enhance result with adapter metadata
            result.metadata.source_info.update({
                "adapter": "NativeSDWISExtractorAdapter",
                "adapter_version": "1.0.0",
                "extraction_architecture": "hexagonal_native"
            })

            return result

        except Exception as e:
            return ExtractionResult(
                success=False,
                data=[],
                metadata=ExtractionMetadata(
                    extracted_count=0,
                    extraction_time=0.0,
                    data_type=query.data_type,
                    source_info={
                        "adapter": "NativeSDWISExtractorAdapter",
                        "error_context": "extract_data"
                    }
                ),
                errors=[f"Native extraction failed: {str(e)}"]
            )

    async def _setup_authentication_context(self, extractor):
        """Setup authentication context for the extractor"""
        # Check if we have a valid authentication session
        if await self.auth.is_authenticated():
            session = await self.auth.get_current_session()
            if session:
                # Pass authentication context to extractor if needed
                # This could be implemented as needed by specific extractors
                pass

    def get_extractor(self, data_type: str) -> Optional[ExtractionPort]:
        """Get the specific extractor for a data type"""
        return self._extractors.get(data_type)


class MockNativeSDWISExtractorAdapter(NativeSDWISExtractorAdapter):
    """Mock version for testing"""

    def __init__(self, mock_data: Optional[Dict[str, List[Dict[str, Any]]]] = None):
        # Don't call super().__init__ to avoid creating real extractors
        if mock_data is not None:
            self.mock_data = mock_data
        else:
            self.mock_data = {
            "water_systems": [
                {
                    "Water System No.": "0010001",
                    "Name": "TEST WATER SYSTEM",
                    "Activity Status": "A",
                    "Sources": "GW",
                    "Types": "CWS",
                    "Population": "1000",
                    "County": "TEST COUNTY"
                }
            ],
            "legal_entities": [
                {
                    "Individual Name": "SMITH, JOHN",
                    "Status": "ACTIVE",
                    "Organization": "TEST ORGANIZATION",
                    "Mail Stop": "123 MAIN ST",
                    "State Code": "MS",
                    "ID Number": "12345",
                    "Entity Type": "INDIVIDUAL"
                }
            ],
            "deficiency_types": [
                {
                    "Type Code": "CG000",
                    "Default Severity Code": "SIG",
                    "Default Category Code": "",
                    "Description": "Significant Deficiency Not Otherwise Specified (Choose Category)",
                    "row_index": 1
                },
                {
                    "Type Code": "CG100",
                    "Default Severity Code": "",
                    "Default Category Code": "SO",
                    "Description": "Source Water Quality",
                    "row_index": 2
                },
                {
                    "Type Code": "CG201",
                    "Default Severity Code": "",
                    "Default Category Code": "TR",
                    "Description": "Function and Condition of Treatment Facilities",
                    "row_index": 3
                }
            ]
            # Note: sample_schedules removed from mock data - extractor not ready for production
            # TODO: Re-add sample_schedules when SampleSchedulesExtractor is fully implemented
            # "sample_schedules": [
            #     {
            #         "Schedule ID": "SCH-001",
            #         "System ID": "MS0300001",
            #         "Sample Type": "ROUTINE",
            #         "Frequency": "MONTHLY",
            #         "Parameter": "COLIFORM",
            #         "Status": "ACTIVE"
            #     }
            # ]
        }

    def get_supported_data_types(self) -> List[str]:
        """Get supported data types"""
        return list(self.mock_data.keys())

    async def validate_query(self, query: ExtractionQuery) -> bool:
        """Validate query for mock data"""
        return query.data_type in self.mock_data

    async def extract_data(self, query: ExtractionQuery, browser_session: AuthenticatedBrowserSessionPort) -> ExtractionResult:
        """Return mock data"""
        import time
        import asyncio

        start_time = time.time()

        # Simulate some processing time
        await asyncio.sleep(0.1)

        # Check if query is valid
        if query.data_type not in self.mock_data:
            return ExtractionResult(
                success=False,
                data=[],
                metadata=ExtractionMetadata(
                    extracted_count=0,
                    extraction_time=time.time() - start_time,
                    data_type=query.data_type,
                    source_info={
                        'adapter': 'MockNativeSDWISExtractorAdapter',
                        'mock_data': True,
                        'extraction_architecture': 'hexagonal_native_mock'
                    }
                ),
                errors=[f"Unsupported data type: {query.data_type}"]
            )

        data = self.mock_data.get(query.data_type, [])

        return ExtractionResult(
            success=True,
            data=data,
            metadata=ExtractionMetadata(
                extracted_count=len(data),
                extraction_time=time.time() - start_time,
                data_type=query.data_type,
                source_info={
                    "adapter": "MockNativeSDWISExtractorAdapter",
                    "mock_data": True,
                    "extraction_architecture": "hexagonal_native_mock"
                }
            )
        )
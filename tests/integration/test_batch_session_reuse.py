"""
Integration tests for batch extraction with session reuse functionality.

Tests the BatchExtractionService to verify:
1. Automatic session reuse for multiple queries
2. Proper cleanup after batch completion
3. Performance improvements over individual extractions
"""

import asyncio
import time
import pytest

from modules.core.domain import ExtractionQuery, PaginationConfig
from modules.core.services import ExtractionService, BatchExtractionService
from modules.adapters.extractors.native_sdwis import MockNativeSDWISExtractorAdapter
from modules.adapters.progress.silent import SilentProgressAdapter
from modules.adapters.output.json import JSONOutputAdapter


class MockConfigAdapter:
    """Mock configuration adapter for testing"""

    def get_credentials(self):
        return {'username': 'test', 'password': 'test'}

    def get_server_config(self):
        return {'base_url': 'http://test:8080/SDWIS/'}

    def get_extraction_config(self):
        return {'batch_size': '1000'}

    def get_browser_config(self):
        return {'headless': True, 'timeout': 60000}

    def validate_config(self):
        return True


class MockBrowserSession:
    """Mock browser session with timing simulation"""

    _instance_counter = 0

    def __init__(self):
        MockBrowserSession._instance_counter += 1
        self.instance_id = MockBrowserSession._instance_counter
        self._authenticated = False
        self.auth_call_count = 0

    async def authenticate(self, credentials, browser_config=None):
        # Simulate authentication delay on first call
        if self.auth_call_count == 0:
            await asyncio.sleep(0.1)  # 100ms authentication delay
        self.auth_call_count += 1
        self._authenticated = True
        return self

    async def get_page(self):
        if not self._authenticated:
            raise Exception("Not authenticated")
        return None  # Mock page

    async def get_context(self):
        if not self._authenticated:
            raise Exception("Not authenticated")
        return None  # Mock context

    def is_authenticated(self):
        return self._authenticated

    async def close(self):
        self._authenticated = False
        # Don't reset auth_call_count - we need it for testing
        # self.auth_call_count = 0

    async def navigate_to_module(self, url):
        pass

    async def take_screenshot(self, path):
        pass

    async def reset_to_home(self):
        pass


@pytest.mark.asyncio
async def test_individual_extractions():
    """Test multiple individual extractions (baseline)"""
    print("🧪 Testing individual extractions (baseline)...")

    results = []
    times = []
    total_auth_calls = 0

    # Get supported data types from mock extractor
    mock_extractor = MockNativeSDWISExtractorAdapter()
    supported_types = mock_extractor.get_supported_data_types()

    for i, data_type in enumerate(supported_types):
        print(f"  {i+1}. Extracting {data_type}...")

        # Create individual service (no session reuse)
        browser_session = MockBrowserSession()

        service = ExtractionService(
            extractor=MockNativeSDWISExtractorAdapter(),
            browser_session_factory=lambda bs=browser_session: bs,
            progress=SilentProgressAdapter(),
            output=JSONOutputAdapter(),
            config=MockConfigAdapter(),
            http_validator=None,
            reuse_session=False
        )

        query = ExtractionQuery(
            data_type=data_type,
            filters={},
            pagination=PaginationConfig(max_pages=1, auto_paginate=False),
            metadata={'test': 'individual'}
        )

        start_time = time.time()
        result = await service.perform_extraction(query)
        extraction_time = time.time() - start_time

        results.append(result)
        times.append(extraction_time)
        total_auth_calls += browser_session.auth_call_count

        print(f"     ⏱️  Time: {extraction_time:.3f}s, Auth calls: {browser_session.auth_call_count}")
        print(f"     ✅ Success: {result.success}, Records: {len(result.data) if result.data else 0}")

    total_time = sum(times)
    print(f"  ⏱️  Total individual extractions: {total_time:.3f}s")
    print(f"  🔐 Total authentication calls: {total_auth_calls}")

    return {
        'total_time': total_time,
        'auth_calls': total_auth_calls,
        'success': all(r.success for r in results),
        'individual_times': times
    }


@pytest.mark.asyncio
async def test_batch_extraction():
    """Test batch extraction with automatic session reuse"""
    print("🧪 Testing batch extraction with session reuse...")

    # Create shared browser session to track calls
    shared_browser_session = MockBrowserSession()

    # Create batch service (session reuse enabled by default)
    service = BatchExtractionService(
        extractor=MockNativeSDWISExtractorAdapter(),
        browser_session_factory=lambda: shared_browser_session,
        progress=SilentProgressAdapter(),
        output=JSONOutputAdapter(),
        config=MockConfigAdapter(),
        http_validator=None
    )

    # Create test queries using supported data types
    mock_extractor = MockNativeSDWISExtractorAdapter()
    supported_types = mock_extractor.get_supported_data_types()

    queries = []
    for data_type in supported_types:
        queries.append(ExtractionQuery(
            data_type=data_type,
            filters={},
            pagination=PaginationConfig(max_pages=1, auto_paginate=False),
            metadata={'test': 'batch'}
        ))

    start_time = time.time()
    results = await service.perform_batch_extraction(queries)
    total_time = time.time() - start_time

    auth_calls = shared_browser_session.auth_call_count
    success = all(r.success for r in results)

    print(f"  ⏱️  Total batch extraction: {total_time:.3f}s")
    print(f"  🔐 Total authentication calls: {auth_calls}")
    print(f"  📊 Extracted records: {sum(r.metadata.extracted_count for r in results)}")

    return {
        'total_time': total_time,
        'auth_calls': auth_calls,
        'success': success,
        'results': results
    }


@pytest.mark.asyncio
async def test_session_reuse_verification():
    """Test that session reuse actually works by monitoring authentication calls"""
    print("🧪 Verifying session reuse behavior...")

    # Create custom browser session factory that tracks instances
    session_instances = []

    def tracked_session_factory():
        session = MockBrowserSession()
        session_instances.append(session)
        return session

    # Test without session reuse
    print("  📊 Testing WITHOUT session reuse...")
    service_no_reuse = ExtractionService(
        extractor=MockNativeSDWISExtractorAdapter(),
        browser_session_factory=tracked_session_factory,
        progress=SilentProgressAdapter(),
        output=JSONOutputAdapter(),
        config=MockConfigAdapter(),
        http_validator=None,
        reuse_session=False  # Explicitly disabled
    )

    queries = [
        ExtractionQuery("water_systems", {}, PaginationConfig(max_pages=1, auto_paginate=False)),
        ExtractionQuery("legal_entities", {}, PaginationConfig(max_pages=1, auto_paginate=False))
    ]

    # Execute without reuse
    session_instances.clear()
    for query in queries:
        await service_no_reuse.perform_extraction(query)

    no_reuse_sessions = len(session_instances)
    no_reuse_auth_calls = sum(s.auth_call_count for s in session_instances)

    print(f"     Sessions created: {no_reuse_sessions}")
    print(f"     Authentication calls: {no_reuse_auth_calls}")

    # Test with session reuse
    print("  📊 Testing WITH session reuse...")
    service_with_reuse = ExtractionService(
        extractor=MockNativeSDWISExtractorAdapter(),
        browser_session_factory=tracked_session_factory,
        progress=SilentProgressAdapter(),
        output=JSONOutputAdapter(),
        config=MockConfigAdapter(),
        http_validator=None,
        reuse_session=True  # Explicitly enabled
    )

    # Execute with reuse
    session_instances.clear()
    for query in queries:
        await service_with_reuse.perform_extraction(query)

    # Clean up
    await service_with_reuse.cleanup_session()

    reuse_sessions = len(session_instances)
    reuse_auth_calls = sum(s.auth_call_count for s in session_instances)

    print(f"     Sessions created: {reuse_sessions}")
    print(f"     Authentication calls: {reuse_auth_calls}")

    # Verify expectations
    expected_improvement = no_reuse_sessions > reuse_sessions or no_reuse_auth_calls > reuse_auth_calls

    return {
        'no_reuse_sessions': no_reuse_sessions,
        'no_reuse_auth_calls': no_reuse_auth_calls,
        'reuse_sessions': reuse_sessions,
        'reuse_auth_calls': reuse_auth_calls,
        'improvement_detected': expected_improvement
    }


# Convert standalone functions to pytest test methods
@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_individual_vs_batch_extraction_comparison():
    """Compare individual extractions vs batch extraction performance."""
    # Test individual extractions (baseline)
    individual_results = await test_individual_extractions()

    # Test batch extraction
    batch_results = await test_batch_extraction()

    # Verify both succeeded
    assert individual_results['success'], "Individual extractions should succeed"
    assert batch_results['success'], "Batch extraction should succeed"

    # Verify authentication call savings
    auth_savings = individual_results['auth_calls'] - batch_results['auth_calls']
    assert auth_savings > 0, f"Expected authentication savings, got {auth_savings}"


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_session_reuse_behavior_verification():
    """Verify that session reuse actually reduces authentication calls."""
    verification_results = await test_session_reuse_verification()

    assert verification_results['improvement_detected'], \
        "Session reuse should demonstrate measurable improvements"

    assert verification_results['no_reuse_auth_calls'] > verification_results['reuse_auth_calls'], \
        "Session reuse should reduce authentication calls"


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_batch_service_enables_session_reuse_by_default():
    """Verify BatchExtractionService automatically enables session reuse."""
    batch_service = BatchExtractionService(
        extractor=MockNativeSDWISExtractorAdapter(),
        browser_session_factory=MockBrowserSession,
        progress=SilentProgressAdapter(),
        output=JSONOutputAdapter(),
        config=MockConfigAdapter()
    )

    # Should have session reuse enabled by default
    assert batch_service.reuse_session is True, \
        "BatchExtractionService should enable session reuse by default"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
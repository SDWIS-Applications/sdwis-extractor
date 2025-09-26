#!/usr/bin/env python3
"""
Integration test for Streamlit UI extraction flow.

This test simulates the exact flow that happens in the Streamlit UI
to debug why water systems extraction is failing.
"""

import asyncio
import os
import sys
from pathlib import Path
from queue import Queue
import threading
import time
from typing import Dict, Any

# Add modules to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Mock Streamlit before importing
from unittest.mock import MagicMock

class MockSessionState:
    """Mock Streamlit session state for testing"""
    def __init__(self):
        self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def __contains__(self, key):
        return key in self.data

    def __setitem__(self, key, value):
        self.data[key] = value

    def __getitem__(self, key):
        return self.data[key]


# Mock streamlit module
mock_st = MagicMock()
mock_st.session_state = MockSessionState()
sys.modules['streamlit'] = mock_st

# Now we can import the Streamlit components
from modules.adapters.ui.streamlit_app import (
    StreamlitConfigAdapter,
    StreamlitExtractionOrchestrator,
    run_extraction_in_thread
)
from modules.core.export_configuration import ExportConfiguration, FileNamingPolicy, ExportMode


def test_streamlit_extraction_flow():
    """Test the complete Streamlit extraction flow"""
    print("=" * 80)
    print("STREAMLIT UI EXTRACTION TEST")
    print("=" * 80)

    # Step 1: Set up mock session state with credentials
    print("\n1. Setting up session state...")
    mock_st.session_state['username'] = os.getenv('SDWIS_USERNAME', 'testuser')
    mock_st.session_state['password'] = os.getenv('SDWIS_PASSWORD', 'testpass')
    mock_st.session_state['server_url'] = os.getenv('SDWIS_URL', 'http://sdwis:8080/SDWIS/')

    print(f"   Username: {mock_st.session_state['username']}")
    print(f"   Password: {'*' * len(mock_st.session_state['password'])}")
    print(f"   Server: {mock_st.session_state['server_url']}")

    # Step 2: Create config adapter and verify it works
    print("\n2. Testing StreamlitConfigAdapter...")
    config_adapter = StreamlitConfigAdapter()

    try:
        creds = config_adapter.get_credentials()
        print(f"   ✓ Credentials retrieved: {creds['username']}")
    except Exception as e:
        print(f"   ✗ Failed to get credentials: {e}")
        return False

    server_config = config_adapter.get_server_config()
    print(f"   ✓ Server config: {server_config['base_url']}")

    browser_config = config_adapter.get_browser_config()
    print(f"   ✓ Browser config: headless={browser_config['headless']}")

    validation_result = config_adapter.validate_config()
    print(f"   ✓ Config validation: {validation_result}")

    # Step 3: Create orchestrator
    print("\n3. Creating StreamlitExtractionOrchestrator...")
    orchestrator = StreamlitExtractionOrchestrator()

    if not orchestrator.initialize_services():
        print("   ✗ Failed to initialize services")
        return False
    print("   ✓ Services initialized")

    # Step 4: Test connection (optional)
    print("\n4. Testing connection...")
    try:
        loop = asyncio.new_event_loop()
        connection_result = loop.run_until_complete(orchestrator.test_connection())
        if connection_result:
            print("   ✓ Connection test passed")
        else:
            print("   ⚠️  Connection test failed (may be using mock credentials)")
    except Exception as e:
        print(f"   ⚠️  Connection test error: {e}")
    finally:
        loop.close()

    # Step 5: Create export configuration
    print("\n5. Creating export configuration...")
    export_config = orchestrator.create_export_configuration(
        selected_data_types=['water_systems'],
        export_mode='general'
    )
    print(f"   ✓ Export config created:")
    print(f"     - Data types: {export_config.data_types}")
    print(f"     - Export mode: {export_config.export_mode}")
    print(f"     - Output format: {export_config.output_format}")

    # Step 6: Test the threading mechanism
    print("\n6. Testing extraction in thread (simulating Streamlit)...")
    results_queue = Queue()

    # Run extraction in thread just like Streamlit does
    extraction_thread = threading.Thread(
        target=run_extraction_in_thread,
        args=(orchestrator, export_config, results_queue),
        daemon=True
    )
    extraction_thread.start()

    # Wait for results (with timeout)
    print("   Waiting for extraction to complete...")
    timeout = 30  # 30 seconds timeout
    start_time = time.time()

    while extraction_thread.is_alive() and (time.time() - start_time) < timeout:
        time.sleep(0.5)
        print(".", end="", flush=True)

    print()  # New line after dots

    if extraction_thread.is_alive():
        print("   ✗ Extraction timed out")
        return False

    # Check results
    if results_queue.empty():
        print("   ✗ No results received")
        return False

    message_type, data = results_queue.get()

    if message_type == 'error':
        print(f"\n   ✗ Extraction failed with error:")
        if isinstance(data, dict):
            print(f"     Error: {data.get('error', 'Unknown')}")
            print(f"     Type: {data.get('type', 'Unknown')}")
            print("\n     Traceback:")
            print("     " + "\n     ".join(data.get('traceback', 'No traceback').split('\n')))
        else:
            print(f"     {data}")
        return False

    elif message_type == 'success':
        print(f"\n   ✓ Extraction completed")
        print(f"\n7. Analyzing results...")

        success = data.get('success', False)
        print(f"   Overall success: {success}")

        if 'results' in data:
            results = data['results']
            print(f"   Number of results: {len(results)}")

            for i, result in enumerate(results):
                print(f"\n   Result {i+1} ({result.get('data_type', 'unknown')}):")
                print(f"     - Success: {result.get('success', False)}")
                print(f"     - Count: {result.get('count', 0)}")
                print(f"     - Output: {result.get('output_path', 'N/A')}")

                if result.get('errors'):
                    print(f"     - Errors: {result['errors']}")
                if result.get('warnings'):
                    print(f"     - Warnings: {result['warnings']}")

        if 'error' in data:
            print(f"\n   Error message: {data['error']}")

        if 'errors' in data:
            print(f"   Errors list: {data['errors']}")

        assert success, "Extraction should have succeeded"
        return  # Success case - test passed

    assert False, "Should have received results"


def test_direct_orchestration():
    """Test orchestration service directly without threading"""
    print("\n" + "=" * 80)
    print("DIRECT ORCHESTRATION TEST (no threading)")
    print("=" * 80)

    # Set up session state
    mock_st.session_state['username'] = os.getenv('SDWIS_USERNAME', 'testuser')
    mock_st.session_state['password'] = os.getenv('SDWIS_PASSWORD', 'testpass')
    mock_st.session_state['server_url'] = os.getenv('SDWIS_URL', 'http://sdwis:8080/SDWIS/')

    orchestrator = StreamlitExtractionOrchestrator()
    orchestrator.initialize_services()

    export_config = orchestrator.create_export_configuration(
        selected_data_types=['water_systems'],
        export_mode='general'
    )

    print("\nRunning extraction directly...")
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(orchestrator.perform_extraction(export_config))
        print(f"Result: {result}")
        success = result.get('success', False)
        assert success, f"Direct orchestration should succeed, got: {result}"
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        assert False, f"Direct orchestration failed with exception: {e}"
    finally:
        loop.close()


if __name__ == "__main__":
    print("Starting Streamlit UI integration tests...\n")

    # Test 1: Full flow with threading
    test1_result = test_streamlit_extraction_flow()

    # Test 2: Direct orchestration
    test2_result = test_direct_orchestration()

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Test 1 (Threading flow): {'✓ PASSED' if test1_result else '✗ FAILED'}")
    print(f"Test 2 (Direct flow): {'✓ PASSED' if test2_result else '✗ FAILED'}")

    sys.exit(0 if (test1_result or test2_result) else 1)
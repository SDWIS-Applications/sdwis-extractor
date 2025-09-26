#!/usr/bin/env python3
"""
SDWIS Streamlit UI Adapter

This module provides a Streamlit web interface for the SDWIS data extraction system.
It integrates with the hexagonal architecture, using domain services through the
ports and adapters pattern.

This is a pure UI adapter - all business logic is handled by domain services.
"""

import streamlit as st
import asyncio
import json
import time
import io
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import threading
from queue import Queue
import sys
import os
from concurrent.futures import ThreadPoolExecutor

# Import the hexagonal architecture components
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from modules.core.domain import ExtractionQuery, PaginationConfig, ExtractionResult
from modules.core.services import BatchExtractionService
from modules.core.registry import get_default_registry, register_default_adapters
from modules.core.export_service import ExportService
from modules.core.export_configuration import ExportConfiguration, FileNamingPolicy
from modules.core.export_orchestration import ExportOrchestrationService
from modules.adapters.auth.http_validator import SDWISHttpAuthValidator
from modules.adapters.auth.browser_session import SDWISAuthenticatedBrowserSession
from modules.adapters.factories import OutputAdapterFactory
from modules.adapters.progress.streamlit import StreamlitProgressAdapter, StreamlitMultiProgressAdapter


class StreamlitConfigAdapter:
    """Configuration adapter that gets settings from Streamlit session state"""

    def __init__(self, cached_values: Dict[str, Any] = None):
        """
        Initialize config adapter.

        Args:
            cached_values: Optional pre-captured values for thread safety
        """
        self.cached_values = cached_values
        if not cached_values:
            self.validate_session_state()

    def validate_session_state(self):
        """Ensure required session state exists"""
        required_keys = ['server_url', 'username', 'password']
        for key in required_keys:
            if key not in st.session_state:
                st.session_state[key] = ''

    def get_credentials(self) -> Dict[str, str]:
        # Use cached values if available (for thread safety)
        if self.cached_values:
            return {
                'username': self.cached_values.get('username', ''),
                'password': self.cached_values.get('password', '')
            }

        credentials = {
            'username': st.session_state.get('username', ''),
            'password': st.session_state.get('password', '')
        }

        # Validate credentials are not empty
        if not credentials['username'] or not credentials['password']:
            raise ValueError(
                "SDWIS credentials not configured. "
                "Please enter username and password in the sidebar."
            )

        return credentials

    def get_server_config(self) -> Dict[str, str]:
        # Use cached values if available
        if self.cached_values:
            base_url = self.cached_values.get('server_url', 'http://sdwis:8080/SDWIS/')
        else:
            base_url = st.session_state.get('server_url', '')
            if not base_url:
                base_url = 'http://sdwis:8080/SDWIS/'

        return {
            'base_url': base_url
        }

    def get_extraction_config(self) -> Dict[str, Any]:
        return {
            'batch_size': '1000',
            'timeout': 60000
        }

    def get_browser_config(self) -> Dict[str, Any]:
        return {
            'headless': True,  # Always headless for Streamlit
            'timeout': 60000,
            'args': ['--no-sandbox', '--disable-dev-shm-usage']
        }

    def validate_config(self) -> bool:
        """Validate that configuration is complete"""
        try:
            creds = self.get_credentials()
            server = self.get_server_config()

            return (
                bool(creds['username']) and
                bool(creds['password']) and
                bool(server['base_url'])
            )
        except ValueError:
            # Credentials not configured yet
            return False


class StreamlitExtractionOrchestrator:
    """
    Orchestrates SDWIS data extraction through Streamlit interface.

    This is a pure adapter - all business logic is handled by domain services.
    It coordinates the UI, progress reporting, and file downloads.
    """

    def __init__(self):
        self.registry = None
        self.orchestration_service = None
        self.progress_adapter = None

    def initialize_services(self) -> bool:
        """Initialize the hexagonal architecture services"""
        try:
            # Initialize registry and register adapters
            self.registry = get_default_registry()
            register_default_adapters()

            return True
        except Exception as e:
            st.error(f"Failed to initialize services: {e}")
            return False

    def create_orchestration_service(self, config_adapter=None, progress_adapter=None) -> ExportOrchestrationService:
        """Create the orchestration service with all dependencies"""
        # Use provided config adapter or create new one
        if config_adapter is None:
            config_adapter = StreamlitConfigAdapter()

        # Create export service
        export_service = ExportService()

        # Use provided progress adapter or create fallback
        if progress_adapter is None:
            from modules.adapters.progress.cli import CLIProgressAdapter
            progress_adapter = CLIProgressAdapter(use_rich=False)  # Fallback for batch service

        # Create authentication components with proper configuration
        server_config = config_adapter.get_server_config()
        http_validator = SDWISHttpAuthValidator(base_url=server_config['base_url'])
        browser_session_factory = lambda: SDWISAuthenticatedBrowserSession(base_url=server_config['base_url'])

        # Get primary extractor (batch service handles multiple types)
        try:
            extractor_adapter = self.registry.get_extractor("water_systems")
        except:
            from modules.adapters.extractors.native_sdwis import NativeSDWISExtractorAdapter
            extractor_adapter = NativeSDWISExtractorAdapter()

        # Create dummy output adapter (orchestration handles real output)
        from modules.adapters.output.json import JSONOutputAdapter
        dummy_output_adapter = JSONOutputAdapter()

        # Create batch extraction service
        batch_service = BatchExtractionService(
            extractor=extractor_adapter,
            browser_session_factory=browser_session_factory,
            progress=progress_adapter,
            output=dummy_output_adapter,
            config=config_adapter,
            http_validator=http_validator
        )

        # Create output adapter factory
        output_adapter_factory = OutputAdapterFactory(export_service)

        return ExportOrchestrationService(batch_service, export_service, output_adapter_factory)

    async def test_connection(self) -> bool:
        """Test connection to SDWIS server"""
        try:
            config_adapter = StreamlitConfigAdapter()

            if not config_adapter.validate_config():
                return False

            # Test HTTP connectivity with configured server
            server_config = config_adapter.get_server_config()
            http_validator = SDWISHttpAuthValidator(base_url=server_config['base_url'])

            # Check connectivity
            connectivity = await http_validator.check_connectivity()
            if not connectivity:
                return False

            # Validate credentials
            credentials = config_adapter.get_credentials()
            return await http_validator.validate_credentials(credentials)

        except Exception as e:
            st.error(f"Connection test failed: {e}")
            return False

    def create_export_configuration(self, selected_data_types: List[str], export_mode: str) -> ExportConfiguration:
        """Create export configuration from UI selections"""
        from modules.core.export_service import ExportMode

        mode = ExportMode.INSPECTION if export_mode == 'inspection' else ExportMode.GENERAL

        # Inspection mode requires JSON format
        output_format = 'json' if export_mode == 'inspection' else 'csv'

        return ExportConfiguration(
            data_types=selected_data_types,
            export_mode=mode,
            output_format=output_format,
            output_path=None,  # Will generate dynamic names
            file_naming_policy=FileNamingPolicy()
        )

    async def perform_extraction(self, export_config: ExportConfiguration) -> Dict[str, Any]:
        """Perform the extraction using orchestration service"""
        if not self.orchestration_service:
            self.orchestration_service = self.create_orchestration_service()

        return await self.orchestration_service.perform_configured_export(export_config)


def create_progress_display(data_types: List[str]) -> StreamlitMultiProgressAdapter:
    """Create progress bars for each selected data type"""
    multi_progress = StreamlitMultiProgressAdapter()

    # Create progress section
    st.subheader("🚀 Extraction Progress")

    for data_type in data_types:
        st.write(f"**{data_type.replace('_', ' ').title()}**")
        progress_bar = st.progress(0.0)
        status_text = st.empty()

        adapter = StreamlitProgressAdapter(progress_bar, status_text)
        multi_progress.add_progress_bar(data_type, adapter, status_text)

    return multi_progress


def handle_extraction_results(results: Dict[str, Any], selected_data_types: List[str]):
    """Handle and display extraction results with download buttons"""
    if not results.get('success', False):
        st.error("❌ Extraction failed")

        # Check for specific error patterns
        error_msg = results.get('error', '')
        if 'Could not find results frame' in error_msg:
            st.error("Unable to access SDWIS data. This usually means:")
            st.error("• The credentials are incorrect")
            st.error("• The SDWIS server is not responding as expected")
            st.error("• You don't have permissions to access this data")
            st.info("💡 Try testing your connection with the 'Test Connection' button first")

        if 'errors' in results:
            for error in results['errors']:
                st.error(f"• {error}")
        return

    # Check if we have partial success
    extraction_results = results.get('results', [])
    output_paths = results.get('output_paths', [])

    # Count successes and failures
    successful_extractions = [r for r in extraction_results if r.get('success', False)]
    failed_extractions = [r for r in extraction_results if not r.get('success', False)]

    if successful_extractions:
        st.success(f"✅ {len(successful_extractions)} extraction(s) completed successfully!")
    if failed_extractions:
        st.warning(f"⚠️ {len(failed_extractions)} extraction(s) failed")

    # Display results and create download buttons

    cols = st.columns(len(selected_data_types))

    for i, (data_type, result) in enumerate(zip(selected_data_types, extraction_results)):
        with cols[i % len(cols)]:
            st.subheader(f"{data_type.replace('_', ' ').title()}")

            if result.get('success'):
                count = result.get('count', 0)
                extraction_time = result.get('extraction_time', 0)

                st.metric("Records Extracted", count)
                st.metric("Extraction Time", f"{extraction_time:.2f}s")

                # Create download button
                if i < len(output_paths) and output_paths[i]:
                    file_path = Path(output_paths[i])
                    if file_path.exists():
                        with open(file_path, 'rb') as f:
                            file_data = f.read()

                        file_extension = file_path.suffix.lower()
                        mime_type = 'text/csv' if file_extension == '.csv' else 'application/json'

                        st.download_button(
                            label=f"📥 Download {data_type.replace('_', ' ').title()}",
                            data=file_data,
                            file_name=file_path.name,
                            mime=mime_type,
                            key=f"download_{data_type}_{int(time.time())}"
                        )

                # Display warnings and errors
                warnings = result.get('warnings', [])
                errors = result.get('errors', [])

                if warnings:
                    with st.expander(f"⚠️ {len(warnings)} warnings"):
                        for warning in warnings:
                            st.warning(warning)

                if errors:
                    with st.expander(f"❌ {len(errors)} errors"):
                        for error in errors:
                            st.error(error)
            else:
                st.error(f"❌ {data_type} extraction failed")
                errors = result.get('errors', [])

                # Check for specific error patterns and provide helpful guidance
                has_frame_error = any('Could not find results frame' in str(e) for e in errors)
                if has_frame_error:
                    st.info(f"💡 The {data_type} extraction couldn't access SDWIS data. This usually means:")
                    st.info("   • Invalid credentials or insufficient permissions")
                    st.info("   • SDWIS server is not responding correctly")
                    st.info("   • Network connectivity issues")
                    st.info("   Use 'Test Connection' in the sidebar to verify your setup")

                # Show the actual errors
                for error in errors:
                    st.error(f"• {error}")


def run_extraction_in_thread(orchestrator: StreamlitExtractionOrchestrator,
                             export_config: ExportConfiguration,
                             results_queue: Queue,
                             cached_config: Dict[str, Any] = None):
    """Run extraction in a separate thread to avoid blocking Streamlit"""
    try:
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # If cached config provided, recreate orchestration service with it
        # Note: Progress will not be shown since we can't access Streamlit from background thread
        if cached_config:
            config_adapter = StreamlitConfigAdapter(cached_values=cached_config)
            # Use CLI progress adapter for background thread since Streamlit progress doesn't work in threads
            from modules.adapters.progress.cli import CLIProgressAdapter
            progress_adapter = CLIProgressAdapter(use_rich=False)
            orchestrator.orchestration_service = orchestrator.create_orchestration_service(config_adapter, progress_adapter)

        # Run the extraction
        result = loop.run_until_complete(
            orchestrator.perform_extraction(export_config)
        )

        results_queue.put(('success', result))

    except Exception as e:
        import traceback
        error_details = {
            'error': str(e),
            'type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        results_queue.put(('error', error_details))
    finally:
        loop.close()


def main():
    """Main Streamlit application"""
    st.set_page_config(
        page_title="SDWIS Data Extractor",
        page_icon="🌊",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("🌊 SDWIS Data Extractor")
    st.markdown("""
    **Data Extraction Tool**

    Extract water systems, legal entities, and inspection data from SDWIS with full automation.
    """)

    # Initialize session state
    if 'extraction_running' not in st.session_state:
        st.session_state.extraction_running = False
    if 'results_queue' not in st.session_state:
        st.session_state.results_queue = Queue()
    if 'extraction_results' not in st.session_state:
        st.session_state.extraction_results = None
    if 'selected_data_types' not in st.session_state:
        st.session_state.selected_data_types = []

    # Initialize orchestrator
    orchestrator = StreamlitExtractionOrchestrator()
    if not orchestrator.initialize_services():
        st.stop()

    # Sidebar configuration
    with st.sidebar:
        st.header("🔧 Configuration")

        # Server configuration
        st.subheader("Server Settings")
        st.session_state.server_url = st.text_input(
            "SDWIS Server URL",
            value=st.session_state.get('server_url', 'http://sdwis:8080/SDWIS/'),
            help="Full URL to your SDWIS server"
        )

        st.session_state.username = st.text_input(
            "Username",
            value=st.session_state.get('username', ''),
            help="SDWIS login username"
        )

        st.session_state.password = st.text_input(
            "Password",
            type="password",
            help="SDWIS login password"
        )

        # Test connection
        if st.button("🔍 Test Connection"):
            with st.spinner("Testing connection..."):
                connection_result = asyncio.run(orchestrator.test_connection())
                if connection_result:
                    st.success("✅ Connection successful!")
                else:
                    st.error("❌ Connection failed! Check settings.")

        st.divider()

        # Export mode selection (needs to be first to control data type selection)
        st.subheader("Export Configuration")
        export_mode = st.radio(
            "Export Mode",
            options=["general", "inspection"],
            format_func=lambda x: "General Export" if x == "general" else "Inspection Export (JSON)",
            help="General: All fields in CSV. Inspection: Selected fields in hierarchical JSON for inspection app."
        )

        st.divider()

        # Data type selection
        st.subheader("Data Types to Extract")

        # Load inspection schema data types if in inspection mode
        inspection_data_types = []
        if export_mode == "inspection":
            try:
                from modules.adapters.export_schema.schema_loader import SchemaLoader
                loader = SchemaLoader()
                schema = loader.load_schema("inspection_report")
                inspection_data_types = [dt.value if hasattr(dt, 'value') else str(dt) for dt in schema.data_types.keys()]
                st.info(f"💡 Inspection mode: Default data types from schema auto-selected. You can deselect if needed.")
            except Exception as e:
                st.warning(f"Could not load inspection schema: {e}")
                inspection_data_types = ["water_systems", "legal_entities"]  # fallback

        else:
            st.markdown("*Select multiple types for batch extraction*")

        available_types = [
            ("water_systems", "🏭 Water Systems", "Extract water system records with pagination"),
            ("legal_entities", "👥 Legal Entities", "Extract individual legal entity records"),
            ("deficiency_types", "⚠️ Deficiency Types", "Extract deficiency type records (future implementation)"),
            # Note: Sample schedules available but not shown as it needs additional UI for search params
        ]

        selected_types = []
        for data_type, label, help_text in available_types:
            # For inspection mode, auto-select types from schema but allow deselection
            if export_mode == "inspection":
                default_value = data_type in inspection_data_types
                help_suffix = " (From inspection schema)" if default_value else ""
                # Use a unique key for inspection mode to avoid conflicts
                checkbox_key = f"inspect_{data_type}"
                if st.checkbox(label, value=default_value, help=f"{help_text}{help_suffix}", key=checkbox_key):
                    selected_types.append(data_type)
            else:
                # Use general mode key
                checkbox_key = f"general_{data_type}"
                if st.checkbox(label, help=help_text, key=checkbox_key):
                    selected_types.append(data_type)

        st.session_state.selected_data_types = selected_types

    # Main content area
    if not selected_types:
        st.info("👈 Please select data types to extract from the sidebar")
        st.stop()

    # Display selected configuration
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📋 Extraction Configuration")
        st.write(f"**Data Types:** {', '.join(t.replace('_', ' ').title() for t in selected_types)}")
        st.write(f"**Export Mode:** {export_mode.title()}")
        st.write(f"**Output Format:** {'JSON (Hierarchical)' if export_mode == 'inspection' else 'CSV (Separate files)'}")

    with col2:
        st.subheader("🎯 Expected Results")
        if "water_systems" in selected_types:
            st.write("🏭 Water Systems: 1,000-5,000 records")
        if "legal_entities" in selected_types:
            st.write("👥 Legal Entities: 5,000-15,000 records")

    # Extraction controls
    if not st.session_state.extraction_running:
        if st.button(
            "🚀 Start Extraction",
            type="primary",
            disabled=not selected_types,
            help="Begin extracting selected data types"
        ):
            if not StreamlitConfigAdapter().validate_config():
                st.error("❌ Please complete server configuration in sidebar")
                st.stop()

            # Start extraction
            st.session_state.extraction_running = True
            st.session_state.extraction_results = None
            st.session_state.extraction_start_time = time.time()  # Reset timer

            # Create export configuration
            export_config = orchestrator.create_export_configuration(selected_types, export_mode)

            # Capture current config values for thread safety
            cached_config = {
                'username': st.session_state.get('username', ''),
                'password': st.session_state.get('password', ''),
                'server_url': st.session_state.get('server_url', '')
            }

            # Start extraction in background thread
            extraction_thread = threading.Thread(
                target=run_extraction_in_thread,
                args=(orchestrator, export_config, st.session_state.results_queue, cached_config),
                daemon=True
            )
            extraction_thread.start()

            # Force rerun to show progress
            st.rerun()
    else:
        if st.button("⏹️ Stop Extraction", type="secondary"):
            st.session_state.extraction_running = False
            st.rerun()

    # Progress tracking and results
    if st.session_state.extraction_running:
        # Check for results
        if not st.session_state.results_queue.empty():
            try:
                message_type, data = st.session_state.results_queue.get_nowait()

                if message_type == 'success':
                    st.session_state.extraction_running = False
                    st.session_state.extraction_results = data
                elif message_type == 'error':
                    st.session_state.extraction_running = False
                    if isinstance(data, dict):
                        st.error(f"❌ Extraction failed: {data.get('error', 'Unknown error')}")
                        st.error(f"Error type: {data.get('type', 'Unknown')}")
                        with st.expander("Full error details"):
                            st.code(data.get('traceback', 'No traceback available'))
                    else:
                        st.error(f"❌ Extraction failed: {data}")

                st.rerun()

            except:
                pass  # Queue empty, continue

        # Show progress display
        st.subheader("🚀 Extraction Progress")

        # Progress bar (indeterminate)
        progress_bar = st.progress(0)

        # Simulate progress steps
        steps = [
            "🔐 Validating credentials...",
            "🌐 Connecting to SDWIS server...",
            "🔍 Searching for data...",
            "📊 Extracting records...",
            "📝 Processing results...",
            "✅ Finalizing extraction..."
        ]

        # Calculate elapsed time since extraction started
        if 'extraction_start_time' not in st.session_state:
            st.session_state.extraction_start_time = time.time()

        elapsed = time.time() - st.session_state.extraction_start_time

        # Show different steps based on elapsed time
        step_duration = 5  # seconds per step
        current_step = min(int(elapsed / step_duration), len(steps) - 1)

        status_text = st.empty()
        status_text.text(steps[current_step])

        # Update progress bar
        progress = min((elapsed / (len(steps) * step_duration)), 0.95)  # Max 95% until completion
        progress_bar.progress(progress)

        st.info(f"🕒 Elapsed time: {elapsed:.0f} seconds")
        st.info("💡 Large datasets may take 3-5 minutes to extract completely")

        time.sleep(1)  # Update every second
        st.rerun()

    # Display results
    if st.session_state.extraction_results:
        st.divider()
        handle_extraction_results(
            st.session_state.extraction_results,
            st.session_state.selected_data_types
        )

    # Instructions and help
    with st.expander("📖 Instructions & Help"):
        st.markdown("""
        ### How to use this tool:

        1. **Configure Connection** (Sidebar)
           - Enter your SDWIS server URL
           - Provide your username and password
           - Test connection to verify settings

        2. **Select Data Types** (Sidebar)
           - Choose one or more data types to extract
           - Each type will create a separate download file

        3. **Choose Export Mode** (Sidebar)
           - **General**: All fields exported as CSV files
           - **Inspection**: Selected fields in JSON format for inspection application

        4. **Start Extraction**
           - Click "Start Extraction" to begin
           - Monitor progress in real-time
           - Downloads will be available when complete

        ### Troubleshooting:

        - **Connection Failed**: Check server URL and credentials
        - **Slow Performance**: Large datasets may take 5-10 minutes
        - **Download Issues**: Files are generated in memory, try smaller data sets for very large results
        """)


if __name__ == "__main__":
    main()
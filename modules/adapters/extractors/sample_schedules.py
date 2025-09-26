"""
Native Sample Schedules Extractor

Built specifically for the modular architecture with support for parameterized
searches and form field handling.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from playwright.async_api import async_playwright, Page, Frame

from ...core.domain import ExtractionQuery, ExtractionResult, ExtractionMetadata
from ...core.ports import ExtractionPort, ExtractionError, ProgressReportingPort, AuthenticatedBrowserSessionPort


class SampleSchedulesExtractor:
    """Native sample schedules extractor for modular architecture"""

    def __init__(
        self,
        base_url: str = "http://sdwis:8080/SDWIS/",
        browser_headless: bool = True,
        timeout_ms: int = 30000,
        progress_reporter: Optional[ProgressReportingPort] = None
    ):
        self.base_url = base_url.rstrip('/') + '/'
        self.login_url = f"{self.base_url}jsp/secure/"
        self.search_url = f"{self.base_url}mbsmain_tc.jsp?clearScreenInputs=NTCRSCH"

        self.browser_headless = browser_headless
        self.timeout_ms = timeout_ms
        self.progress = progress_reporter

        # Internal state
        self._browser = None
        self._page = None
        self._authenticated = False

        # Search field mappings based on your existing research
        self.field_mappings = {
            'pws_id': 'Field2',
            'facility_id': 'TEXT_42',
            'schedule_type': 'TYPE_CODE1',  # Radio button: OT/TC/NT
            'active_only': 'FLAG1',  # Checkbox
            'sample_count_unit': 'SAMPLE_COUNT_UNIT_CODE1',  # Select dropdown
        }

    def get_supported_data_types(self) -> List[str]:
        """Get supported data types"""
        return ["sample_schedules"]

    async def validate_query(self, query: ExtractionQuery) -> bool:
        """Validate extraction query"""
        return query.data_type == "sample_schedules"

    async def extract_data(self, query: ExtractionQuery, browser_session: AuthenticatedBrowserSessionPort) -> ExtractionResult:
        """Extract sample schedules with parameterized search"""
        if not await self.validate_query(query):
            return ExtractionResult(
                success=False,
                data=[],
                metadata=ExtractionMetadata(
                    extracted_count=0,
                    extraction_time=0.0,
                    data_type=query.data_type
                ),
                errors=["Invalid query for sample schedules extractor"]
            )

        start_time = time.time()

        try:
            # Get search parameters from query
            search_params = query.filters.get('search_params', {})

            if self.progress:
                self.progress.set_total_steps(6)  # auth, navigate, form_fill, search, extract, finalize

            # Step 1: Use provided authenticated browser session
            if self.progress:
                self.progress.increment_step("Using authenticated browser session")

            # Use the provided browser session instead of creating our own
            if not browser_session.is_authenticated():
                raise ExtractionError("Browser session is not authenticated")

            self._page = await browser_session.get_page()

            # Step 2: Navigate to sample schedules search
            if self.progress:
                self.progress.increment_step("Navigating to sample schedules search")

            await self._navigate_to_search()

            # Step 3: Fill search form
            if self.progress:
                self.progress.increment_step("Filling search parameters")

            search_frame = await self._find_search_frame()
            if not search_frame:
                raise ExtractionError("Could not find search frame")

            await self._fill_search_form(search_frame, search_params)

            # Step 4: Execute search
            if self.progress:
                self.progress.increment_step("Executing search")

            await self._execute_search(search_frame)

            # Step 5: Extract results
            if self.progress:
                self.progress.increment_step("Extracting sample schedules data")

            results_frame = await self._find_results_frame()
            if not results_frame:
                raise ExtractionError("Could not find results frame")

            schedules_data = await self._extract_schedules_data(results_frame)

            # Step 6: Finalize
            if self.progress:
                self.progress.increment_step("Finalizing extraction")

            extraction_time = time.time() - start_time

            if self.progress:
                self.progress.update_progress(
                    100,
                    f"Extraction complete - {len(schedules_data)} schedules found"
                )

            return ExtractionResult(
                success=True,
                data=schedules_data,
                metadata=ExtractionMetadata(
                    extracted_count=len(schedules_data),
                    extraction_time=extraction_time,
                    data_type="sample_schedules",
                    source_info={
                        "extractor": "SampleSchedulesExtractor",
                        "base_url": self.base_url,
                        "search_params": search_params,
                        "extraction_method": "form_based_search"
                    }
                )
            )

        except Exception as e:
            return ExtractionResult(
                success=False,
                data=[],
                metadata=ExtractionMetadata(
                    extracted_count=0,
                    extraction_time=time.time() - start_time,
                    data_type="sample_schedules"
                ),
                errors=[f"Sample schedules extraction failed: {str(e)}"]
            )
        finally:
            await self._cleanup()

    async def _initialize_browser(self):
        """Initialize Playwright browser"""
        if self._browser:
            return

        playwright = await async_playwright().start()
        self._browser = await playwright.chromium.launch(headless=self.browser_headless)
        self._page = await self._browser.new_page()

    async def _authenticate(self):
        """Authenticate with SDWIS"""
        if self._authenticated:
            return

        # Authentication handled by service layer
        self._authenticated = True

    async def _navigate_to_search(self):
        """Navigate to sample schedules search page"""
        await self._page.goto(self.search_url)
        await self._page.wait_for_load_state('networkidle')

        # Wait for frames to load
        await self._page.wait_for_function('() => window.frames && window.frames.length > 0')

    async def _find_search_frame(self) -> Optional[Frame]:
        """Find the search frame by looking for sample schedule specific fields"""
        for frame in self._page.frames:
            try:
                # Look for sample schedule specific fields
                pws_field = await frame.query_selector('input[name="Field2"]')
                type_radio = await frame.query_selector('input[name="TYPE_CODE1"]')

                if pws_field or type_radio:
                    return frame
            except:
                continue
        return None

    async def _fill_search_form(self, search_frame: Frame, search_params: Dict[str, Any]):
        """Fill the search form with provided parameters"""
        filled_fields = []

        for param_name, param_value in search_params.items():
            field_name = self.field_mappings.get(param_name, param_name)

            try:
                if param_name == 'schedule_type':
                    # Handle radio button
                    await self._set_radio_button(search_frame, field_name, param_value)
                    filled_fields.append(f"{param_name}={param_value}")

                elif param_name == 'active_only':
                    # Handle checkbox
                    await self._set_checkbox(search_frame, field_name, param_value)
                    filled_fields.append(f"{param_name}={param_value}")

                elif param_name == 'sample_count_unit':
                    # Handle select dropdown
                    await self._set_select_option(search_frame, field_name, param_value)
                    filled_fields.append(f"{param_name}={param_value}")

                else:
                    # Handle text input
                    input_field = await search_frame.query_selector(f'input[name="{field_name}"]')
                    if input_field:
                        await input_field.fill(str(param_value))
                        filled_fields.append(f"{param_name}={param_value}")

            except Exception as e:
                if self.progress:
                    self.progress.report_progress(
                        type('ProgressUpdate', (), {
                            'percent': 0,
                            'message': f"Warning: Could not set {param_name}={param_value}: {str(e)}",
                            'metadata': {'field_error': str(e)}
                        })()
                    )

        if self.progress and filled_fields:
            self.progress.report_progress(
                type('ProgressUpdate', (), {
                    'percent': 50,
                    'message': f"Filled search fields: {', '.join(filled_fields)}",
                    'metadata': {'filled_fields': filled_fields}
                })()
            )

    async def _set_radio_button(self, frame: Frame, field_name: str, value: str):
        """Set radio button value"""
        radio_button = await frame.query_selector(f'input[name="{field_name}"][value="{value}"]')
        if radio_button:
            await radio_button.click()
        else:
            # Try to find any radio with this name and click the first one
            radio_buttons = await frame.query_selector_all(f'input[name="{field_name}"]')
            if radio_buttons:
                await radio_buttons[0].click()

    async def _set_checkbox(self, frame: Frame, field_name: str, checked: bool):
        """Set checkbox state"""
        checkbox = await frame.query_selector(f'input[name="{field_name}"]')
        if checkbox:
            if checked:
                await checkbox.check()
            else:
                await checkbox.uncheck()

    async def _set_select_option(self, frame: Frame, field_name: str, value: str):
        """Set select dropdown option"""
        select = await frame.query_selector(f'select[name="{field_name}"]')
        if select:
            await select.select_option(value)

    async def _execute_search(self, search_frame: Frame):
        """Execute the search"""
        # Look for search button
        search_button = await search_frame.query_selector(
            'input[type="button"][value*="Search"], input[type="submit"][value*="Search"]'
        )
        if not search_button:
            search_button = await search_frame.query_selector('input[type="button"], input[type="submit"]')

        if search_button:
            await search_button.click()
            await asyncio.sleep(3)  # Wait for results to load

    async def _find_results_frame(self) -> Optional[Frame]:
        """Find the frame containing search results"""
        for frame in self._page.frames:
            try:
                # Look for results table
                table = await frame.query_selector('table.DFGUILBX')
                if table:
                    return frame
            except:
                continue
        return None

    async def _extract_schedules_data(self, results_frame: Frame) -> List[Dict[str, Any]]:
        """Extract sample schedules data from results frame"""
        try:
            # Try JavaScript extraction first
            schedules_data = await results_frame.evaluate('''
                () => {
                    if (typeof parent !== 'undefined' && parent.values && Array.isArray(parent.values)) {
                        return parent.values;
                    }
                    return null;
                }
            ''')

            if schedules_data:
                return self._convert_to_structured_schedules(schedules_data)

            # Fallback: try table extraction
            return await self._extract_from_table(results_frame)

        except Exception as e:
            if self.progress:
                self.progress.report_progress(
                    type('ProgressUpdate', (), {
                        'percent': 0,
                        'message': f"Error extracting schedules data: {str(e)}",
                        'metadata': {'error': str(e)}
                    })()
                )
            return []

    def _convert_to_structured_schedules(self, raw_data: List[Any]) -> List[Dict[str, Any]]:
        """Convert raw JavaScript data to structured schedule format"""
        structured_schedules = []

        # Define expected field names (adjust based on actual SDWIS output)
        field_names = [
            "Schedule ID", "PWS ID", "Facility ID", "Schedule Type",
            "Status", "Sample Count", "Frequency", "Analyte Group"
        ]

        for raw_schedule in raw_data:
            if isinstance(raw_schedule, list) and len(raw_schedule) >= 2:
                schedule_data = raw_schedule[1] if len(raw_schedule) > 1 else raw_schedule

                if isinstance(schedule_data, list):
                    schedule_dict = {}
                    for i, field_name in enumerate(field_names):
                        if i < len(schedule_data):
                            value = schedule_data[i]
                            # Clean up HTML entities and whitespace
                            if isinstance(value, str):
                                value = value.replace('&nbsp;', ' ').strip()
                            schedule_dict[field_name] = value

                    # Must have a schedule ID or PWS ID to be valid
                    if schedule_dict.get('Schedule ID') or schedule_dict.get('PWS ID'):
                        structured_schedules.append(schedule_dict)

        return structured_schedules

    async def _extract_from_table(self, results_frame: Frame) -> List[Dict[str, Any]]:
        """Fallback: extract data directly from HTML table"""
        try:
            # Find the data table
            table = await results_frame.query_selector('table.DFGUILBX')
            if not table:
                return []

            # Extract table headers
            header_row = await table.query_selector('tr')
            if not header_row:
                return []

            headers = []
            header_cells = await header_row.query_selector_all('th, td')
            for cell in header_cells:
                header_text = await cell.text_content()
                headers.append(header_text.strip() if header_text else "")

            # Extract data rows
            data_rows = await table.query_selector_all('tr')[1:]  # Skip header row
            schedules = []

            for row in data_rows:
                cells = await row.query_selector_all('td')
                if len(cells) >= len(headers):
                    schedule_dict = {}
                    for i, header in enumerate(headers):
                        if i < len(cells):
                            cell_text = await cells[i].text_content()
                            schedule_dict[header] = cell_text.strip() if cell_text else ""

                    schedules.append(schedule_dict)

            return schedules

        except Exception:
            return []

    async def _cleanup(self):
        """Clean up browser resources"""
        if self._browser:
            try:
                await self._browser.close()
            except:
                pass
            self._browser = None
            self._page = None
            self._authenticated = False
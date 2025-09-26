"""
Native Water Systems Extractor

Built specifically for the modular architecture, implementing the ExtractionPort
interface with clean separation of concerns and progress reporting integration.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from playwright.async_api import async_playwright, Page, Frame

from ...core.domain import ExtractionQuery, ExtractionResult, ExtractionMetadata
from ...core.ports import ExtractionPort, ExtractionError, ProgressReportingPort, AuthenticatedBrowserSessionPort


class WaterSystemsExtractor:
    """Native water systems extractor for modular architecture"""

    def __init__(
        self,
        base_url: str = "http://sdwis:8080/SDWIS/",
        browser_headless: bool = True,
        timeout_ms: int = 30000,
        progress_reporter: Optional[ProgressReportingPort] = None
    ):
        self.base_url = base_url.rstrip('/') + '/'
        self.login_url = f"{self.base_url}jsp/secure/"
        self.search_url = f"{self.base_url}ibsmain_tc.jsp?clearScreenInputs=CHANGE"

        self.browser_headless = browser_headless
        self.timeout_ms = timeout_ms
        self.progress = progress_reporter

        # Internal state
        self._browser = None
        self._page = None
        self._authenticated = False

    def get_supported_data_types(self) -> List[str]:
        """Get supported data types"""
        return ["water_systems"]

    async def validate_query(self, query: ExtractionQuery) -> bool:
        """Validate extraction query"""
        return query.data_type == "water_systems"

    async def extract_data(self, query: ExtractionQuery, browser_session: AuthenticatedBrowserSessionPort) -> ExtractionResult:
        """Extract water systems data"""
        if not await self.validate_query(query):
            return ExtractionResult(
                success=False,
                data=[],
                metadata=ExtractionMetadata(
                    extracted_count=0,
                    extraction_time=0.0,
                    data_type=query.data_type
                ),
                errors=["Invalid query for water systems extractor"]
            )

        start_time = time.time()
        step_times = {}

        try:
            # Get authenticated page from browser session
            step_start = time.time()
            page = await browser_session.get_page()
            step_times['get_page'] = time.time() - step_start
            print(f"⏱️  Get page: {step_times['get_page']:.3f}s")

            # Setup network monitoring (following working pattern)
            step_start = time.time()
            def log_request(request):
                if 'ibs' in request.url.lower():
                    print(f"🌐 Request: {request.method} {request.url[:80]}...")

            def log_response(response):
                if 'ibs' in response.url.lower() and 'DOREQUEST' in response.url:
                    print(f"📡 Response: {response.status} {response.url[:80]}...")

            page.on("request", log_request)
            page.on("response", log_response)
            step_times['setup_monitoring'] = time.time() - step_start
            print(f"⏱️  Setup monitoring: {step_times['setup_monitoring']:.3f}s")

            # Initialize progress if available
            step_start = time.time()
            if self.progress:
                self.progress.set_total_steps(4)  # navigate, search, extract, paginate
            step_times['init_progress'] = time.time() - step_start
            print(f"⏱️  Init progress: {step_times['init_progress']:.3f}s")

            # Step 1: Navigate to search page
            step_start = time.time()
            if self.progress:
                self.progress.increment_step("Navigating to water systems search")

            await page.goto(self.search_url)
            await page.wait_for_load_state('networkidle')
            # Wait for frames to be loaded (following working pattern)
            await page.wait_for_function('() => window.frames && window.frames.length > 0')
            step_times['navigate_to_search'] = time.time() - step_start
            print(f"⏱️  Navigate to search: {step_times['navigate_to_search']:.3f}s")

            # Step 2: Perform search (following working pattern)
            step_start = time.time()
            if self.progress:
                self.progress.increment_step("Executing search query")

            search_frame = await self._find_search_frame(page)
            if not search_frame:
                raise ExtractionError("Could not find search frame")

            await self._execute_search(search_frame, page)
            step_times['execute_search'] = time.time() - step_start
            print(f"⏱️  Execute search: {step_times['execute_search']:.3f}s")

            # Step 3: Extract initial data batch
            step_start = time.time()
            if self.progress:
                self.progress.increment_step("Extracting initial data batch")

            results_frame = await self._find_results_frame(page)
            if not results_frame:
                raise ExtractionError("Could not find results frame")

            # Get total count for progress tracking
            total_expected = await self._get_total_count(results_frame)
            if total_expected is not None:
                print(f"📊 Total results reported by SDWIS (ROWS_RESULTED1): {total_expected}")
            else:
                print("⚠️  Could not read ROWS_RESULTED1 count")
            step_times['find_results_setup'] = time.time() - step_start
            print(f"⏱️  Find results and setup: {step_times['find_results_setup']:.3f}s")

            all_systems = []
            batch_number = 1
            processed_ids = set()

            # Step 5: Extract all batches with pagination
            step_start = time.time()
            if self.progress:
                self.progress.increment_step("Extracting data with pagination")
            step_times['init_pagination'] = time.time() - step_start
            print(f"⏱️  Init pagination: {step_times['init_pagination']:.3f}s")

            while True:
                batch_start = time.time()

                # Update progress with batch info
                if self.progress and total_expected:
                    progress_pct = min(int((len(all_systems) / total_expected) * 100), 99)
                    self.progress.update_progress(
                        progress_pct,
                        f"Extracting batch {batch_number} - {len(all_systems)}/{total_expected} systems"
                    )

                # Extract current batch
                extract_start = time.time()
                batch_systems = await self._extract_current_batch(results_frame)
                extract_time = time.time() - extract_start
                print(f"⏱️  Extract batch {batch_number}: {extract_time:.3f}s")

                if not batch_systems:
                    break

                # Filter duplicates
                unique_systems = []
                for system in batch_systems:
                    system_id = system.get('Water System No.', '')
                    if system_id and system_id not in processed_ids:
                        unique_systems.append(system)
                        processed_ids.add(system_id)

                if not unique_systems:
                    # All systems were duplicates - we're done
                    break

                all_systems.extend(unique_systems)

                # Check if we need to paginate
                if len(batch_systems) < 1000:  # Last batch
                    break

                # Try to get next batch
                nav_start = time.time()
                if not await self._navigate_to_next_batch(results_frame, page):
                    break
                nav_time = time.time() - nav_start
                print(f"⏱️  Navigate to batch {batch_number + 1}: {nav_time:.3f}s")

                batch_total = time.time() - batch_start
                print(f"⏱️  Total batch {batch_number}: {batch_total:.3f}s")

                batch_number += 1

            # Note: Field mapping is handled by ExportService in core layer
            # Adapters should only extract raw data, not transform it

            # Step 6: Cleanup and finalize
            step_start = time.time()
            if self.progress:
                self.progress.increment_step("Finalizing extraction")

            extraction_time = time.time() - start_time

            # Final progress update
            if self.progress:
                self.progress.update_progress(
                    100,
                    f"Extraction complete - {len(all_systems)} systems extracted"
                )

            step_times['finalize'] = time.time() - step_start
            print(f"⏱️  Finalize: {step_times['finalize']:.3f}s")

            # Final validation against ROWS_RESULTED1
            if total_expected is not None:
                if len(all_systems) == total_expected:
                    print(f"✅ Extraction validation: {len(all_systems)} systems extracted matches ROWS_RESULTED1 count ({total_expected})")
                else:
                    print(f"⚠️  Count mismatch: Extracted {len(all_systems)} systems but ROWS_RESULTED1 reported {total_expected}")

            print(f"\n📊 TIMING BREAKDOWN:")
            for step, duration in step_times.items():
                print(f"  {step}: {duration:.3f}s")

            return ExtractionResult(
                success=True,
                data=all_systems,
                metadata=ExtractionMetadata(
                    extracted_count=len(all_systems),
                    extraction_time=extraction_time,
                    data_type="water_systems",
                    total_available=total_expected,
                    source_info={
                        "extractor": "WaterSystemsExtractor",
                        "base_url": self.base_url,
                        "extraction_method": "direct_javascript_access",
                        "pagination_method": "view_next_navigation"
                    },
                    pagination_info={
                        "batches_processed": batch_number,
                        "unique_systems_found": len(all_systems),
                        "total_extracted_records": len(all_systems)
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
                    data_type="water_systems"
                ),
                errors=[f"Water systems extraction failed: {str(e)}"]
            )
        finally:
            # Browser session cleanup is handled by the service layer
            pass

    async def _initialize_browser(self):
        """Initialize Playwright browser"""
        if self._browser:
            return

        playwright = await async_playwright().start()
        self._browser = await playwright.chromium.launch(headless=self.browser_headless)
        self._page = await self._browser.new_page()

        # Set up network monitoring for debugging if needed
        def log_request(request):
            if 'ibs' in request.url.lower() and 'DOREQUEST' in request.url:
                if self.progress:
                    self.progress.report_progress(
                        type('ProgressUpdate', (), {
                            'percent': 0,
                            'message': f"Network request: {request.method} {request.url[-50:]}...",
                            'metadata': {'request_url': request.url}
                        })()
                    )

        self._page.on("request", log_request)

    async def _authenticate(self):
        """Authenticate with SDWIS"""
        if self._authenticated:
            return

        # This will be handled by the authentication adapter in the service layer
        # For now, we assume the page context has valid session
        self._authenticated = True

    async def _navigate_to_search(self):
        """Navigate to water systems search page"""
        await self._page.goto(self.search_url)
        await self._page.wait_for_load_state('networkidle')

        # Wait for frames to load
        await self._page.wait_for_function('() => window.frames && window.frames.length > 0')

    async def _find_search_frame(self, page: Page) -> Optional[Frame]:
        """Find the search frame by counting input elements"""
        for frame in page.frames:
            try:
                frame_inputs = await frame.query_selector_all('input')
                if len(frame_inputs) > 5:  # Search form has multiple inputs
                    return frame
            except:
                continue
        return None

    async def _execute_search(self, search_frame: Frame, page: Page):
        """Execute the search in the search frame following working pattern"""
        # Find the search button (following working pattern)
        search_button = await search_frame.query_selector('button:has-text("Search")')
        if search_button:
            await search_button.click()
            # Wait for search results to load - check for the results frame with data
            # Wait for the results to load by checking for parent.values
            await page.wait_for_load_state('networkidle')
            # Give the JavaScript time to populate parent.values (following working pattern)
            await page.wait_for_function(
                '''() => {
                    try {
                        // Check if parent.values exists and has data
                        return typeof parent !== 'undefined' &&
                               parent.values &&
                               Array.isArray(parent.values) &&
                               parent.values.length > 0;
                    } catch (e) {
                        return false;
                    }
                }''',
                timeout=10000
            )
            print("✅ Search completed")
            return True
        return False

    async def _find_results_frame(self, page: Page) -> Optional[Frame]:
        """Find the frame containing the results table"""
        for frame in page.frames:
            try:
                # Look for the characteristic DFGUILBX table class
                table = await frame.query_selector('table.DFGUILBX')
                if table:
                    return frame
            except:
                continue
        return None

    async def _get_total_count(self, results_frame: Frame) -> Optional[int]:
        """Get the total count from ROWS_RESULTED1 input"""
        try:
            # Wait a moment for value to be populated
            await results_frame.wait_for_timeout(500)

            # Try different selector approaches
            count_element = await results_frame.wait_for_selector(
                'input[name="ROWS_RESULTED1"]',
                timeout=2000,
                state="attached"
            )

            if count_element:
                # Wait for value to be populated
                count_value = await count_element.get_attribute('value')

                # If empty, try to evaluate via JS
                if not count_value:
                    count_value = await results_frame.evaluate('''
                        () => {
                            const elem = document.querySelector('input[name="ROWS_RESULTED1"]');
                            return elem ? elem.value : null;
                        }
                    ''')

                if count_value and str(count_value).strip().isdigit():
                    return int(count_value)
                elif count_value:
                    print(f"    Debug: ROWS_RESULTED1 value = '{count_value}' (not numeric)")
            else:
                print(f"    Debug: ROWS_RESULTED1 element not found in frame")
        except Exception as e:
            print(f"    Debug: Error reading ROWS_RESULTED1: {e}")
        return None

    async def _extract_current_batch(self, results_frame: Frame) -> List[Dict[str, Any]]:
        """Extract water systems from parent.values JavaScript array (following working pattern)"""
        systems_data = await results_frame.evaluate('''
            () => {
                if (typeof parent !== 'undefined' && parent.values && Array.isArray(parent.values)) {
                    return {
                        length: parent.values.length,
                        data: parent.values
                    };
                }
                return null;
            }
        ''')

        if not systems_data:
            return []

        print(f"🎯 Found JavaScript data with {systems_data['length']} items")

        # Process the data (following exact working pattern)
        systems = []
        headers = ['Activity Status', 'Water System No.', 'Name', 'Federal Primary Source',
                  'Federal Type', 'State Type', 'Population', 'Principal County Served']

        for row in systems_data['data']:
            if isinstance(row, list) and len(row) >= 8:
                system = {}
                for i, header in enumerate(headers):
                    if i < len(row) and isinstance(row[i], list) and len(row[i]) >= 1:
                        value = str(row[i][0]).replace('&nbsp;', ' ').replace('&nbsp', ' ').strip()
                        system[header] = value
                    else:
                        system[header] = ''

                if system.get('Water System No.'):
                    systems.append(system)

        return systems


    async def _navigate_to_next_batch(self, results_frame: Frame, page: Page) -> bool:
        """Navigate to next batch using JavaScript navigation"""
        print("🔍 Navigating to next batch using JavaScript...")

        try:
            # Get initial data state for change detection
            initial_length = await results_frame.evaluate('parent.values ? parent.values.length : 0')
            initial_first_ws = await results_frame.evaluate(
                'parent.values && parent.values.length > 0 ? parent.values[0][1][0] : null'
            )
            print(f"📊 Before Next: {initial_length} systems, first: {initial_first_ws}")

            # Use JavaScript navigation to trigger next batch
            navigation_result = await results_frame.evaluate('''
                () => {
                    try {
                        // Find the View menu button
                        const viewMenu = document.querySelector('div.DFGUIMNU') ||
                                       document.querySelector('[title="View"]') ||
                                       document.getElementById('Item1_3');

                        if (!viewMenu) {
                            return { success: false, error: 'View menu not found' };
                        }

                        // Click to open dropdown
                        viewMenu.click();

                        // Small delay for dropdown to appear
                        setTimeout(() => {
                            // Find and click Next item
                            const nextItem = document.querySelector('div#Item1_3_2') ||
                                           document.querySelector('a[accesskey="N"]') ||
                                           Array.from(document.querySelectorAll('div.DFGUIMNU')).find(el =>
                                               el.textContent.includes('Next'));

                            if (nextItem) {
                                nextItem.click();
                                return { success: true };
                            } else {
                                return { success: false, error: 'Next menu item not found' };
                            }
                        }, 100);

                        return { success: true, action: 'clicked_view_menu' };
                    } catch (e) {
                        return { success: false, error: e.toString() };
                    }
                }
            ''')

            if not navigation_result.get('success'):
                print(f"❌ JavaScript navigation failed: {navigation_result.get('error')}")
                return False

            # Wait for the DOREQUEST response
            try:
                async with page.expect_response(
                    lambda response: 'ibs0100e.jsp' in response.url and 'DOREQUEST' in response.url,
                    timeout=8000
                ) as response_info:
                    response = await response_info.value
                    print(f"📡 Got pagination response: {response.status}")
            except Exception as e:
                print(f"⚠️ No pagination response detected: {e}")

            # Check if data changed with shorter timeout
            try:
                await results_frame.wait_for_function(
                    f'''() => {{
                        try {{
                            return parent.values &&
                                   parent.values.length > 0 &&
                                   (parent.values.length !== {initial_length} ||
                                    parent.values[0][1][0] !== "{initial_first_ws}");
                        }} catch (e) {{
                            return false;
                        }}
                    }}''',
                    timeout=3000
                )
                print("✅ Data has changed - pagination successful")
            except:
                print("⚠️ Data may not have changed")

            # Verify final state
            new_length = await results_frame.evaluate('parent.values ? parent.values.length : 0')
            new_first_ws = await results_frame.evaluate(
                'parent.values && parent.values.length > 0 ? parent.values[0][1][0] : null'
            )
            print(f"📊 After Next: {new_length} systems, first: {new_first_ws}")

            # Return true if we got new data
            data_changed = new_length != initial_length or new_first_ws != initial_first_ws
            print(f"🔄 Pagination result: {data_changed}")
            return data_changed

        except Exception as e:
            print(f"❌ Error during pagination: {e}")
            return False

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
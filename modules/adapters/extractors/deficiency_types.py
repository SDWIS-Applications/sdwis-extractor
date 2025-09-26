"""
Deficiency Types Extractor

Extracts all deficiency types from SDWIS by navigating to Site Visit -> Add -> DefTypGoTo button.
Navigation path: Site Visit -> Add -> DefTypGoTo button opens table with all deficiency types.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from playwright.async_api import async_playwright, Page, Frame

from ...core.domain import ExtractionQuery, ExtractionResult, ExtractionMetadata
from ...core.ports import ExtractionPort, ExtractionError, ProgressReportingPort, AuthenticatedBrowserSessionPort


class DeficiencyTypesExtractor:
    """Deficiency types extractor for Site Visit module"""

    def __init__(
        self,
        base_url: str = "http://sdwis:8080/SDWIS/",
        browser_headless: bool = True,
        timeout_ms: int = 30000,
        progress_reporter: Optional[ProgressReportingPort] = None
    ):
        self.base_url = base_url.rstrip('/') + '/'
        self.login_url = f"{self.base_url}jsp/secure/"
        # Site Visit -> Deficiency -> Add navigation (LINK3 from documentation - section 3.2.1)
        self.deficiency_add_url = f"{self.base_url}ibsmain_tc.jsp?clearScreenInputs=LINK3"

        self.browser_headless = browser_headless
        self.timeout_ms = timeout_ms
        self.progress = progress_reporter

        # Internal state
        self._browser = None
        self._page = None
        self._authenticated = False

    def get_supported_data_types(self) -> List[str]:
        """Get supported data types"""
        return ["deficiency_types"]

    async def validate_query(self, query: ExtractionQuery) -> bool:
        """Validate extraction query"""
        return query.data_type == "deficiency_types"

    def _apply_inspection_mapping(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply field name mapping for inspection mode"""
        field_mapping = {
            "Type Code": "code",
            "Default Severity Code": "typical_severity",
            "Default Category Code": "typical_category",
            "Description": "description"
        }

        mapped_data = []
        for item in data:
            mapped_item = {}
            for original_key, value in item.items():
                # Map field names
                mapped_key = field_mapping.get(original_key, original_key.lower().replace(" ", "_"))

                # Special handling for description - convert to lowercase
                if mapped_key == "description" and isinstance(value, str):
                    mapped_item[mapped_key] = value.lower()
                else:
                    mapped_item[mapped_key] = value

            mapped_data.append(mapped_item)

        return mapped_data

    async def extract_data(self, query: ExtractionQuery, browser_session: AuthenticatedBrowserSessionPort) -> ExtractionResult:
        """Extract deficiency types data"""
        if not await self.validate_query(query):
            return ExtractionResult(
                success=False,
                data=[],
                metadata=ExtractionMetadata(
                    extracted_count=0,
                    extraction_time=0.0,
                    data_type=query.data_type
                ),
                errors=["Invalid query for deficiency types extractor"]
            )

        start_time = time.time()
        step_times = {}

        try:
            # Get authenticated page from browser session
            step_start = time.time()
            page = await browser_session.get_page()
            step_times['get_page'] = time.time() - step_start
            print(f"⏱️  Get page: {step_times['get_page']:.3f}s")

            # Setup network monitoring
            step_start = time.time()
            def log_request(request):
                if 'ibs' in request.url.lower():
                    print(f"🌐 Request: {request.method} {request.url[:80]}...")

            def log_response(response):
                if 'ibs' in response.url.lower():
                    print(f"📡 Response: {response.status} {response.url[:80]}...")

            page.on("request", log_request)
            page.on("response", log_response)
            step_times['setup_monitoring'] = time.time() - step_start
            print(f"⏱️  Setup monitoring: {step_times['setup_monitoring']:.3f}s")

            # Initialize progress if available
            step_start = time.time()
            if self.progress:
                self.progress.set_total_steps(5)  # navigate, find_frame, click_button, extract_data, finalize
            step_times['init_progress'] = time.time() - step_start
            print(f"⏱️  Init progress: {step_times['init_progress']:.3f}s")

            # Step 1: Navigate to Site Visit -> Deficiency -> Add page
            step_start = time.time()
            if self.progress:
                self.progress.increment_step("Navigating to Deficiency Add page")

            await page.goto(self.deficiency_add_url)
            await page.wait_for_load_state('networkidle')
            # Wait for frames to be loaded
            await page.wait_for_function('() => window.frames && window.frames.length > 0')
            step_times['navigate_to_deficiency'] = time.time() - step_start
            print(f"⏱️  Navigate to Deficiency Add: {step_times['navigate_to_deficiency']:.3f}s")

            # Step 2: Find the frame containing the DefTypGoTo button
            step_start = time.time()
            if self.progress:
                self.progress.increment_step("Finding DefTypGoTo button frame")

            deficiency_frame = await self._find_deficiency_frame(page)
            if not deficiency_frame:
                raise ExtractionError("Could not find frame with DefTypGoTo button")

            step_times['find_frame'] = time.time() - step_start
            print(f"⏱️  Find DefTypGoTo frame: {step_times['find_frame']:.3f}s")

            # Step 3: Click DefTypGoTo button to open deficiency types table
            step_start = time.time()
            if self.progress:
                self.progress.increment_step("Opening deficiency types table")

            await self._click_deftyp_goto_button(deficiency_frame, page)
            step_times['click_button'] = time.time() - step_start
            print(f"⏱️  Click DefTypGoTo button: {step_times['click_button']:.3f}s")

            # Step 4: Extract deficiency types data from the opened table
            step_start = time.time()
            if self.progress:
                self.progress.increment_step("Extracting deficiency types data")

            # Find the results frame/table containing deficiency types
            results_frame = await self._find_deficiency_results_frame(page)
            if not results_frame:
                raise ExtractionError("Could not find deficiency types results table")

            # Get the count from Field1 input
            total_count = await self._get_deficiency_count(results_frame)
            if total_count is not None:
                print(f"📊 Total deficiency types count from Field1: {total_count}")
            else:
                print("⚠️  Could not read deficiency types count from Field1")

            # Extract deficiency types data
            deficiency_types = await self._extract_deficiency_types(results_frame)

            # Note: Field mapping is handled by ExportService in core layer
            # Adapters should only extract raw data, not transform it

            step_times['extract_data'] = time.time() - step_start
            print(f"⏱️  Extract deficiency types: {step_times['extract_data']:.3f}s")

            # Step 5: Finalize
            step_start = time.time()
            if self.progress:
                self.progress.increment_step("Finalizing extraction")

            extraction_time = time.time() - start_time

            # Final progress update
            if self.progress:
                self.progress.update_progress(
                    100,
                    f"Extraction complete - {len(deficiency_types)} deficiency types extracted"
                )

            step_times['finalize'] = time.time() - step_start
            print(f"⏱️  Finalize: {step_times['finalize']:.3f}s")

            # Final validation against Field1 count
            if total_count is not None:
                if len(deficiency_types) == total_count:
                    print(f"✅ Extraction validation: {len(deficiency_types)} deficiency types extracted matches Field1 count ({total_count})")
                else:
                    print(f"⚠️  Count mismatch: Extracted {len(deficiency_types)} deficiency types but Field1 reported {total_count}")

            print(f"\n📊 TIMING BREAKDOWN:")
            for step, duration in step_times.items():
                print(f"  {step}: {duration:.3f}s")

            return ExtractionResult(
                success=True,
                data=deficiency_types,
                metadata=ExtractionMetadata(
                    extracted_count=len(deficiency_types),
                    extraction_time=extraction_time,
                    data_type="deficiency_types",
                    total_available=total_count,
                    source_info={
                        "extractor": "DeficiencyTypesExtractor",
                        "base_url": self.base_url,
                        "extraction_method": "site_visit_navigation",
                        "navigation_path": "Site Visit -> Add -> DefTypGoTo"
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
                    data_type="deficiency_types"
                ),
                errors=[f"Deficiency types extraction failed: {str(e)}"]
            )
        finally:
            # Browser session cleanup is handled by the service layer
            pass

    async def _find_deficiency_frame(self, page: Page) -> Optional[Frame]:
        """Find the frame containing the DefTypGoTo button"""
        for frame in page.frames:
            try:
                # Look for the DefTypGoTo button by name and id
                deftyp_button = await frame.query_selector('button[name="DefTypGoTo"][id="DefTypGoTo"]')
                if deftyp_button:
                    print("✅ Found DefTypGoTo button frame")
                    return frame
            except:
                continue
        return None

    async def _click_deftyp_goto_button(self, deficiency_frame: Frame, page: Page):
        """Click the DefTypGoTo button to open deficiency types table"""
        try:
            # Click the DefTypGoTo button
            deftyp_button = await deficiency_frame.query_selector('button[name="DefTypGoTo"][id="DefTypGoTo"]')
            if deftyp_button:
                print("🔍 Clicking DefTypGoTo button...")
                await deftyp_button.click()

                # Wait for the deficiency types table/popup to appear
                await page.wait_for_load_state('networkidle')

                # Wait a bit for any dynamic content to load
                await page.wait_for_timeout(2000)

                print("✅ DefTypGoTo button clicked successfully")
                return True
            else:
                raise ExtractionError("DefTypGoTo button not found")
        except Exception as e:
            raise ExtractionError(f"Failed to click DefTypGoTo button: {str(e)}")

    async def _find_deficiency_results_frame(self, page: Page) -> Optional[Frame]:
        """Find the frame containing the deficiency types results table"""
        for frame in page.frames:
            try:
                # Look for Field1 input (holds the count)
                field1_input = await frame.query_selector('input[name="Field1"][id="Field1"]')
                if field1_input:
                    print("✅ Found deficiency types results frame with Field1")
                    return frame

                # Also look for typical SDWIS table structures
                table = await frame.query_selector('table.DFGUILBX')
                if table:
                    # Check if this table contains deficiency data
                    table_text = await frame.text_content()
                    if 'deficiency' in table_text.lower() or 'type' in table_text.lower():
                        print("✅ Found deficiency types table frame")
                        return frame
            except:
                continue
        return None

    async def _get_deficiency_count(self, results_frame: Frame) -> Optional[int]:
        """Get the deficiency types count from Field1 input"""
        try:
            # Wait a moment for value to be populated
            await results_frame.wait_for_timeout(500)

            # Find Field1 input element
            field1_element = await results_frame.wait_for_selector(
                'input[name="Field1"][id="Field1"]',
                timeout=2000,
                state="attached"
            )

            if field1_element:
                # Get the count value
                count_value = await field1_element.get_attribute('value')

                # If empty, try to evaluate via JS
                if not count_value:
                    count_value = await results_frame.evaluate('''
                        () => {
                            const elem = document.querySelector('input[name="Field1"][id="Field1"]');
                            return elem ? elem.value : null;
                        }
                    ''')

                if count_value and str(count_value).strip().isdigit():
                    return int(count_value)
                elif count_value:
                    print(f"    Debug: Field1 value = '{count_value}' (not numeric)")
            else:
                print(f"    Debug: Field1 element not found in frame")
        except Exception as e:
            print(f"    Debug: Error reading Field1: {e}")
        return None

    async def _extract_deficiency_types(self, results_frame: Frame) -> List[Dict[str, Any]]:
        """Extract deficiency types from the full dataset (like parent.values for other extractors)"""
        try:
            # Wait for data to be present
            await results_frame.wait_for_timeout(1000)

            # Method 1: Try to access parent.values array (like water systems extractor)
            parent_values_data = await results_frame.evaluate('''
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

            if parent_values_data:
                print(f"🎯 Found parent.values with {parent_values_data['length']} items")
                return await self._process_parent_values_data(parent_values_data['data'])

            # Method 2: Look for other JavaScript data arrays that might contain the full dataset
            js_data = await results_frame.evaluate('''
                () => {
                    // Check for common SDWIS data variable names
                    const dataVars = ['data', 'values', 'tableData', 'deficiencyData', 'items', 'records'];
                    const results = {};

                    for (let varName of dataVars) {
                        try {
                            if (typeof window[varName] !== 'undefined' && Array.isArray(window[varName])) {
                                results[varName] = {
                                    length: window[varName].length,
                                    data: window[varName]
                                };
                            }
                            if (typeof parent[varName] !== 'undefined' && Array.isArray(parent[varName])) {
                                results['parent.' + varName] = {
                                    length: parent[varName].length,
                                    data: parent[varName]
                                };
                            }
                        } catch (e) {
                            // Continue checking
                        }
                    }

                    return results;
                }
            ''')

            print(f"🔍 JavaScript data arrays found: {list(js_data.keys())}")

            # Use the largest array found
            largest_data = None
            largest_size = 0

            for var_name, var_data in js_data.items():
                if var_data['length'] > largest_size:
                    largest_data = var_data
                    largest_size = var_data['length']
                    print(f"🎯 Using {var_name} array with {largest_size} items")

            if largest_data:
                return await self._process_javascript_data(largest_data['data'])

            # Method 3: Extract from visible table as fallback
            print("⚠️  No JavaScript arrays found, falling back to table extraction")
            return await self._extract_from_table(results_frame)

        except Exception as e:
            print(f"❌ Error extracting deficiency types: {e}")
            return []

    async def _process_parent_values_data(self, data) -> List[Dict[str, Any]]:
        """Process parent.values data (similar to water systems extractor)"""
        deficiency_types = []
        headers = ['Type Code', 'Default Severity Code', 'Default Category Code', 'Description']

        for i, row in enumerate(data):
            if isinstance(row, list) and len(row) >= 4:
                deficiency_type = {}
                for j, header in enumerate(headers):
                    if j < len(row):
                        # Handle nested arrays like in water systems
                        if isinstance(row[j], list) and len(row[j]) >= 1:
                            value = str(row[j][0]).replace('&nbsp;', ' ').replace('&nbsp', ' ').strip()
                        else:
                            value = str(row[j]).replace('&nbsp;', ' ').replace('&nbsp', ' ').strip()
                        deficiency_type[header] = value
                    else:
                        deficiency_type[header] = ''

                deficiency_type['row_index'] = i + 1

                if deficiency_type.get('Type Code'):  # Only add if has type code
                    deficiency_types.append(deficiency_type)

        return deficiency_types


    async def _process_javascript_data(self, data) -> List[Dict[str, Any]]:
        """Process generic JavaScript array data"""
        deficiency_types = []

        for i, item in enumerate(data):
            if isinstance(item, dict):
                # Direct object - use as is
                item['row_index'] = i + 1
                deficiency_types.append(item)
            elif isinstance(item, list):
                # Array format - convert to object
                headers = ['Type Code', 'Default Severity Code', 'Default Category Code', 'Description']
                deficiency_type = {}
                for j, header in enumerate(headers):
                    if j < len(item):
                        deficiency_type[header] = str(item[j]).replace('&nbsp;', ' ').strip()
                    else:
                        deficiency_type[header] = ''
                deficiency_type['row_index'] = i + 1
                deficiency_types.append(deficiency_type)

        return deficiency_types

    async def _extract_from_table(self, results_frame: Frame) -> List[Dict[str, Any]]:
        """Fallback: Extract from visible table structure"""
        try:
            await results_frame.wait_for_selector('table', timeout=5000)

            table_data = await results_frame.evaluate('''
                () => {
                    const tables = document.querySelectorAll('table');
                    let tableData = [];

                    for (let table of tables) {
                        const rows = table.querySelectorAll('tr');
                        if (rows.length > 1) {
                            let rowData = [];
                            for (let row of rows) {
                                const cells = row.querySelectorAll('td, th');
                                if (cells.length > 0) {
                                    let cellData = [];
                                    for (let cell of cells) {
                                        cellData.push(cell.textContent.trim());
                                    }
                                    rowData.push(cellData);
                                }
                            }
                            if (rowData.length > 0) {
                                tableData.push(rowData);
                            }
                        }
                    }

                    return tableData;
                }
            ''')

            print(f"🎯 Found {len(table_data)} tables with data")
            deficiency_types = []

            if table_data:
                for table in table_data:
                    if len(table) > 1:
                        headers = table[0] if table else []
                        for i, row in enumerate(table[1:], 1):
                            if len(row) > 0:
                                deficiency_type = {}
                                for j, value in enumerate(row):
                                    if j < len(headers) and headers[j]:
                                        deficiency_type[headers[j]] = value
                                    else:
                                        deficiency_type[f'column_{j}'] = value
                                deficiency_type['row_index'] = i
                                if any(deficiency_type.values()):
                                    deficiency_types.append(deficiency_type)
                        break

            return deficiency_types

        except Exception as e:
            print(f"❌ Table extraction failed: {e}")
            return []
"""
Native Legal Entities Extractor

Built specifically for the modular architecture, implementing the full-name
continuation strategy with clean progress reporting and error handling.
"""

import asyncio
import re
import time
from typing import Dict, List, Optional, Any, Set
from playwright.async_api import async_playwright, Page, Frame

from ...core.domain import ExtractionQuery, ExtractionResult, ExtractionMetadata
from ...core.ports import ExtractionPort, ExtractionError, ProgressReportingPort, AuthenticatedBrowserSessionPort


class LegalEntitiesExtractor:
    """Native legal entities extractor using full-name continuation strategy"""

    def __init__(
        self,
        base_url: str = "http://sdwis:8080/SDWIS/",
        browser_headless: bool = True,
        timeout_ms: int = 30000,
        progress_reporter: Optional[ProgressReportingPort] = None
    ):
        self.base_url = base_url.rstrip('/') + '/'
        self.login_url = f"{self.base_url}jsp/secure/"
        self.search_url = f"{self.base_url}lemmain_tc.jsp?clearScreenInputs=LINK_1"

        self.browser_headless = browser_headless
        self.timeout_ms = timeout_ms
        self.progress = progress_reporter

        # Internal state
        self._browser = None
        self._page = None
        self._authenticated = False

        # Exclusion patterns for filtering
        self._exclusion_patterns = []

    def get_supported_data_types(self) -> List[str]:
        """Get supported data types"""
        return ["legal_entities"]

    async def validate_query(self, query: ExtractionQuery) -> bool:
        """Validate extraction query"""
        return query.data_type == "legal_entities"

    async def extract_data(self, query: ExtractionQuery, browser_session: AuthenticatedBrowserSessionPort) -> ExtractionResult:
        """Extract legal entities using full-name continuation strategy"""
        if not await self.validate_query(query):
            return ExtractionResult(
                success=False,
                data=[],
                metadata=ExtractionMetadata(
                    extracted_count=0,
                    extraction_time=0.0,
                    data_type=query.data_type
                ),
                errors=["Invalid query for legal entities extractor"]
            )

        start_time = time.time()

        try:
            # Setup exclusion patterns from query filters
            exclusion_patterns = query.filters.get('exclusion_patterns', [])
            self._setup_exclusion_patterns(exclusion_patterns)

            # Get authenticated page from browser session
            page = await browser_session.get_page()
            self._page = page  # Store for use in other methods

            # Initialize progress
            if self.progress:
                self.progress.set_total_steps(4)  # navigate, extract, filter, finalize

            # Step 1: Navigate to legal entities search
            if self.progress:
                self.progress.increment_step("Navigating to legal entities search")

            await page.goto(self.search_url)
            await page.wait_for_load_state('domcontentloaded')

            # Step 3: Extract all entities using full-name continuation
            if self.progress:
                self.progress.increment_step("Extracting entities with full-name continuation")

            all_entities = await self._extract_all_entities(page)

            # Step 4: Apply exclusion filters
            if self.progress:
                self.progress.increment_step("Applying exclusion filters")

            filtered_entities = self._apply_exclusion_filters(all_entities)

            # Note: Field mapping is handled by ExportService in core layer
            # Adapters should only extract raw data, not transform it

            # Step 5: Finalize
            if self.progress:
                self.progress.increment_step("Finalizing extraction")

            extraction_time = time.time() - start_time

            # Final progress update
            if self.progress:
                excluded_count = len(all_entities) - len(filtered_entities)
                self.progress.update_progress(
                    100,
                    f"Extraction complete - {len(filtered_entities)} entities ({excluded_count} filtered)"
                )

            return ExtractionResult(
                success=True,
                data=filtered_entities,
                metadata=ExtractionMetadata(
                    extracted_count=len(filtered_entities),
                    extraction_time=extraction_time,
                    data_type="legal_entities",
                    total_available=len(all_entities),  # Before filtering
                    source_info={
                        "extractor": "LegalEntitiesExtractor",
                        "base_url": self.base_url,
                        "extraction_method": "full_name_continuation",
                        "exclusion_patterns": exclusion_patterns,
                        "total_before_filtering": len(all_entities)
                    }
                ),
                warnings=self._generate_warnings(all_entities, filtered_entities)
            )

        except Exception as e:
            return ExtractionResult(
                success=False,
                data=[],
                metadata=ExtractionMetadata(
                    extracted_count=0,
                    extraction_time=time.time() - start_time,
                    data_type="legal_entities"
                ),
                errors=[f"Legal entities extraction failed: {str(e)}"]
            )
        finally:
            # Browser session cleanup is handled by the service layer
            pass

    def _setup_exclusion_patterns(self, patterns: List[str]):
        """Compile exclusion patterns for efficient filtering"""
        self._exclusion_patterns = []
        for pattern in patterns:
            try:
                compiled_pattern = re.compile(pattern)
                self._exclusion_patterns.append(compiled_pattern)
                if self.progress:
                    self.progress.report_progress(
                        type('ProgressUpdate', (), {
                            'percent': 0,
                            'message': f"Loaded exclusion pattern: {pattern}",
                            'metadata': {'pattern': pattern}
                        })()
                    )
            except re.error as e:
                if self.progress:
                    self.progress.report_progress(
                        type('ProgressUpdate', (), {
                            'percent': 0,
                            'message': f"Invalid regex pattern '{pattern}': {e}",
                            'metadata': {'pattern': pattern, 'error': str(e)}
                        })()
                    )

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
        """Navigate to legal entities search page"""
        await self._page.goto(self.search_url)
        await self._page.wait_for_load_state('networkidle')

        # Wait for frames to load
        await self._page.wait_for_function('() => window.frames && window.frames.length > 0')

    async def _extract_all_entities(self, page: Page) -> List[Dict[str, Any]]:
        """Extract all legal entities using full-name continuation strategy"""
        all_entities = []
        processed_names = set()
        search_continuation = "0"  # Start with "0" to get alphabetically first entries
        search_count = 0
        max_searches = 15  # Safety limit

        while search_continuation and search_count < max_searches:
            search_count += 1

            if self.progress:
                self.progress.update_progress(
                    min(int((search_count / max_searches) * 90), 90),
                    f"Search {search_count}: Starting with '{search_continuation}'"
                )

            # Perform search with continuation name
            batch_entities = await self._search_entities(search_continuation)

            if not batch_entities:
                break

            # Process batch
            new_entities_count = 0
            last_name = None

            for entity in batch_entities:
                entity_name = entity.get('Individual Name', '').strip()

                if entity_name and entity_name not in processed_names:
                    all_entities.append(entity)
                    processed_names.add(entity_name)
                    new_entities_count += 1
                    last_name = entity_name

            if self.progress:
                self.progress.report_progress(
                    type('ProgressUpdate', (), {
                        'percent': min(int((search_count / max_searches) * 90), 90),
                        'message': f"Search {search_count}: Found {new_entities_count} new entities (total: {len(all_entities)})",
                        'metadata': {
                            'search_term': search_continuation,
                            'batch_size': len(batch_entities),
                            'new_entities': new_entities_count,
                            'total_entities': len(all_entities)
                        }
                    })()
                )

            # Prepare next search term
            if last_name and len(batch_entities) >= 1000:
                # Use the last entity's full name for continuation
                search_continuation = last_name
            else:
                # This was the last batch
                break

        return all_entities

    async def _search_entities(self, search_term: str) -> List[Dict[str, Any]]:
        """Perform a single search with the given term"""
        try:
            # Navigate to search page
            await self._page.goto(self.search_url)

            # Find search frame
            search_frame = None
            for attempt in range(20):  # 10 seconds max
                for frame in self._page.frames:
                    try:
                        # Look for the specific LEM search frame
                        if 'LEM_C_LEGAL_ENTITY_SEARCH' in frame.url:
                            frame_inputs = await frame.query_selector_all('input')
                            if len(frame_inputs) > 3:
                                search_frame = frame
                                break
                    except:
                        continue

                if search_frame:
                    break
                await asyncio.sleep(0.5)

            if not search_frame:
                raise ExtractionError("Legal Entity search frame not found")

            # Fill search field
            name_input = await search_frame.wait_for_selector('input[name="Field1"]', timeout=5000)

            # Select "IN - Individual" from dropdown
            legal_entity_dropdown = await search_frame.wait_for_selector('select[name="ListBox1"]', timeout=5000)
            await legal_entity_dropdown.select_option('IN - Individual')

            # Fill search term
            await name_input.evaluate('el => el.value = ""')
            await name_input.fill(search_term)

            # Click search button
            search_button = await search_frame.wait_for_selector('button:has-text("Search")', timeout=5000)
            await search_button.click()

            # Wait for results (following working pattern)
            results_frame = await self._wait_for_lem_results_frame()
            if not results_frame:
                return []

            return await self._extract_entities_from_frame(results_frame)

        except Exception as e:
            if self.progress:
                self.progress.report_progress(
                    type('ProgressUpdate', (), {
                        'percent': 0,
                        'message': f"Error in search '{search_term}': {str(e)}",
                        'metadata': {'search_term': search_term, 'error': str(e)}
                    })()
                )
            return []

    async def _wait_for_lem_results_frame(self):
        """Wait for Legal Entity results frame with data"""
        for attempt in range(40):  # 20 seconds max
            for frame in self._page.frames:
                try:
                    # Look for LEM results frame (similar to water systems pattern)
                    if 'lem0100e.jsp' in frame.url and 'GETDATA' in frame.url:
                        # Check if data is loaded
                        has_data = await frame.evaluate('''
                            () => typeof parent !== 'undefined' &&
                                 parent.values &&
                                 Array.isArray(parent.values) &&
                                 parent.values.length > 0
                        ''')
                        if has_data:
                            return frame
                except:
                    continue

            await asyncio.sleep(0.5)

        raise ExtractionError("Legal Entity results frame with data not found")

    async def _find_results_frame(self) -> Optional[Frame]:
        """Find the frame containing results"""
        for frame in self._page.frames:
            try:
                # Look for results table or data indicators
                table = await frame.query_selector('table.DFGUILBX')
                if table:
                    return frame
            except:
                continue
        return None

    async def _extract_entities_from_frame(self, results_frame: Frame) -> List[Dict[str, Any]]:
        """Extract entities from the results frame"""
        try:
            # Extract data from parent.values array
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

            # Parse the extracted data
            return self._parse_legal_entities_data(systems_data['data'])

        except Exception as e:
            if self.progress:
                self.progress.report_progress(
                    type('ProgressUpdate', (), {
                        'percent': 0,
                        'message': f"Error extracting entities: {str(e)}",
                        'metadata': {'error': str(e)}
                    })()
                )
            return []

    def _parse_legal_entities_data(self, raw_data):
        """Parse raw parent.values data into structured legal entities"""
        entities = []

        if not raw_data:
            return entities

        # Parse each row into raw format first, then apply field tagging
        for row in raw_data:
            if isinstance(row, list) and len(row) >= 2:
                raw_entity = {}

                try:
                    # Extract entity information from nested arrays
                    if len(row) > 0 and isinstance(row[0], list) and len(row[0]) > 0:
                        entity_info = str(row[0][0]) if row[0] else ""
                        raw_entity["entity_info"] = entity_info.replace('&nbsp;', ' ').replace('&nbsp', ' ').replace(' ;', ' ').strip()

                    if len(row) > 1 and isinstance(row[1], list) and len(row[1]) > 0:
                        entity_status = str(row[1][0]) if row[1] else ""
                        raw_entity["status"] = entity_status.replace('&nbsp;', ' ').replace('&nbsp', ' ').replace(' ;', ' ').strip()

                    # Add more fields as we discover the structure
                    for i in range(2, min(len(row), 10)):  # Up to 10 fields
                        if isinstance(row[i], list) and len(row[i]) > 0:
                            field_value = str(row[i][0])
                            # Keep raw values for parsing later - we'll clean up &nbsp; in parse_entity
                            raw_entity[f"field_{i}"] = field_value

                    # Only include if has meaningful entity info
                    if raw_entity.get("entity_info") and len(raw_entity.get("entity_info", "")) > 3:
                        # Parse into properly tagged fields
                        parsed_entity = self._parse_legal_entity(raw_entity)
                        entities.append(parsed_entity)

                except Exception as e:
                    continue

        return entities

    def _parse_legal_entity(self, raw_entity):
        """Parse a single raw legal entity"""
        parsed = {}

        # Parse name field (entity_info) - format: "LAST, FIRST" or single name
        entity_info = raw_entity.get('entity_info', '').replace('&nbsp;', ' ').replace('&nbsp', ' ').replace(' ;', ' ').strip()
        if entity_info:
            if ',' in entity_info:
                # Format: "LAST, FIRST MIDDLE"
                parts = entity_info.split(',', 1)
                parsed['last_name'] = parts[0].strip()
                parsed['first_name'] = parts[1].strip() if len(parts) > 1 else ''
            else:
                # Single name or organization - put in last_name field
                parsed['last_name'] = entity_info.strip()
                parsed['first_name'] = ''
        else:
            parsed['last_name'] = ''
            parsed['first_name'] = ''

        # Status - should all be "IN" for individuals
        parsed['status'] = raw_entity.get('status', '').replace('&nbsp;', ' ').replace('&nbsp', ' ').replace(' ;', ' ').strip()

        # Organization - helps differentiate same-name individuals
        # If it's only &nbsp entities, make it empty, otherwise clean it up
        org_raw = raw_entity.get('field_2', '')
        if org_raw.strip() in ['&nbsp;', '&nbsp'] or not org_raw.strip():
            parsed['organization'] = ''
        else:
            parsed['organization'] = org_raw.replace('&nbsp;', ' ').replace('&nbsp', ' ').replace(' ;', ' ').strip()

        # Mail stop - helps differentiate same-name individuals
        # If it's only &nbsp entities, make it empty, otherwise clean it up
        mail_stop_raw = raw_entity.get('field_3', '')
        if mail_stop_raw.strip() in ['&nbsp;', '&nbsp'] or not mail_stop_raw.strip():
            parsed['mail_stop'] = ''
        else:
            parsed['mail_stop'] = mail_stop_raw.replace('&nbsp;', ' ').replace('&nbsp', ' ').replace(' ;', ' ').strip()

        # Federal ID - extract state code and number (skip redundant full ID)
        federal_id = raw_entity.get('field_9', '').replace('&nbsp;', ' ').replace('&nbsp', ' ').replace(' ;', ' ').strip()
        if federal_id:
            # Extract state code (MS/HQ) and integer number
            import re
            match = re.match(r'([A-Z]{2})(\d+)', federal_id)
            if match:
                parsed['tinlgent_st_code'] = match.group(1)  # MS or HQ
                parsed['tinlgent_is_number'] = int(match.group(2))  # Integer value
            else:
                # If doesn't match expected format, store as-is
                parsed['tinlgent_st_code'] = ''
                parsed['tinlgent_is_number'] = 0
        else:
            parsed['tinlgent_st_code'] = ''
            parsed['tinlgent_is_number'] = 0

        # Convert to the expected format for the modular architecture
        return {
            'Individual Name': f"{parsed['last_name']}, {parsed['first_name']}" if parsed['first_name'] else parsed['last_name'],
            'Status': parsed['status'],
            'Organization': parsed['organization'],
            'Mail Stop': parsed['mail_stop'],
            'State Code': parsed['tinlgent_st_code'],
            'ID Number': parsed['tinlgent_is_number']
        }

    def _apply_exclusion_filters(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply exclusion patterns to filter out unwanted entities"""
        if not self._exclusion_patterns:
            return entities

        filtered_entities = []
        excluded_count = 0

        for entity in entities:
            should_exclude = False
            individual_name = entity.get('Individual Name', '')

            # Check against all exclusion patterns
            for pattern in self._exclusion_patterns:
                if pattern.search(individual_name):
                    should_exclude = True
                    excluded_count += 1
                    break

            if not should_exclude:
                filtered_entities.append(entity)

        if self.progress and excluded_count > 0:
            self.progress.report_progress(
                type('ProgressUpdate', (), {
                    'percent': 95,
                    'message': f"Filtered out {excluded_count} entities using exclusion patterns",
                    'metadata': {'excluded_count': excluded_count}
                })()
            )

        return filtered_entities

    def _generate_warnings(self, all_entities: List[Dict[str, Any]], filtered_entities: List[Dict[str, Any]]) -> List[str]:
        """Generate warnings based on extraction results"""
        warnings = []

        excluded_count = len(all_entities) - len(filtered_entities)
        if excluded_count > 0:
            warnings.append(f"Excluded {excluded_count} entities using exclusion patterns")

        # Check for potential data quality issues
        empty_names = sum(1 for entity in filtered_entities if not entity.get('Individual Name', '').strip())
        if empty_names > 0:
            warnings.append(f"Found {empty_names} entities with empty names")

        return warnings


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
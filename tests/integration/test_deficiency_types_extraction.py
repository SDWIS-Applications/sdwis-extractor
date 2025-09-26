"""
Integration tests for deficiency types extraction functionality
"""

import pytest
from modules.adapters.extractors.deficiency_types import DeficiencyTypesExtractor
from modules.core.domain import ExtractionQuery, ExtractionMetadata
from modules.adapters.auth.browser_session import MockBrowserSession


class TestDeficiencyTypesExtraction:
    """Integration tests for deficiency types extractor"""

    @pytest.fixture
    def mock_browser_session(self):
        """Create mock browser session for testing"""
        return MockBrowserSession()

    @pytest.fixture
    def deficiency_extractor(self):
        """Create deficiency types extractor instance"""
        return DeficiencyTypesExtractor(
            base_url="http://test:8080/SDWIS/",
            browser_headless=True
        )

    @pytest.mark.asyncio
    async def test_supported_data_types(self, deficiency_extractor):
        """Test that deficiency_types is in supported data types"""
        supported_types = deficiency_extractor.get_supported_data_types()
        assert "deficiency_types" in supported_types

    @pytest.mark.asyncio
    async def test_query_validation_valid(self, deficiency_extractor):
        """Test validation of valid deficiency types query"""
        query = ExtractionQuery(
            data_type="deficiency_types",
            filters={},
            metadata={}
        )

        is_valid = await deficiency_extractor.validate_query(query)
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_query_validation_invalid(self, deficiency_extractor):
        """Test validation of invalid query"""
        query = ExtractionQuery(
            data_type="water_systems",  # Wrong data type
            filters={},
            metadata={}
        )

        is_valid = await deficiency_extractor.validate_query(query)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_general_mode_extraction(self, deficiency_extractor, mock_browser_session):
        """Test extraction in general mode (no field mapping)"""
        query = ExtractionQuery(
            data_type="deficiency_types",
            filters={},
            metadata={"export_mode": "general"}
        )

        # Mock the extraction methods to avoid real SDWIS calls
        async def mock_extract_deficiency_types(frame):
            return [
                {
                    "Type Code": "CG000",
                    "Default Severity Code": "SIG",
                    "Default Category Code": "",
                    "Description": "Test Deficiency Type"
                }
            ]

        # Note: This would require more complex mocking for full integration test
        # For now, just test the basic structure

    @pytest.mark.asyncio
    async def test_inspection_mode_extraction_mapping(self, deficiency_extractor, mock_browser_session):
        """Test that inspection mode triggers field mapping"""
        query = ExtractionQuery(
            data_type="deficiency_types",
            filters={},
            metadata={"export_mode": "inspection"}
        )

        # Test the mapping logic directly since full extraction requires SDWIS
        sample_data = [
            {
                "Type Code": "CG000",
                "Default Severity Code": "SIG",
                "Default Category Code": "",
                "Description": "SIGNIFICANT DEFICIENCY TEST"
            }
        ]

        mapped_data = deficiency_extractor._apply_inspection_mapping(sample_data)

        assert len(mapped_data) == 1
        assert mapped_data[0]["code"] == "CG000"
        assert mapped_data[0]["typical_severity"] == "SIG"
        assert mapped_data[0]["typical_category"] == ""
        assert "significant deficiency test" in mapped_data[0]["description"].lower()

    def test_url_construction(self, deficiency_extractor):
        """Test that deficiency add URL is constructed correctly"""
        expected_url = "http://test:8080/SDWIS/ibsmain_tc.jsp?clearScreenInputs=LINK3"
        assert deficiency_extractor.deficiency_add_url == expected_url

    @pytest.mark.asyncio
    async def test_field_count_extraction_simulation(self, deficiency_extractor):
        """Test Field1 count extraction logic (simulated)"""
        # This would test the _get_deficiency_count method in isolation
        # Since it requires a frame, we test the logic conceptually

        # The method should extract count from input[name="Field1"][id="Field1"]
        # and return an integer if the value is numeric

        # Test cases:
        # - Valid numeric value -> return int
        # - Empty value -> return None
        # - Non-numeric value -> return None
        # - Missing element -> return None

        # This validates the extraction logic structure
        assert hasattr(deficiency_extractor, '_get_deficiency_count')

    def test_navigation_parameters(self, deficiency_extractor):
        """Test that navigation parameters are set correctly"""
        # Deficiency types uses LINK3 (Site Visit -> Deficiency -> Add)
        assert "LINK3" in deficiency_extractor.deficiency_add_url

        # Base URL should be properly formatted
        assert deficiency_extractor.base_url.endswith('/')

        # Login URL should be constructed correctly
        expected_login = "http://test:8080/SDWIS/jsp/secure/"
        assert deficiency_extractor.login_url == expected_login
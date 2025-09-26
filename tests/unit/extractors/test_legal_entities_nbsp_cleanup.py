#!/usr/bin/env python3
"""
Test to verify that &nbsp entities are properly cleaned up in legal entities extractor
"""

import pytest
import sys
from pathlib import Path

# Add modules to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from modules.adapters.extractors.legal_entities import LegalEntitiesExtractor


class TestLegalEntitiesNbspCleanup:
    """Test &nbsp cleanup in legal entities parsing"""

    def test_parse_entity_nbsp_cleanup(self):
        """Test that parse_entity properly cleans up &nbsp in org and mail_stop fields"""

        extractor = LegalEntitiesExtractor()

        # Test case 1: Only &nbsp in organization field
        raw_entity_1 = {
            'entity_info': 'SMITH, JOHN',
            'status': 'IN',
            'field_2': '&nbsp',  # organization
            'field_3': '&nbsp',  # mail_stop
            'field_9': 'MS19350'  # federal_id
        }

        parsed_1 = extractor._parse_legal_entity(raw_entity_1)

        assert parsed_1['Organization'] == '', f"Expected empty organization, got '{parsed_1['Organization']}'"
        assert parsed_1['Mail Stop'] == '', f"Expected empty mail_stop, got '{parsed_1['Mail Stop']}'"

        # Test case 2: Real content with &nbsp
        raw_entity_2 = {
            'entity_info': 'DOE, JANE',
            'status': 'IN',
            'field_2': 'Smith&nbspCorporation',  # organization with &nbsp
            'field_3': '123&nbspMain&nbspSt',   # mail_stop with &nbsp
            'field_9': 'MS12345'
        }

        parsed_2 = extractor._parse_legal_entity(raw_entity_2)

        assert parsed_2['Organization'] == 'Smith Corporation', f"Expected 'Smith Corporation', got '{parsed_2['Organization']}'"
        assert parsed_2['Mail Stop'] == '123 Main St', f"Expected '123 Main St', got '{parsed_2['Mail Stop']}'"

        # Test case 3: Empty fields
        raw_entity_3 = {
            'entity_info': 'BROWN, BOB',
            'status': 'IN',
            'field_2': '',  # empty organization
            'field_3': '',  # empty mail_stop
            'field_9': 'MS67890'
        }

        parsed_3 = extractor._parse_legal_entity(raw_entity_3)

        assert parsed_3['Organization'] == '', f"Expected empty organization, got '{parsed_3['Organization']}'"
        assert parsed_3['Mail Stop'] == '', f"Expected empty mail_stop, got '{parsed_3['Mail Stop']}'"

        # Test case 4: Normal content (no &nbsp;)
        raw_entity_4 = {
            'entity_info': 'JONES, MARY',
            'status': 'IN',
            'field_2': 'ACME Corp',
            'field_3': 'Suite 200',
            'field_9': 'MS11111'
        }

        parsed_4 = extractor._parse_legal_entity(raw_entity_4)

        assert parsed_4['Organization'] == 'ACME Corp', f"Expected 'ACME Corp', got '{parsed_4['Organization']}'"
        assert parsed_4['Mail Stop'] == 'Suite 200', f"Expected 'Suite 200', got '{parsed_4['Mail Stop']}'"

        # Test case 5: &nbsp; (with semicolon) in organization field
        raw_entity_5 = {
            'entity_info': 'JONES, BILL',
            'status': 'IN',
            'field_2': '&nbsp;',  # organization with semicolon
            'field_3': '&nbsp;',  # mail_stop with semicolon
            'field_9': 'MS55555'  # federal_id
        }

        parsed_5 = extractor._parse_legal_entity(raw_entity_5)

        assert parsed_5['Organization'] == '', f"Expected empty organization, got '{parsed_5['Organization']}'"
        assert parsed_5['Mail Stop'] == '', f"Expected empty mail_stop, got '{parsed_5['Mail Stop']}'"

    def test_csv_output_format(self):
        """Test that the final output doesn't contain &nbsp in CSV format"""

        extractor = LegalEntitiesExtractor()

        # Simulate a raw entity with &nbsp
        raw_entity = {
            'entity_info': 'TEST, USER',
            'status': 'IN',
            'field_2': '&nbsp',  # organization
            'field_3': '&nbsp',  # mail_stop
            'field_9': 'MS99999'
        }

        parsed = extractor._parse_legal_entity(raw_entity)

        # Create CSV-like output to verify
        csv_line = f'"{parsed["Individual Name"]}",{parsed["Status"]},{parsed["Organization"]},{parsed["Mail Stop"]},{parsed["State Code"]},{parsed["ID Number"]}'

        print(f"CSV line: {csv_line}")

        # Verify no &nbsp in the output
        assert '&nbsp' not in csv_line, f"CSV output still contains &nbsp: {csv_line}"
        assert ',,' in csv_line, f"Expected empty fields (,,) in CSV, got: {csv_line}"


if __name__ == "__main__":
    test = TestLegalEntitiesNbspCleanup()

    print("Testing &nbsp cleanup in legal entities...")
    test.test_parse_entity_nbsp_cleanup()
    print("✓ parse_entity cleanup test passed")

    test.test_csv_output_format()
    print("✓ CSV output format test passed")

    print("All tests passed!")
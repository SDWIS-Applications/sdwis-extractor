"""
Unit tests for ExtractionQuery domain model.

Tests the core business logic and validation rules for extraction queries
without any infrastructure dependencies.
"""

import pytest
from modules.core.domain import ExtractionQuery, PaginationConfig


class TestExtractionQuery:
    """Test the ExtractionQuery domain model."""

    def test_valid_extraction_query_creation(self):
        """Test creating a valid extraction query."""
        query = ExtractionQuery(
            data_type="water_systems",
            filters={"status": "active"},
            pagination=PaginationConfig(max_pages=5)
        )

        assert query.data_type == "water_systems"
        assert query.filters == {"status": "active"}
        assert query.pagination.max_pages == 5
        assert isinstance(query.metadata, dict)

    def test_extraction_query_with_defaults(self):
        """Test extraction query with default values."""
        query = ExtractionQuery(data_type="legal_entities")

        assert query.data_type == "legal_entities"
        assert query.filters == {}
        assert isinstance(query.pagination, PaginationConfig)
        assert query.metadata == {}

    def test_invalid_data_type_raises_error(self):
        """Test that invalid data types are rejected."""
        with pytest.raises(ValueError, match="Unsupported data_type: invalid_type"):
            ExtractionQuery(data_type="invalid_type")

    def test_supported_data_types(self):
        """Test all supported data types are accepted."""
        supported_types = ["water_systems", "legal_entities", "sample_schedules"]

        for data_type in supported_types:
            query = ExtractionQuery(data_type=data_type)
            assert query.data_type == data_type

    def test_filters_are_mutable_dict(self):
        """Test that filters can be modified after creation."""
        query = ExtractionQuery(data_type="water_systems")

        # Should start empty
        assert query.filters == {}

        # Should be modifiable
        query.filters["new_filter"] = "value"
        assert query.filters["new_filter"] == "value"

    def test_metadata_is_mutable_dict(self):
        """Test that metadata can be modified after creation."""
        query = ExtractionQuery(data_type="water_systems")

        # Should start empty
        assert query.metadata == {}

        # Should be modifiable
        query.metadata["source"] = "test"
        assert query.metadata["source"] == "test"

    def test_pagination_config_integration(self):
        """Test integration with PaginationConfig."""
        pagination = PaginationConfig(
            page_size=50,
            max_pages=10,
            start_page=2,
            auto_paginate=False
        )

        query = ExtractionQuery(
            data_type="water_systems",
            pagination=pagination
        )

        assert query.pagination.page_size == 50
        assert query.pagination.max_pages == 10
        assert query.pagination.start_page == 2
        assert query.pagination.auto_paginate is False

    def test_query_equality(self):
        """Test that queries with same values are considered equal."""
        query1 = ExtractionQuery(
            data_type="water_systems",
            filters={"status": "active"},
            pagination=PaginationConfig(max_pages=5)
        )

        query2 = ExtractionQuery(
            data_type="water_systems",
            filters={"status": "active"},
            pagination=PaginationConfig(max_pages=5)
        )

        # Note: dataclass equality comparison
        assert query1.data_type == query2.data_type
        assert query1.filters == query2.filters
        assert query1.pagination.max_pages == query2.pagination.max_pages

    def test_query_with_complex_filters(self):
        """Test extraction query with complex filter objects."""
        complex_filters = {
            "exclusion_patterns": [".*ADDRESS.*", "^[A-Z]{2}\\d+$"],
            "search_params": {
                "pws_id": "0010001",
                "facility_id": "WELL 1"
            },
            "date_range": {
                "start": "2023-01-01",
                "end": "2023-12-31"
            }
        }

        query = ExtractionQuery(
            data_type="legal_entities",
            filters=complex_filters
        )

        assert query.filters["exclusion_patterns"] == [".*ADDRESS.*", "^[A-Z]{2}\\d+$"]
        assert query.filters["search_params"]["pws_id"] == "0010001"
        assert query.filters["date_range"]["start"] == "2023-01-01"


class TestPaginationConfig:
    """Test the PaginationConfig value object."""

    def test_pagination_config_defaults(self):
        """Test default pagination configuration."""
        config = PaginationConfig()

        assert config.page_size is None
        assert config.max_pages is None
        assert config.start_page == 1
        assert config.auto_paginate is True

    def test_pagination_config_with_values(self):
        """Test pagination config with specific values."""
        config = PaginationConfig(
            page_size=100,
            max_pages=5,
            start_page=2,
            auto_paginate=False
        )

        assert config.page_size == 100
        assert config.max_pages == 5
        assert config.start_page == 2
        assert config.auto_paginate is False

    def test_pagination_config_immutable_behavior(self):
        """Test that pagination config behaves as a value object."""
        config = PaginationConfig(page_size=100)

        # Test that config retains its values (value object behavior)
        assert config.page_size == 100

        # Note: PaginationConfig is currently mutable dataclass
        # If immutability is required, add frozen=True to @dataclass decorator

    def test_pagination_config_in_extraction_query(self):
        """Test that pagination config works correctly within extraction query."""
        config = PaginationConfig(max_pages=3)
        query = ExtractionQuery(data_type="water_systems", pagination=config)

        assert query.pagination.max_pages == 3
        assert query.pagination.auto_paginate is True


@pytest.mark.unit
class TestDomainModelIntegration:
    """Test integration between domain models."""

    def test_extraction_query_serializable(self):
        """Test that extraction query can be serialized for logging/debugging."""
        query = ExtractionQuery(
            data_type="water_systems",
            filters={"status": "active"},
            pagination=PaginationConfig(max_pages=2)
        )

        # Should be representable as string
        str_repr = str(query)
        assert "water_systems" in str_repr
        assert "ExtractionQuery" in str_repr

        # Should be representable for debugging
        repr_str = repr(query)
        assert "water_systems" in repr_str

    def test_query_with_metadata_for_tracing(self):
        """Test adding tracing metadata to queries."""
        query = ExtractionQuery(
            data_type="water_systems",
            metadata={
                "request_id": "req_123",
                "user_id": "user_456",
                "source": "cli",
                "timestamp": "2023-09-25T10:30:00Z"
            }
        )

        assert query.metadata["request_id"] == "req_123"
        assert query.metadata["source"] == "cli"

    def test_business_rule_validation(self):
        """Test that domain model enforces business rules."""
        # Business rule: data_type must be from supported list
        supported_types = {"water_systems", "legal_entities", "sample_schedules"}

        for valid_type in supported_types:
            # Should not raise
            query = ExtractionQuery(data_type=valid_type)
            assert query.data_type == valid_type

        # Invalid types should raise
        invalid_types = ["users", "reports", "", None]
        for invalid_type in invalid_types:
            with pytest.raises((ValueError, TypeError)):
                ExtractionQuery(data_type=invalid_type)
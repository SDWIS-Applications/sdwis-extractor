"""
Core domain models for SDWIS data extraction.

These models define the fundamental data structures and value objects
used throughout the application, independent of any infrastructure concerns.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime


@dataclass
class PaginationConfig:
    """Configuration for pagination behavior during extraction"""

    page_size: Optional[int] = None
    max_pages: Optional[int] = None
    start_page: int = 1
    auto_paginate: bool = True


@dataclass
class ExtractionQuery:
    """Request parameters for data extraction"""

    data_type: str              # "water_systems", "legal_entities", "deficiency_types"
    filters: Dict[str, Any] = field(default_factory=dict)     # Optional search filters
    pagination: PaginationConfig = field(default_factory=PaginationConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)    # Additional context

    def __post_init__(self):
        """Validate data_type is supported"""
        supported_types = {"water_systems", "legal_entities", "deficiency_types", "sample_schedules"}
        if self.data_type not in supported_types:
            raise ValueError(f"Unsupported data_type: {self.data_type}. Must be one of: {supported_types}")


@dataclass
class ExtractionMetadata:
    """Metadata about the extraction operation"""

    extracted_count: int
    extraction_time: float
    data_type: str
    source_info: Dict[str, Any] = field(default_factory=dict)
    total_available: Optional[int] = None  # From SDWIS interface (e.g., ROWS_RESULTED1)
    extraction_timestamp: datetime = field(default_factory=datetime.now)
    pagination_info: Dict[str, Any] = field(default_factory=dict)  # Pages processed, batches, etc.


@dataclass
class ExtractionResult:
    """Standardized extraction output"""

    success: bool
    data: List[Dict[str, Any]]  # Extracted records
    metadata: ExtractionMetadata
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if extraction encountered any errors"""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if extraction encountered any warnings"""
        return len(self.warnings) > 0

    @property
    def record_count(self) -> int:
        """Get the number of extracted records"""
        return len(self.data)




@dataclass
class ProgressUpdate:
    """Progress update information"""

    percent: int  # 0-100
    message: str
    current_step: int
    total_steps: int
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate percent is in valid range"""
        if not 0 <= self.percent <= 100:
            raise ValueError(f"Progress percent must be between 0 and 100, got: {self.percent}")
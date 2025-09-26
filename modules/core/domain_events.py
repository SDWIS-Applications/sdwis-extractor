"""
Domain Events System

Defines domain events and event handling infrastructure for the SDWIS automation system.
Events represent significant business occurrences that other parts of the system may need to react to.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Optional, Protocol, Callable, Awaitable
from uuid import uuid4
from enum import Enum
from abc import ABC, abstractmethod


class EventSeverity(Enum):
    """Event severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True)
class DomainEvent(ABC):
    """Base class for all domain events"""
    event_id: str
    timestamp: datetime
    event_type: str
    aggregate_id: str  # ID of the aggregate that generated the event
    severity: EventSeverity
    context: Dict[str, Any]

    def __post_init__(self):
        # Ensure immutability of events
        if not self.event_id:
            object.__setattr__(self, 'event_id', str(uuid4()))
        if not self.timestamp:
            object.__setattr__(self, 'timestamp', datetime.now())


# Export-related events
@dataclass(frozen=True)
class ExportStartedEvent(DomainEvent):
    """Published when an export operation begins"""
    data_types: List[str]
    export_mode: str
    output_format: str
    estimated_records: Optional[int] = None

    def __post_init__(self):
        super().__post_init__()
        if not self.event_type:
            object.__setattr__(self, 'event_type', 'ExportStarted')


@dataclass(frozen=True)
class ExportProgressEvent(DomainEvent):
    """Published during export operation progress"""
    data_type: str
    completed_records: int
    total_records: Optional[int]
    progress_percentage: float
    current_operation: str

    def __post_init__(self):
        super().__post_init__()
        if not self.event_type:
            object.__setattr__(self, 'event_type', 'ExportProgress')


@dataclass(frozen=True)
class ExportCompletedEvent(DomainEvent):
    """Published when an export operation completes successfully"""
    data_types: List[str]
    export_mode: str
    output_paths: List[str]
    total_records: int
    execution_time_seconds: float

    def __post_init__(self):
        super().__post_init__()
        if not self.event_type:
            object.__setattr__(self, 'event_type', 'ExportCompleted')


@dataclass(frozen=True)
class ExportFailedEvent(DomainEvent):
    """Published when an export operation fails"""
    data_types: List[str]
    export_mode: str
    error_message: str
    error_type: str
    partial_results: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        super().__post_init__()
        if not self.event_type:
            object.__setattr__(self, 'event_type', 'ExportFailed')


@dataclass(frozen=True)
class ExportValidationFailedEvent(DomainEvent):
    """Published when export configuration validation fails"""
    configuration_errors: List[str]
    suggested_fixes: List[str]

    def __post_init__(self):
        super().__post_init__()
        if not self.event_type:
            object.__setattr__(self, 'event_type', 'ExportValidationFailed')


# Extraction-related events
@dataclass(frozen=True)
class ExtractionStartedEvent(DomainEvent):
    """Published when data extraction begins"""
    data_type: str
    query_parameters: Dict[str, Any]

    def __post_init__(self):
        super().__post_init__()
        if not self.event_type:
            object.__setattr__(self, 'event_type', 'ExtractionStarted')


@dataclass(frozen=True)
class ExtractionCompletedEvent(DomainEvent):
    """Published when data extraction completes"""
    data_type: str
    records_extracted: int
    extraction_time_seconds: float

    def __post_init__(self):
        super().__post_init__()
        if not self.event_type:
            object.__setattr__(self, 'event_type', 'ExtractionCompleted')


@dataclass(frozen=True)
class ExtractionFailedEvent(DomainEvent):
    """Published when data extraction fails"""
    data_type: str
    error_message: str
    retry_count: int

    def __post_init__(self):
        super().__post_init__()
        if not self.event_type:
            object.__setattr__(self, 'event_type', 'ExtractionFailed')


# Schema and configuration events
@dataclass(frozen=True)
class SchemaLoadedEvent(DomainEvent):
    """Published when an export schema is loaded"""
    schema_name: str
    schema_version: str

    def __post_init__(self):
        super().__post_init__()
        if not self.event_type:
            object.__setattr__(self, 'event_type', 'SchemaLoaded')


@dataclass(frozen=True)
class SchemaMigratedEvent(DomainEvent):
    """Published when a schema is migrated to a new version"""
    schema_name: str
    from_version: str
    to_version: str
    migration_details: Dict[str, Any]

    def __post_init__(self):
        super().__post_init__()
        if not self.event_type:
            object.__setattr__(self, 'event_type', 'SchemaMigrated')


# Event handling infrastructure
EventHandler = Callable[[DomainEvent], Awaitable[None]]


class EventPublisher(Protocol):
    """Port interface for event publishing"""

    async def publish(self, event: DomainEvent) -> None:
        """Publish a domain event"""
        ...

    async def publish_batch(self, events: List[DomainEvent]) -> None:
        """Publish multiple events as a batch"""
        ...


class EventSubscriber(Protocol):
    """Port interface for event subscription"""

    async def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe to events of a specific type"""
        ...

    async def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Unsubscribe from events"""
        ...


class InMemoryEventBus:
    """Simple in-memory event bus implementation"""

    def __init__(self):
        self._handlers: Dict[str, List[EventHandler]] = {}
        self._global_handlers: List[EventHandler] = []

    async def publish(self, event: DomainEvent) -> None:
        """Publish a domain event to all registered handlers"""
        # Notify specific event type handlers
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                # In a real system, this would be logged properly
                print(f"Event handler error for {event.event_type}: {e}")

        # Notify global handlers
        for handler in self._global_handlers:
            try:
                await handler(event)
            except Exception as e:
                print(f"Global event handler error: {e}")

    async def publish_batch(self, events: List[DomainEvent]) -> None:
        """Publish multiple events"""
        for event in events:
            await self.publish(event)

    async def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe to events of a specific type"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def subscribe_global(self, handler: EventHandler) -> None:
        """Subscribe to all events"""
        self._global_handlers.append(handler)

    async def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Unsubscribe from events"""
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
            except ValueError:
                pass  # Handler wasn't subscribed


class EventStore:
    """Simple event store for audit and replay purposes"""

    def __init__(self):
        self._events: List[DomainEvent] = []

    async def store_event(self, event: DomainEvent) -> None:
        """Store an event for audit purposes"""
        self._events.append(event)

    def get_events(
        self,
        aggregate_id: Optional[str] = None,
        event_type: Optional[str] = None,
        after_timestamp: Optional[datetime] = None
    ) -> List[DomainEvent]:
        """Retrieve stored events with optional filtering"""
        filtered_events = self._events

        if aggregate_id:
            filtered_events = [e for e in filtered_events if e.aggregate_id == aggregate_id]

        if event_type:
            filtered_events = [e for e in filtered_events if e.event_type == event_type]

        if after_timestamp:
            filtered_events = [e for e in filtered_events if e.timestamp > after_timestamp]

        return filtered_events

    def get_event_statistics(self) -> Dict[str, Any]:
        """Get statistics about stored events"""
        event_counts = {}
        severity_counts = {}

        for event in self._events:
            # Count by event type
            event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1

            # Count by severity
            severity_counts[event.severity.value] = severity_counts.get(event.severity.value, 0) + 1

        return {
            'total_events': len(self._events),
            'event_type_counts': event_counts,
            'severity_counts': severity_counts,
            'first_event_timestamp': self._events[0].timestamp if self._events else None,
            'last_event_timestamp': self._events[-1].timestamp if self._events else None
        }


# Event builder utilities
class EventBuilder:
    """Builder for creating domain events with common patterns"""

    @staticmethod
    def create_export_started(
        aggregate_id: str,
        data_types: List[str],
        export_mode: str,
        output_format: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ExportStartedEvent:
        """Create an export started event"""
        return ExportStartedEvent(
            event_id=str(uuid4()),
            timestamp=datetime.now(),
            event_type='ExportStarted',
            aggregate_id=aggregate_id,
            severity=EventSeverity.INFO,
            context=context or {},
            data_types=data_types,
            export_mode=export_mode,
            output_format=output_format
        )

    @staticmethod
    def create_export_failed(
        aggregate_id: str,
        data_types: List[str],
        export_mode: str,
        error_message: str,
        error_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ExportFailedEvent:
        """Create an export failed event"""
        return ExportFailedEvent(
            event_id=str(uuid4()),
            timestamp=datetime.now(),
            event_type='ExportFailed',
            aggregate_id=aggregate_id,
            severity=EventSeverity.ERROR,
            context=context or {},
            data_types=data_types,
            export_mode=export_mode,
            error_message=error_message,
            error_type=error_type
        )
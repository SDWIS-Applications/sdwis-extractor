# SDWIS Automation Test Suite

This test suite is designed to validate the hexagonal architecture of the SDWIS automation system. The structure mirrors the architectural layers and ensures that hexagonal principles are maintained as the system evolves.

## Test Structure Overview

```
tests/
├── unit/                          # Fast, isolated tests (< 100ms each)
│   ├── core/                      # Domain layer tests - Pure business logic
│   │   ├── domain/                # Domain models, value objects, entities
│   │   │   └── test_extraction_query.py    # ExtractionQuery domain model tests
│   │   ├── services/              # Application services, orchestration logic
│   │   └── ports/                 # Port interfaces and contracts
│   └── adapters/                  # Infrastructure layer tests
│       ├── auth/                  # Authentication adapters
│       ├── extractors/            # Data extraction adapters
│       ├── output/                # Output format adapters
│       └── progress/              # Progress reporting adapters
├── integration/                   # Cross-layer tests (100ms - 5s each)
│   ├── test_batch_session_reuse.py        # Batch extraction with session reuse
│   ├── test_context_manager.py            # Context manager session patterns
│   ├── test_modular_architecture.py       # Modular architecture functionality
│   ├── test_native_extractors.py          # Native extractor implementations
│   └── test_session_reuse.py              # Browser session reuse patterns
├── contract/                      # Port compliance tests (validates interfaces)
│   └── test_extraction_port_compliance.py # ExtractionPort implementation compliance
├── architecture/                  # Architecture validation tests
│   ├── test_hexagonal_compliance.py       # Hexagonal architecture enforcement
│   └── test_architecture_improvements.py  # Architecture enhancement validation
├── e2e/                          # End-to-end tests (> 5s, full workflows)
└── fixtures/                     # Test data, mock objects, utilities
    ├── mock_data/                 # Sample test data files
    ├── test_configurations/       # Test configuration files
    └── test_helpers.py           # Test utilities and mock factories
```

## Test Categories

### 🏃‍♂️ **Unit Tests** (`tests/unit/`)
- **Purpose**: Test individual components in isolation
- **Speed**: < 100ms per test
- **Dependencies**: None (all external dependencies mocked)
- **Coverage**: Domain logic, individual adapter functionality

**Examples**:
- Domain model validation rules
- Service orchestration logic
- Individual adapter transformations
- Error handling scenarios

### 🔗 **Integration Tests** (`tests/integration/`)
- **Purpose**: Test interaction between multiple components
- **Speed**: 100ms - 5s per test
- **Dependencies**: Multiple real adapters, mocked external systems
- **Coverage**: Component collaboration, data flow

**Examples**:
- Service + adapter integration
- Registry + factory patterns
- Session management workflows
- Export pipeline functionality

### 📋 **Contract Tests** (`tests/contract/`)
- **Purpose**: Validate that all implementations follow port contracts
- **Speed**: < 500ms per test
- **Dependencies**: All adapter implementations
- **Coverage**: Interface compliance, behavioral contracts

**Examples**:
- All extractors implement `ExtractionPort` correctly
- All output adapters implement `OutputPort` correctly
- Mock adapters behave identically to real ones
- Method signatures and return types

### 🏛️ **Architecture Tests** (`tests/architecture/`)
- **Purpose**: Enforce hexagonal architecture principles
- **Speed**: < 1s per test (static analysis)
- **Dependencies**: Source code analysis
- **Coverage**: Dependency direction, layer isolation, coupling

**Examples**:
- Core layer doesn't import adapter layer
- Services depend on ports, not concrete classes
- No circular dependencies between layers
- Business logic isolation verification

### 🌐 **End-to-End Tests** (`tests/e2e/`)
- **Purpose**: Validate complete user workflows
- **Speed**: > 5s per test
- **Dependencies**: Full system, may require real SDWIS connection
- **Coverage**: Complete use cases, user scenarios

**Examples**:
- Full extraction workflows
- CLI command execution
- Error recovery scenarios
- Performance validation

## Running Tests

### By Category (Recommended)
```bash
# Fast feedback loop - Run during development
pytest tests/unit tests/contract -m "not real" -v

# Integration validation
pytest tests/integration -m "not real" -v

# Architecture compliance check
pytest tests/architecture -v

# Full system validation (slow)
pytest tests/e2e -v

# All tests (excluding those requiring real SDWIS)
pytest -m "not real" -v
```

### By Test Type
```bash
# Unit tests only
pytest tests/unit/ -v

# Contract compliance
pytest tests/contract/ -v

# Architecture validation
pytest tests/architecture/ -v

# Integration tests
pytest tests/integration/ -v

# End-to-end tests
pytest tests/e2e/ -v
```

### With Coverage
```bash
# Generate coverage report
pytest --cov=modules --cov-report=html --cov-report=term -v

# Coverage by layer
pytest --cov=modules.core tests/unit/core/ -v
pytest --cov=modules.adapters tests/unit/adapters/ -v
```

## Test Markers

Tests use pytest markers to categorize functionality:

- `@pytest.mark.unit` - Unit tests (fast, isolated)
- `@pytest.mark.integration` - Integration tests (multiple components)
- `@pytest.mark.contract` - Port contract compliance tests
- `@pytest.mark.architecture` - Architecture validation tests
- `@pytest.mark.e2e` - End-to-end tests (full workflows)
- `@pytest.mark.mock` - Tests using mock data only
- `@pytest.mark.real` - Tests requiring real SDWIS connection (CI skip)

## Hexagonal Architecture Test Principles

### 1. **Domain Layer Testing**
- Test business logic in complete isolation
- No infrastructure dependencies in domain tests
- Focus on business rules, validation, and behavior
- Mock all external dependencies

### 2. **Port Contract Testing**
- Verify all implementations follow the same interface
- Test behavioral contracts, not just method signatures
- Ensure mock adapters behave like real ones
- Validate error handling consistency

### 3. **Adapter Testing**
- Test infrastructure concerns (HTTP, file I/O, databases)
- Mock external systems but test adapter logic
- Verify data transformations and mappings
- Test error scenarios and edge cases

### 4. **Architecture Compliance**
- Automatically enforce dependency direction rules
- Validate layer boundaries are not violated
- Check for circular dependencies
- Ensure business logic doesn't leak into adapters

### 5. **Integration Testing Strategy**
- Test component collaboration without external systems
- Use real adapters with mocked dependencies
- Validate data flows and transformations
- Test error propagation and handling

## Configuration Files

### `pytest.ini` (Project Root)
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (slower, multiple components)
    contract: Port contract compliance tests
    architecture: Architecture validation tests
    e2e: End-to-end tests (slowest, full system)
    mock: Tests using mock data only
    real: Tests requiring real SDWIS connection
addopts = -v --strict-markers --tb=short
filterwarnings =
    ignore::DeprecationWarning:playwright.*
    ignore::ResourceWarning
```

### `conftest.py` (Test Configuration)
Located in `tests/conftest.py` - contains shared fixtures, test configuration, and utilities used across all test types.

## Test Fixtures

### Mock Data (`tests/fixtures/mock_data/`)
- Sample extraction results
- Mock SDWIS responses
- Test configuration files
- Error scenario data

### Test Helpers (`tests/fixtures/test_helpers.py`)
- Common test utilities
- Mock object factories
- Assertion helpers
- Test data generators

## Development Workflow

### 1. **Test-Driven Development**
```bash
# Write failing test first
pytest tests/unit/core/services/test_export_service.py::test_new_feature -v

# Implement feature
# Run test to verify
pytest tests/unit/core/services/test_export_service.py::test_new_feature -v
```

### 2. **Architecture Compliance Check**
```bash
# Before committing changes
pytest tests/architecture/ -v

# Verify no architectural violations
pytest tests/contract/ -v
```

### 3. **Full Validation**
```bash
# Run all tests except those requiring real SDWIS
pytest -m "not real" --cov=modules --cov-fail-under=80 -v
```

## Guidelines for Test Development

### **Unit Test Guidelines**
- Each test should run in < 100ms
- Mock all external dependencies
- Test one specific behavior per test method
- Use descriptive test names that explain the scenario
- Follow AAA pattern: Arrange, Act, Assert

### **Integration Test Guidelines**
- Test realistic scenarios with multiple components
- Use real adapters but mock external systems
- Focus on component interaction and data flow
- Test error propagation between layers

### **Contract Test Guidelines**
- Test all implementations of a port interface
- Verify behavioral contracts, not just method signatures
- Ensure consistent error handling across implementations
- Validate that mocks behave like real implementations

### **Architecture Test Guidelines**
- Write tests that prevent architectural violations
- Use static analysis to check dependency directions
- Validate that business logic stays in the core layer
- Check for proper separation of concerns

## Continuous Integration

This test suite is designed to run in CI/CD pipelines:

1. **Pull Request Checks**: Unit, contract, and architecture tests
2. **Integration Testing**: Full integration test suite
3. **Nightly Builds**: End-to-end tests with mock SDWIS
4. **Release Validation**: Full test suite including performance tests

## Contributing

When adding new features:

1. **Start with tests**: Write contract tests for new ports
2. **Validate architecture**: Run architecture tests after changes
3. **Maintain coverage**: Aim for >80% test coverage
4. **Document behavior**: Use descriptive test names and docstrings
5. **Test error scenarios**: Don't just test the happy path

## Common Test Patterns

### Testing Services
```python
def test_extraction_service_with_mocked_dependencies():
    # Arrange
    mock_extractor = Mock(spec=ExtractionPort)
    mock_extractor.extract_data.return_value = ExtractionResult(...)

    service = ExtractionService(
        extractor=mock_extractor,
        browser_session_factory=Mock(),
        progress=Mock(spec=ProgressReportingPort),
        output=Mock(spec=OutputPort),
        config=Mock(spec=ConfigurationPort)
    )

    # Act
    result = await service.perform_extraction(query)

    # Assert
    assert result.success
    mock_extractor.extract_data.assert_called_once()
```

### Testing Adapters
```python
def test_json_output_adapter_formats_data_correctly():
    # Arrange
    adapter = JSONOutputAdapter()
    result = ExtractionResult(...)

    # Act
    formatted_data = adapter._format_for_compatibility(result)

    # Assert
    assert "all_water_systems" in formatted_data
    assert "extraction_summary" in formatted_data
```

### Testing Ports Compliance
```python
@pytest.mark.parametrize("adapter_class", [
    JSONOutputAdapter,
    CSVOutputAdapter,
    EnhancedJSONOutputAdapter
])
def test_output_adapter_implements_port(adapter_class):
    adapter = adapter_class()

    # Verify interface compliance
    assert hasattr(adapter, 'save_data')
    assert hasattr(adapter, 'get_supported_formats')
    assert hasattr(adapter, 'validate_destination')

    # Test method signatures
    import inspect
    save_data_sig = inspect.signature(adapter.save_data)
    assert 'result' in save_data_sig.parameters
    assert 'destination' in save_data_sig.parameters
```

This test suite ensures that the SDWIS automation system maintains its hexagonal architecture integrity while providing comprehensive coverage of all functionality.
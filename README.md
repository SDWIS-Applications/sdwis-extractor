# SDWIS Extractor

Automated data extraction tool for SDWIS (Safe Drinking Water Information System) STATE. Extract water systems, legal entities, and deficiency types with 100% coverage using a modern CLI and web interface.

## Features

- **Complete Data Coverage**: Extracts all 1,903 water systems and 8,619 legal entities
- **Multiple Interfaces**: Command-line interface and Streamlit web UI
- **Multiple Export Formats**: CSV and JSON output with flexible formatting
- **Inspection Mode**: Hierarchical JSON exports for detailed analysis
- **Hexagonal Architecture**: Clean, maintainable codebase following ports and adapters pattern
- **Comprehensive Testing**: Full test suite with 100% extraction validation

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/SDWIS-Applications/sdwis-extractor.git
cd sdwis-extractor

# Install dependencies
uv add playwright
uv run playwright install

# Configure credentials
cp .env.example .env
# Edit .env with your SDWIS credentials
```

### Usage

#### Command Line Interface

```bash
# Extract water systems
uv run python -m modules.cli.main water_systems -o systems.json

# Extract legal entities
uv run python -m modules.cli.main legal_entities --format csv -o entities.csv

# Extract deficiency types
uv run python -m modules.cli.main deficiency_types -o deficiency_types.csv

# Test connection
uv run python -m modules.cli.main --check-auth
```

#### Web Interface

```bash
# Launch Streamlit web interface
uv run streamlit run modules/adapters/ui/streamlit_app.py
```

Open your browser to `http://localhost:8501` for the interactive web interface featuring:
- Real-time progress tracking
- Multiple data type selection
- Built-in connection testing
- Multiple file downloads (CSV/JSON)
- Inspection mode for detailed exports

## Configuration

### Environment Variables

```bash
# Required
SDWIS_URL=http://sdwis:8080/SDWIS/
SDWIS_USERNAME=your_username
SDWIS_PASSWORD=your_password

# Optional
BROWSER_HEADLESS=true
BROWSER_TIMEOUT=30000
DEFAULT_OUTPUT_FORMAT=csv
```

### Browser Options

```bash
# Run with visible browser (for debugging)
uv run python -m modules.cli.main water_systems --no-headless

# Run in background (default)
uv run python -m modules.cli.main water_systems
```

## Data Types

### Water Systems
Extract all 1,903 water systems with complete metadata:
- System identification and status
- Population served and county information
- Source types and federal classifications
- Complete pagination handling

### Legal Entities
Extract all 8,619 individual legal entities:
- Personal and organization information
- Status and classification codes
- State codes and unique identifiers
- Smart full-name continuation strategy

### Deficiency Types
Extract site visit deficiency codes:
- Violation categories and descriptions
- Regulatory compliance mappings
- Inspection-ready data structures

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run unit tests only
uv run pytest tests/unit/ -v

# Run without real SDWIS connection
uv run pytest -m "not real" -v
```

## Architecture

This project follows hexagonal (ports and adapters) architecture:

```
modules/
├── core/           # Domain models and business logic
├── adapters/       # External integrations
│   ├── extractors/ # SDWIS data extraction
│   ├── auth/       # Authentication handlers
│   ├── output/     # Export formats
│   └── ui/         # User interfaces
└── cli/            # Command-line interface
```

## Requirements

- Python 3.11+
- Access to SDWIS system
- Valid SDWIS credentials
- Network access to SDWIS server (typically internal)

## License

MIT License - see LICENSE file for details.

## Support

For issues and feature requests, please use the GitHub issue tracker.

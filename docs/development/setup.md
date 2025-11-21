# aipartnerupflow Development Guide

This document is for developers working on the `aipartnerupflow` project. For user documentation, see [README.md](../../README.md).

## Project Structure

See [docs/architecture/DIRECTORY_STRUCTURE.md](../architecture/DIRECTORY_STRUCTURE.md) for detailed directory structure including source code, tests, and all modules.

## Prerequisites

- **Python 3.10+** (3.12+ recommended, see note below)
- **DuckDB** (default embedded storage, no setup required)
- **PostgreSQL** (optional, for distributed/production scenarios)

> **Note**: The project uses Python 3.12 for compatibility. Python 3.13 may have compatibility issues.

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd aipartnerupflow

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2. Install Dependencies

#### Option A: Using uv (Recommended - Fastest)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project in development mode with all extras
uv pip install -e ".[all,dev]"

# OR install with specific extras
uv pip install -e ".[api,cli,dev]"  # API + CLI + dev tools
```

#### Option B: Using pip (Traditional)

```bash
# Install project in development mode with all features
pip install -e ".[all,dev]"

# OR install with specific extras
pip install -e ".[api,cli,dev]"  # API + CLI + dev tools
```

#### Option C: Using Poetry (If configured)

```bash
# Install poetry if you haven't already
curl -sSL https://install.python-poetry.org | python3 -

# Install all dependencies
poetry install --with dev
```

### 3. Environment Configuration

Create a `.env` file in the project root (optional, for API service configuration):

```env
# API Service Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Database Configuration (optional, if using PostgreSQL)
# DATABASE_URL=postgresql+asyncpg://user:password@localhost/aipartnerupflow

# DuckDB (default, no configuration needed)
# Uses embedded database, no external setup required

# Development
DEBUG=True
LOG_LEVEL=INFO
```

### 4. Verify Installation

```bash
# Check installation
python -c "import aipartnerupflow; print(aipartnerupflow.__version__)"

# Run tests to verify everything works
pytest tests/ -v
```

## Development Workflow

### Running the Project

#### Run Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_task_manager.py -v

# Run with coverage
pytest --cov=aipartnerupflow --cov-report=html tests/

# Run only unit tests (exclude integration tests)
pytest -m "not integration" tests/

# Run only integration tests
pytest -m integration tests/
```

#### Run API Server (Development)

```bash
# Method 1: Using CLI (if installed with [cli] extra)
aipartnerupflow serve start --port 8000 --reload
# Or use shorthand:
apflow serve start --port 8000 --reload

# Method 2: Using Python module directly (recommended)
python -m aipartnerupflow.api.main

# Method 3: Using entry point (if installed with [a2a] extra)
aipartnerupflow-server

# Method 4: Direct execution of serve command (for development)
python src/aipartnerupflow/cli/commands/serve.py start --port 8000 --reload
```

#### Run CLI Commands

```bash
# List available flows
aipartnerupflow list-flows

# Run a flow
aipartnerupflow run example_flow --inputs '{"key": "value"}'

# Start daemon mode
aipartnerupflow daemon start
```

### Code Quality

#### Format Code

```bash
# Format all code
black src/ tests/

# Check formatting without applying
black --check src/ tests/
```

#### Lint Code

```bash
# Run linter
ruff check src/ tests/

# Auto-fix linting issues
ruff check --fix src/ tests/
```

#### Type Checking

```bash
# Run type checker
mypy src/aipartnerupflow/

# Check specific module
mypy src/aipartnerupflow/core/interfaces/ src/aipartnerupflow/core/execution/ src/aipartnerupflow/core/storage/
```

#### Run All Checks

```bash
# Run formatting, linting, and type checking
black --check src/ tests/ && ruff check src/ tests/ && mypy src/aipartnerupflow/
```

### Database Operations

#### Default DuckDB (No Setup Required)

DuckDB is the default embedded storage. It requires no external setup - it creates database files locally.

```bash
# Test storage (creates temporary DuckDB file)
pytest tests/test_storage.py -v
```

#### PostgreSQL (Optional)

If you want to test with PostgreSQL:

```bash
# Install PostgreSQL extra
pip install -e ".[postgres]"

# Set environment variable
export DATABASE_URL="postgresql+asyncpg://user:password@localhost/aipartnerupflow"

# Run database migrations (if using Alembic)
alembic upgrade head
```

#### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

### Running Services

#### API Service

```bash
# Development mode (auto-reload)
aipartnerupflow serve --port 8000 --reload

# Production mode
aipartnerupflow serve --port 8000 --workers 4
```

#### Daemon Mode

```bash
# Start daemon
aipartnerupflow daemon start

# Stop daemon
aipartnerupflow daemon stop

# Check daemon status
aipartnerupflow daemon status
```

## Dependency Management

### Core Dependencies

Installed with `pip install aipartnerupflow` (pure orchestration framework):

- `pydantic` - Data validation
- `sqlalchemy` - ORM
- `alembic` - Database migrations
- `duckdb-engine` - Default embedded storage

**Note**: CrewAI is NOT in core dependencies - it's available via [crewai] extra.

### Optional Dependencies

#### A2A Protocol Server (`[a2a]`)

```bash
pip install -e ".[a2a]"
```

Includes:
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `a2a-sdk[http-server]` - A2A protocol support
- `httpx`, `aiohttp` - HTTP clients
- `websockets` - WebSocket support

#### CLI Tools (`[cli]`)

```bash
pip install -e ".[cli]"
```

Includes:
- `click`, `rich`, `typer` - CLI framework and utilities

#### PostgreSQL (`[postgres]`)

```bash
pip install -e ".[postgres]"
```

Includes:
- `asyncpg` - Async PostgreSQL driver
- `psycopg2-binary` - Sync PostgreSQL driver

#### CrewAI Support (`[crewai]`)

```bash
pip install -e ".[crewai]"
```

Includes:
- `crewai[tools]` - Core CrewAI orchestration engine
- `crewai-tools` - CrewAI tools
- CrewManager for LLM-based agent crews
- BatchManager for atomic batch execution of multiple crews

**Note**: BatchManager is part of [crewai] because it's specifically designed for batching CrewAI crews together.

**Note**: For examples and learning templates, see the test cases in `tests/integration/` and `tests/extensions/`. Test cases serve as comprehensive examples demonstrating real-world usage patterns.

#### Development (`[dev]`)

```bash
pip install -e ".[dev]"
```

Includes:
- `pytest`, `pytest-asyncio`, `pytest-cov` - Testing
- `black` - Code formatting
- `ruff` - Linting
- `mypy` - Type checking

### Full Installation

```bash
# Install everything
pip install -e ".[all,dev]"
```

## Testing

### Test Structure

See [docs/architecture/DIRECTORY_STRUCTURE.md](../architecture/DIRECTORY_STRUCTURE.md#test-suite-tests-) for complete test directory structure.

Test structure mirrors source code structure:
- `tests/core/` - Core framework tests
- `tests/extensions/` - Extension tests
- `tests/api/a2a/` - A2A Protocol Server tests
- `tests/cli/` - CLI tests
- `tests/integration/` - Integration tests

### Writing Tests

#### Test Fixtures

Use the provided fixtures from `conftest.py`:

```python
import pytest

@pytest.mark.asyncio
async def test_my_feature(sync_db_session, sample_task_data):
    # Use sync_db_session for database operations
    # Use sample_task_data for test data
    pass
```

#### Test Markers

```python
# Mark as integration test (requires external services)
@pytest.mark.integration
async def test_external_service():
    pass

# Mark as slow test
@pytest.mark.slow
def test_performance():
    pass

# Mark as requiring API keys
@pytest.mark.requires_api_keys
async def test_api_integration(api_keys_available):
    pass
```

### Test Coverage

```bash
# Generate coverage report
pytest --cov=aipartnerupflow --cov-report=html tests/

# View HTML report
open htmlcov/index.html  # macOS
# or
xdg-open htmlcov/index.html  # Linux
```

## Code Organization

### Module Structure

**Core Modules** (always included with `pip install aipartnerupflow`):
- **`execution/`**: Task orchestration specifications (TaskManager, StreamingCallbacks)
- **`interfaces/`**: Core interfaces (ExecutableTask, BaseTask, TaskStorage)
- **`storage/`**: Storage abstractions and implementations (DuckDB default, PostgreSQL optional)
- **`utils/`**: Utility functions

**Optional Extension Modules**:
- **`extensions/crewai/`**: CrewAI LLM task support [crewai extra]
  - `crew_manager.py`: CrewManager for LLM-based agent crews
  - `batch_manager.py`: BatchManager for atomic batch execution of multiple crews
  - `types.py`: CrewManagerState, BatchState
  - Note: BatchManager is included in [crewai] as it's specifically for batching CrewAI crews

**Learning Resources**:
- **Test cases**: Serve as examples (see `tests/integration/` and `tests/extensions/`)
  - Integration tests demonstrate real-world usage patterns
  - Extension tests show how to use specific executors
  - Test cases can be used as learning templates

**Service Modules**:
- **`api/`**: API layer (A2A server, handlers) [a2a extra]
- **`cli/`**: Command-line interface [cli extra]
**Protocol Standard**: The framework adopts **A2A (Agent-to-Agent) Protocol** as the standard protocol. See `api/` module for A2A Protocol implementation.

### Adding New Features

1. **New Custom Task**: Implement `ExecutableTask` interface (core)
2. **New CrewAI Crew**: Add to `ext/crews/` [ext extra]
3. **New Batch**: Add to `ext/batches/` [ext extra]
4. **New Storage Backend**: Add dialect to `storage/dialects/`
5. **New API Endpoint**: Add handler to `api/handlers/`
6. **New CLI Command**: Add to `cli/commands/`

### Code Style

- **Line length**: 100 characters
- **Type hints**: Use type hints for function parameters and return values
- **Docstrings**: Use Google-style docstrings
- **Imports**: Sort imports with `ruff`
- **Comments**: Write comments in English

## Debugging

### Enable Debug Logging

```python
import logging
from aipartnerupflow.utils.logger import get_logger

logger = get_logger(__name__)
logger.setLevel(logging.DEBUG)
```

### Using Debugger

```bash
# Run with Python debugger
python -m pdb -m pytest tests/test_task_manager.py::TestTaskManager::test_create_task
```

### Common Issues

#### Import Errors

```bash
# Ensure package is installed in development mode
pip install -e "."

# Check Python path
python -c "import sys; print(sys.path)"
```

#### Database Connection Issues

```bash
# For DuckDB: Check file permissions
ls -la *.duckdb

# For PostgreSQL: Verify connection string
python -c "from sqlalchemy import create_engine; engine = create_engine('YOUR_CONNECTION_STRING'); print(engine.connect())"
```

## Building and Distribution

### Build Package

```bash
# Build source distribution
python -m build

# Build wheel
python -m build --wheel
```

### Local Installation Test

```bash
# Install from local build
pip install dist/aipartnerupflow-0.2.0-py3-none-any.whl
```

## Contributing

### Development Workflow

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/my-feature
   ```
3. **Make your changes**
   - Write code
   - Add tests
   - Update documentation
4. **Run quality checks**
   ```bash
   black src/ tests/
   ruff check --fix src/ tests/
   mypy src/aipartnerupflow/
   pytest tests/
   ```
5. **Commit changes**
   ```bash
   git commit -m "feat: Add my feature"
   ```
6. **Push and create PR**
   ```bash
   git push origin feature/my-feature
   ```

### Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting)
- `refactor:` - Code refactoring
- `test:` - Test changes
- `chore:` - Maintenance tasks

### Pull Request Checklist

- [ ] Code follows project style guidelines
- [ ] Tests pass (`pytest tests/`)
- [ ] Code is formatted (`black src/ tests/`)
- [ ] No linting errors (`ruff check src/ tests/`)
- [ ] Type checking passes (`mypy src/aipartnerupflow/`)
- [ ] Documentation updated (if needed)
- [ ] CHANGELOG.md updated (if needed)

## Resources

- **User Documentation**: [README.md](../../README.md)
- **Changelog**: [CHANGELOG.md](../../CHANGELOG.md)
- **Website**: [aipartnerup.com](https://aipartnerup.com)
- **Issue Tracker**: [GitHub Issues](https://github.com/aipartnerup/aipartnerupflow/issues)

## Getting Help

- **Questions**: Open a GitHub issue
- **Bugs**: Report via GitHub issues
- **Feature Requests**: Open a GitHub discussion
- **Documentation**: Check [docs/](docs/) directory

## License

Apache-2.0 - See [LICENSE](LICENSE) file for details.


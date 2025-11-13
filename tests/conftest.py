"""
Test configuration and fixtures for aipartnerupflow
"""
import pytest
import pytest_asyncio
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from typing import AsyncGenerator, Generator

# Add project root to Python path for development
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Add src directory to path for imports
src_path = os.path.join(project_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Auto-discover built-in extensions for tests
# This ensures extensions are registered before tests run
# Must be imported before other modules that use the registry
try:
    from aipartnerupflow.extensions.stdio import SystemInfoExecutor, CommandExecutor  # noqa: F401
except ImportError:
    pass  # Extension not available, tests will handle this

try:
    from aipartnerupflow.extensions.crewai import CrewManager  # noqa: F401
except ImportError:
    pass  # Extension not available, tests will handle this

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from aipartnerupflow.core.storage.sqlalchemy.models import Base, TaskModel, TASK_TABLE_NAME
from aipartnerupflow.core.storage.factory import create_session, get_default_session, reset_default_session
# Backward compatibility aliases
create_storage = create_session
get_default_storage = get_default_session


# Custom pytest markers
def pytest_configure(config):
    """Configure custom pytest markers"""
    config.addinivalue_line(
        "markers", "requires_api_keys: mark test as requiring API keys"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test that requires external services"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow"
    )


@pytest.fixture(scope="function")
def temp_db_path():
    """Create a temporary database file path"""
    fd, db_path = tempfile.mkstemp(suffix=".duckdb")
    os.close(fd)  # Close file descriptor, we just need the path
    
    yield db_path
    
    # Cleanup - ensure file is removed even if test fails
    try:
        if os.path.exists(db_path):
            os.unlink(db_path)
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture(scope="function")
def sync_db_session(temp_db_path):
    """
    Create a synchronous database session for testing
    
    Each test gets a fresh database session with automatic cleanup:
    - Tables are created fresh for each test
    - Data is cleaned up after each test to ensure test isolation
    """
    # Ensure file doesn't exist (cleanup from previous failed test)
    if os.path.exists(temp_db_path):
        try:
            os.unlink(temp_db_path)
        except Exception:
            pass
    
    # Create engine with DuckDB
    engine = create_engine(
        f"duckdb:///{temp_db_path}",
        echo=False
    )
    
    # Create tables fresh for each test
    Base.metadata.create_all(engine)
    
    # Create session
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    try:
        yield session
    finally:
        # Cleanup: Rollback any pending transactions
        try:
            session.rollback()
        except Exception:
            pass
        
        # Cleanup: Delete all data from tables to ensure test isolation
        try:
            # Delete all tasks to ensure test isolation
            # Note: Using TASK_TABLE_NAME constant for table name
            session.execute(text(f"DELETE FROM {TASK_TABLE_NAME}"))
            session.commit()
        except Exception:
            session.rollback()
        
        # Close session and dispose engine
        session.close()
        engine.dispose()
        
        # Remove database file
        try:
            if os.path.exists(temp_db_path):
                os.unlink(temp_db_path)
        except Exception:
            pass  # Ignore cleanup errors


@pytest_asyncio.fixture(scope="function")
async def async_db_session(temp_db_path):
    """
    Create a mock AsyncSession for testing is_async detection
    
    Note: DuckDB doesn't support async drivers, so SQLAlchemy won't allow
    creating AsyncEngine with DuckDB. This fixture creates a mock AsyncSession
    that properly implements isinstance checks for testing TaskManager's is_async logic.
    
    In production, PostgreSQL with asyncpg provides true async operations.
    The is_async detection is sufficient for the codebase since TaskManager
    uses isinstance(db, AsyncSession) to determine async mode.
    """
    from unittest.mock import AsyncMock, MagicMock
    from sqlalchemy.ext.asyncio import AsyncSession
    
    # Create a mock that will pass isinstance checks
    # We subclass MagicMock and set __class__ to make isinstance work
    class MockAsyncSession(AsyncSession):
        """Mock AsyncSession that passes isinstance checks"""
        def __init__(self):
            # Don't call super().__init__() to avoid requiring real engine
            pass
    
    # Create instance and configure mock methods
    mock_session = MockAsyncSession()
    mock_session.commit = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.get = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.query = MagicMock()
    mock_session.bind = None
    
    yield mock_session
    
    # Cleanup
    try:
        await mock_session.close()
    except Exception:
        pass


@pytest.fixture(scope="function")
def mock_storage():
    """Create a mock storage instance"""
    storage = Mock()
    storage.save_task = AsyncMock(return_value=True)
    storage.get_task = AsyncMock(return_value=None)
    storage.update_task_status = AsyncMock(return_value=True)
    storage.list_tasks = AsyncMock(return_value=[])
    storage.delete_task = AsyncMock(return_value=True)
    storage.close = AsyncMock()
    return storage


@pytest.fixture(scope="function")
def sample_task_data():
    """Sample task data for testing"""
    return {
        "id": "test-task-1",
        "parent_id": None,
        "user_id": "test-user-123",
        "name": "Test Task",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "progress": 0.0,
        "input_data": {"url": "https://example.com"},
        "params": {},
        "schemas": {
            "type": "crew",
            "method": "web_analyzer",
            "input_schema": {
                "properties": {
                    "url": {"type": "string", "required": True}
                }
            }
        },
        "result": None,
        "error": None
    }


@pytest.fixture(scope="function")
def sample_task_tree_data():
    """Sample task tree data for testing"""
    return {
        "tasks": [
            {
                "id": "root-task",
                "parent_id": None,
                "user_id": "test-user-123",
                "name": "Root Task",
                "status": "pending",
                "priority": 3,
                "has_children": True,
                "dependencies": [
                    {"id": "child-1", "required": True},
                    {"id": "child-2", "required": True}
                ],
                "schemas": {
                    "type": "local",
                    "method": "aggregate_task_results"
                }
            },
            {
                "id": "child-1",
                "parent_id": "root-task",
                "user_id": "test-user-123",
                "name": "Child Task 1",
                "status": "pending",
                "priority": 1,
                "has_children": False,
                "dependencies": [],
                "schemas": {
                    "type": "crew",
                    "method": "web_analyzer",
                    "input_schema": {
                        "properties": {
                            "url": {"type": "string", "required": True}
                        }
                    }
                },
                "input_data": {"url": "https://example.com"}
            },
            {
                "id": "child-2",
                "parent_id": "root-task",
                "user_id": "test-user-123",
                "name": "Child Task 2",
                "status": "pending",
                "priority": 1,
                "has_children": False,
                "dependencies": [
                    {"id": "child-1", "required": True}
                ],
                "schemas": {
                    "type": "flow",
                    "method": "ai_presence_analyzer",
                    "input_schema": {
                        "properties": {
                            "url": {"type": "string", "required": True}
                        }
                    }
                },
                "input_data": {"url": "https://example.com"}
            }
        ]
    }


@pytest.fixture(autouse=True)
def reset_storage_singleton():
    """Reset storage singleton before each test"""
    reset_default_session()
    yield
    reset_default_session()


@pytest.fixture(autouse=True)
def mock_logger():
    """Mock logger for testing"""
    with patch('aipartnerupflow.core.utils.logger.get_logger') as mock_logger:
        logger = Mock()
        logger.info = Mock()
        logger.debug = Mock()
        logger.warning = Mock()
        logger.error = Mock()
        mock_logger.return_value = logger
        yield logger


@pytest.fixture
def api_keys_available():
    """Check if required API keys are available for integration tests"""
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not openai_key:
        pytest.skip("OPENAI_API_KEY is not set - skipping integration test")
    
    return {
        "openai_api_key": openai_key
    }


def requires_api_keys(func):
    """Decorator to mark tests that require API keys"""
    return pytest.mark.requires_api_keys(pytest.mark.asyncio(func))


def integration_test(func):
    """Decorator to mark integration tests that require external services"""
    return pytest.mark.integration(pytest.mark.requires_api_keys(pytest.mark.asyncio(func)))


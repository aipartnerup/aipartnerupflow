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
from typing import AsyncGenerator, Generator, Optional

# Add project root to Python path for development
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Add src directory to path for imports
src_path = os.path.join(project_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed

# Auto-discover built-in extensions for tests
# This ensures extensions are registered before tests run
# Must be imported before other modules that use the registry
try:
    from aipartnerupflow.extensions.stdio import SystemInfoExecutor, CommandExecutor  # noqa: F401
except ImportError:
    pass  # Extension not available, tests will handle this

try:
    from aipartnerupflow.extensions.crewai import CrewManager, BatchManager  # noqa: F401
except ImportError:
    pass  # Extension not available, tests will handle this

try:
    from aipartnerupflow.extensions.core import AggregateResultsExecutor  # noqa: F401
except ImportError:
    pass  # Extension not available, tests will handle this

try:
    from aipartnerupflow.extensions.generate import GenerateExecutor  # noqa: F401
except ImportError:
    pass  # Extension not available, tests will handle this

try:
    from aipartnerupflow.extensions.llm import LLMExecutor  # noqa: F401
except ImportError:
    pass  # Extension not available, tests will handle this

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from aipartnerupflow.core.storage.sqlalchemy.models import Base, TaskModel, TASK_TABLE_NAME
from aipartnerupflow.core.storage.factory import (
    create_session,
    get_default_session,
    reset_default_session,
    set_default_session,
    is_postgresql_url,
    normalize_postgresql_url,
)
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

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
    config.addinivalue_line("markers", "manual: mark test file as manual only (skip by default)")

    # Disable CrewAI execution traces prompt in tests
    # This prevents the interactive "Would you like to view your execution traces?" prompt
    # that appears when CrewAI executes crews, which would cause tests to hang
    os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")


def _get_test_database_url() -> Optional[str]:
    """Get test database URL from environment variable"""
    return os.getenv("TEST_DATABASE_URL")


@pytest.fixture(scope="function")
def temp_db_path():
    """Create a temporary database file path (only used for DuckDB)"""
    test_db_url = _get_test_database_url()
    
    # If using PostgreSQL, don't create temp file
    if test_db_url and is_postgresql_url(test_db_url):
        logger.info("Using PostgreSQL database for testing")
        yield None
        return
    
    # Create temporary DuckDB file
    logger.info("Creating temporary DuckDB file for testing")
    fd, db_path = tempfile.mkstemp(suffix=".duckdb")
    os.close(fd)  # Close file descriptor, we just need the path
    
    yield db_path
    
    # Cleanup - ensure file is removed even if test fails
    try:
        if db_path and os.path.exists(db_path):
            os.unlink(db_path)
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture(scope="function")
def sync_db_session(temp_db_path):
    """
    Create a synchronous database session for testing
    
    Supports both DuckDB (default) and PostgreSQL (via TEST_DATABASE_URL).
    Each test gets a fresh database session with automatic cleanup:
    - Tables are created fresh for each test
    - Data is cleaned up after each test to ensure test isolation
    """
    test_db_url = _get_test_database_url()
    
    # Use PostgreSQL if TEST_DATABASE_URL is set and is PostgreSQL
    if test_db_url and is_postgresql_url(test_db_url):
        logger.info(f"Using PostgreSQL database for testing: {test_db_url}")
        # Normalize connection string for sync mode
        connection_string = normalize_postgresql_url(test_db_url, async_mode=False)
        
        # Create engine with PostgreSQL
        engine = create_engine(connection_string, echo=False)
        
        # For PostgreSQL, we need to drop and recreate tables to ensure schema matches
        # PostgreSQL is a shared database, so previous tests may have created tables
        # with custom fields (e.g., priority_level from custom TaskModel tests)
        # Note: This is necessary for PostgreSQL but not for DuckDB (which uses new files each time)
        try:
            Base.metadata.drop_all(engine)
        except Exception as e:
            logger.warning(f"Error dropping tables (may not exist): {e}")
        
        # Create tables fresh for each test
        Base.metadata.create_all(engine)
        
        # Create session
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        try:
            yield session
        finally:
            # Cleanup: Rollback any pending transactions first
            try:
                session.rollback()
            except Exception:
                pass
            
            # Cleanup: Delete all data from tables to ensure test isolation
            # Use a new transaction to avoid InFailedSqlTransaction errors
            try:
                # Start a new transaction for cleanup
                session.begin()
                session.execute(text(f"DELETE FROM {TASK_TABLE_NAME}"))
                session.commit()
            except Exception as e:
                # If cleanup fails, rollback and try to continue
                try:
                    session.rollback()
                except Exception:
                    pass
                logger.debug(f"Cleanup failed (non-critical): {e}")
            
            # Close session and dispose engine
            try:
                session.close()
            except Exception:
                pass
            try:
                engine.dispose()
            except Exception:
                pass
    else:
        # Use DuckDB (default behavior)
        logger.info(f"Using DuckDB database for testing: {temp_db_path}")
        # Ensure file doesn't exist (cleanup from previous failed test)
        if temp_db_path and os.path.exists(temp_db_path):
            try:
                os.unlink(temp_db_path)
            except Exception:
                pass
        
        # Create engine with DuckDB
        engine = create_engine(
            f"duckdb:///{temp_db_path}",
            echo=False
        )
        
        # For DuckDB, we don't need to drop tables because each test uses a new file
        # The file is deleted after each test, so schema is always fresh
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
                if temp_db_path and os.path.exists(temp_db_path):
                    os.unlink(temp_db_path)
            except Exception:
                pass  # Ignore cleanup errors


@pytest_asyncio.fixture(scope="function")
async def async_db_session(temp_db_path):
    """
    Create an async database session for testing
    
    Supports both DuckDB (mock) and PostgreSQL (real async session via TEST_DATABASE_URL).
    
    Note: DuckDB doesn't support async drivers, so SQLAlchemy won't allow
    creating AsyncEngine with DuckDB. When using DuckDB, this fixture creates a mock AsyncSession
    that properly implements isinstance checks for testing TaskManager's is_async logic.
    
    When TEST_DATABASE_URL is set to PostgreSQL, this fixture creates a real AsyncSession
    with asyncpg driver, providing true async operations.
    """
    test_db_url = _get_test_database_url()
    
    # Use PostgreSQL if TEST_DATABASE_URL is set and is PostgreSQL
    if test_db_url and is_postgresql_url(test_db_url):
        logger.info(f"Using PostgreSQL database for async testing: {test_db_url}")
        # Normalize connection string for async mode
        connection_string = normalize_postgresql_url(test_db_url, async_mode=True)
        
        # Create async engine with PostgreSQL
        engine = create_async_engine(connection_string, echo=False)
        
        # For PostgreSQL async, we need to drop and recreate tables to ensure schema matches
        # PostgreSQL is a shared database, so previous tests may have created tables
        # with custom fields (e.g., priority_level from custom TaskModel tests)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
        except Exception as e:
            logger.warning(f"Error dropping tables (may not exist): {e}")
        
        # Create tables fresh for each test
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Create async session
        SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        session = SessionLocal()
        
        try:
            yield session
        finally:
            # Cleanup: Rollback any pending transactions first
            try:
                await session.rollback()
            except Exception:
                pass
            
            # Cleanup: Delete all data from tables to ensure test isolation
            # Use a new transaction to avoid InFailedSqlTransaction errors
            try:
                # Start a new transaction for cleanup
                await session.begin()
                await session.execute(text(f"DELETE FROM {TASK_TABLE_NAME}"))
                await session.commit()
            except Exception as e:
                # If cleanup fails, rollback and try to continue
                try:
                    await session.rollback()
                except Exception:
                    pass
                logger.debug(f"Cleanup failed (non-critical): {e}")
            
            # Close session and dispose engine
            try:
                await session.close()
            except Exception:
                pass
            try:
                await engine.dispose()
            except Exception:
                pass
    else:
        # Use mock AsyncSession for DuckDB (DuckDB doesn't support async)
        logger.info("Using mock AsyncSession for DuckDB (DuckDB doesn't support async drivers)")
        from unittest.mock import AsyncMock, MagicMock
        
        # Note: AsyncSession is already imported at module level, don't re-import here
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
        "inputs": {"url": "https://example.com"},
        "params": {},
        "schemas": {
            "method": "crewai_executor",
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
                    "method": "aggregate_results_executor"
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
                    "method": "crewai_executor",
                    "input_schema": {
                        "properties": {
                            "url": {"type": "string", "required": True}
                        }
                    }
                },
                "inputs": {"url": "https://example.com"}
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
                    "method": "crewai_executor",
                    "input_schema": {
                        "properties": {
                            "url": {"type": "string", "required": True}
                        }
                    }
                },
                "inputs": {"url": "https://example.com"}
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
def ensure_executors_registered():
    """
    Ensure all required executors are registered before each test
    
    This fixture ensures that executors are registered even if previous tests
    cleared the ExtensionRegistry. This is necessary because ExtensionRegistry
    is a singleton and some tests (like test_main.py) clear it in setup_method.
    
    The fixture explicitly re-registers executors using override=True to ensure
    they are available even if registry was cleared by previous tests.
    """
    from aipartnerupflow.core.extensions import get_registry
    from aipartnerupflow.core.extensions.types import ExtensionCategory
    
    registry = get_registry()
    
    # Helper function to register executor if not already registered
    def ensure_registered(executor_class, executor_id: str):
        """Register executor if not already registered"""
        if not registry.is_registered(executor_id):
            try:
                # Try to create a template instance
                try:
                    template = executor_class(inputs={})
                except Exception:
                    # If instantiation fails, create minimal template
                    class TemplateClass(executor_class):
                        def __init__(self):
                            pass
                    template = TemplateClass()
                    template.id = getattr(executor_class, 'id', executor_id)
                    template.name = getattr(executor_class, 'name', executor_class.__name__)
                    template.description = getattr(executor_class, 'description', '')
                    template.category = ExtensionCategory.EXECUTOR
                    template.type = getattr(executor_class, 'type', 'default')
                
                # Register with override=True to force re-registration
                registry.register(
                    extension=template,
                    executor_class=executor_class,
                    override=True
                )
            except Exception:
                # Ignore registration errors - some executors may not be available
                pass
    
    # Ensure all required executors are registered
    try:
        from aipartnerupflow.extensions.stdio import SystemInfoExecutor, CommandExecutor
        ensure_registered(SystemInfoExecutor, "system_info_executor")
        ensure_registered(CommandExecutor, "command_executor")
    except ImportError:
        pass
    
    try:
        from aipartnerupflow.extensions.crewai import CrewManager, BatchManager
        ensure_registered(CrewManager, "crewai_executor")
        ensure_registered(BatchManager, "batch_crewai_executor")
    except ImportError:
        pass
    
    try:
        from aipartnerupflow.extensions.core import AggregateResultsExecutor
        ensure_registered(AggregateResultsExecutor, "aggregate_results_executor")
    except ImportError:
        pass
    
    try:
        from aipartnerupflow.extensions.generate import GenerateExecutor
        ensure_registered(GenerateExecutor, "generate_executor")
    except ImportError:
        pass
    
    try:
        from aipartnerupflow.extensions.llm import LLMExecutor
        ensure_registered(LLMExecutor, "llm_executor")
    except ImportError:
        pass
    
    yield
    
    # No cleanup needed - registry state persists between tests
    # (which is the desired behavior for most tests)


@pytest.fixture(scope="function")
def use_test_db_session(sync_db_session):
    """
    Fixture to set and reset default session for tests - uses in-memory database
    
    This fixture ensures that all tests use a temporary in-memory database
    instead of the persistent database file, preventing data pollution.
    
    Usage:
        - Add `use_test_db_session` parameter to your test function
        - The fixture will automatically set the default session to the test database
        - After the test, it will reset the default session
    
    Example:
        async def test_something(self, use_test_db_session):
            # get_default_session() will return the test database session
            session = get_default_session()
            ...
    """
    set_default_session(sync_db_session)
    
    # Patch create_pooled_session to return the test session
    # This ensures that code using create_pooled_session() gets the test session
    from contextlib import asynccontextmanager
    
    @asynccontextmanager
    async def mock_create_pooled_session(*args, **kwargs):
        yield sync_db_session
        
    # Patch both the factory function and the import in routes and executor
    with patch('aipartnerupflow.core.storage.factory.create_pooled_session', side_effect=mock_create_pooled_session), \
         patch('aipartnerupflow.api.routes.tasks.create_pooled_session', side_effect=mock_create_pooled_session), \
         patch('aipartnerupflow.core.execution.task_executor.create_pooled_session', side_effect=mock_create_pooled_session):
        yield sync_db_session
        
    reset_default_session()


@pytest.fixture(scope="function")
def fresh_db_session(temp_db_path):
    """
    Create a fresh database session with tables dropped and recreated
    
    This fixture is specifically for tests that need custom TaskModel with additional fields.
    It drops and recreates tables to ensure schema matches the current TaskModel.
    
    Performance note: This fixture has higher overhead than sync_db_session because it
    drops and recreates tables. Only use this fixture when you need to test custom TaskModel
    or when schema changes are required.
    
    Usage:
        - Use this fixture instead of sync_db_session when testing custom TaskModel
        - Example: def test_custom_model(self, fresh_db_session):
    """
    test_db_url = _get_test_database_url()
    
    # Use PostgreSQL if TEST_DATABASE_URL is set and is PostgreSQL
    if test_db_url and is_postgresql_url(test_db_url):
        logger.info(f"Using PostgreSQL database with fresh tables: {test_db_url}")
        connection_string = normalize_postgresql_url(test_db_url, async_mode=False)
        engine = create_engine(connection_string, echo=False)
        
        # Drop and recreate tables to ensure schema matches
        try:
            Base.metadata.drop_all(engine)
        except Exception as e:
            logger.warning(f"Error dropping tables (may not exist): {e}")
        
        Base.metadata.create_all(engine)
        
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        try:
            yield session
        finally:
            try:
                session.rollback()
            except Exception:
                pass
            
            try:
                session.begin()
                session.execute(text(f"DELETE FROM {TASK_TABLE_NAME}"))
                session.commit()
            except Exception as e:
                try:
                    session.rollback()
                except Exception:
                    pass
                logger.debug(f"Cleanup failed (non-critical): {e}")
            
            try:
                session.close()
            except Exception:
                pass
            try:
                engine.dispose()
            except Exception:
                pass
    else:
        # Use DuckDB (default behavior)
        logger.info(f"Using DuckDB database with fresh tables: {temp_db_path}")
        if temp_db_path and os.path.exists(temp_db_path):
            try:
                os.unlink(temp_db_path)
            except Exception:
                pass
        
        engine = create_engine(
            f"duckdb:///{temp_db_path}",
            echo=False
        )
        
        # Drop and recreate tables to ensure schema matches
        try:
            Base.metadata.drop_all(engine)
        except Exception as e:
            logger.warning(f"Error dropping tables (may not exist): {e}")
        
        Base.metadata.create_all(engine)
        
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        try:
            yield session
        finally:
            try:
                session.rollback()
            except Exception:
                pass
            
            try:
                session.execute(text(f"DELETE FROM {TASK_TABLE_NAME}"))
                session.commit()
            except Exception:
                session.rollback()
            
            session.close()
            engine.dispose()
            
            try:
                if temp_db_path and os.path.exists(temp_db_path):
                    os.unlink(temp_db_path)
            except Exception:
                pass


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


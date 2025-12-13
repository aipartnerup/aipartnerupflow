"""
Database session factory for creating database sessions
"""

from typing import Optional, Union
from pathlib import Path
import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
from aipartnerupflow.core.storage.sqlalchemy.models import Base
from aipartnerupflow.core.storage.dialects.registry import get_dialect_config
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

# Global default session instance (lazy loading)
_default_session: Optional[Union[Session, AsyncSession]] = None


def is_postgresql_url(url: str) -> bool:
    """
    Check if connection string is PostgreSQL
    
    Args:
        url: Database connection string
    
    Returns:
        True if the URL is PostgreSQL, False otherwise
    """
    return url.startswith("postgresql://") or url.startswith("postgresql+")


def normalize_postgresql_url(url: str, async_mode: bool) -> str:
    """
    Normalize PostgreSQL connection string to use appropriate driver
    
    Args:
        url: PostgreSQL connection string
        async_mode: Whether to use async driver (asyncpg) or sync (psycopg2)
    
    Returns:
        Normalized connection string
    """
    # If already has driver specified, use as-is
    if "+" in url.split("://")[0]:
        return url
    
    # Extract scheme and rest
    if url.startswith("postgresql://"):
        rest = url[13:]  # Remove "postgresql://"
    else:
        rest = url.split("://", 1)[1] if "://" in url else url
    
    # Add appropriate driver
    if async_mode:
        return f"postgresql+asyncpg://{rest}"
    else:
        return f"postgresql+psycopg2://{rest}"


def _get_database_url_from_env() -> Optional[str]:
    """
    Get database URL from environment variables
    
    Checks DATABASE_URL first, then AIPARTNERUPFLOW_DATABASE_URL
    
    Returns:
        Database URL string or None if not set
    """
    # Check DATABASE_URL first (standard convention)
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url
    
    # Check AIPARTNERUPFLOW_DATABASE_URL (project-specific)
    db_url = os.getenv("AIPARTNERUPFLOW_DATABASE_URL")
    if db_url:
        return db_url
    
    return None


def _get_default_db_path() -> str:
    """
    Get default database path.
    If examples module is available, use persistent database.
    Otherwise, use in-memory database.
    
    Returns:
        Database path string
    """
    # Check environment variable first
    env_path = os.getenv("AIPARTNERUPFLOW_DB_PATH")
    if env_path:
        return env_path
    
    # Examples module has been removed, use persistent database by default
    # Default location: ~/.aipartnerup/data/aipartnerupflow.duckdb
    home_dir = Path.home()
    data_dir = home_dir / ".aipartnerup" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = str(data_dir / "aipartnerupflow.duckdb")
    logger.debug(f"Using persistent database: {db_path}")
    return db_path


def create_session(
    connection_string: Optional[str] = None,
    path: Optional[Union[str, Path]] = None,
    async_mode: Optional[bool] = None,
    **kwargs
) -> Union[Session, AsyncSession]:
    """
    Create database session
    
    This function automatically detects the database type from the connection string.
    If connection_string is provided, it will be used directly (supports PostgreSQL with SSL).
    If connection_string is None, it defaults to DuckDB.
    
    Args:
        connection_string: Full database connection string. Examples:
            - PostgreSQL: "postgresql://user:password@host:port/dbname" (automatically converted to postgresql+asyncpg:// for async mode)
            - PostgreSQL: "postgresql+asyncpg://user:password@host:port/dbname?sslmode=require"
            - PostgreSQL with SSL cert: "postgresql+asyncpg://user:password@host:port/dbname?sslrootcert=/path/to/cert"
            - DuckDB: "duckdb:///path/to/file.duckdb" or "duckdb:///:memory:"
            If None, defaults to DuckDB using path parameter
            Note: For PostgreSQL, if connection_string is "postgresql://..." (without driver),
                  it will be automatically normalized to "postgresql+asyncpg://..." for async mode
                  or "postgresql+psycopg2://..." for sync mode.
        path: Database file path (DuckDB only, used when connection_string is None)
            - If None and connection_string is None: uses default persistent path
            - If ":memory:": uses in-memory database
            - Otherwise: uses file path
        async_mode: Whether to use async mode. If None:
            - For PostgreSQL: defaults to True (async mode)
            - For DuckDB: defaults to False (sync mode, DuckDB doesn't support async drivers)
        **kwargs: Additional engine parameters (e.g., pool_size, pool_pre_ping)
    
    Returns:
        Database session (Session or AsyncSession)
    
    Examples:
        # Default DuckDB (persistent file)
        session = create_session()
        
        # DuckDB in-memory
        session = create_session(path=":memory:")
        
        # DuckDB file
        session = create_session(path="./data/agentflow.duckdb")
        
        # PostgreSQL with connection string (recommended for library usage)
        # Note: "postgresql://" is automatically converted to "postgresql+asyncpg://" for async mode
        session = create_session(
            connection_string="postgresql://user:password@localhost/dbname"
        )
        
        # PostgreSQL with explicit driver
        session = create_session(
            connection_string="postgresql+asyncpg://user:password@localhost/dbname"
        )
        
        # PostgreSQL with SSL (auto-converted)
        session = create_session(
            connection_string="postgresql://user:password@host:port/dbname?sslmode=require"
        )
        
        # PostgreSQL with SSL certificate (auto-converted)
        session = create_session(
            connection_string="postgresql://user:password@host:port/dbname?sslrootcert=/path/to/ca.crt"
        )
    """
    # Determine dialect and connection string
    if connection_string is not None:
        # Connection string provided - detect dialect from connection string
        if is_postgresql_url(connection_string):
            dialect = "postgresql"
            # For PostgreSQL, default to async mode if not specified
            if async_mode is None:
                async_mode = True
            # Normalize PostgreSQL URL to use appropriate driver
            connection_string = normalize_postgresql_url(connection_string, async_mode)
        elif connection_string.startswith("duckdb://"):
            dialect = "duckdb"
            # For DuckDB, default to sync mode if not specified
            if async_mode is None:
                async_mode = False
            # Extract path from duckdb:// URL
            path = connection_string.replace("duckdb:///", "").replace("duckdb://", "")
            if path == "" or path == ":memory:":
                path = ":memory:"
            else:
                path = str(Path(path).absolute())
        else:
            raise ValueError(
                f"Unsupported connection string format: {connection_string}. "
                f"Supported formats: postgresql://..., postgresql+asyncpg://..., duckdb://..."
            )
    else:
        # No connection string - use DuckDB with path
        dialect = "duckdb"
        if async_mode is None:
            async_mode = False
        if path is None:
            path = _get_default_db_path()
        elif path != ":memory:":
            path = str(Path(path).absolute())
    
    try:
        dialect_config = get_dialect_config(dialect)
    except ValueError:
        # If PostgreSQL not installed, fallback to DuckDB
        if dialect == "postgresql":
            logger.warning(
                "PostgreSQL not available (install with [postgres] extra), "
                "falling back to DuckDB"
            )
            dialect = "duckdb"
            dialect_config = get_dialect_config(dialect)
            if path is None:
                path = _get_default_db_path()
            connection_string = dialect_config.get_connection_string(path=path)
            async_mode = False
        else:
            raise
    
    # Generate connection string if not provided
    if connection_string is None:
        if dialect == "duckdb":
            connection_string = dialect_config.get_connection_string(path=path)
        else:
            # This should not happen, but handle it gracefully
            raise ValueError("Connection string is required for PostgreSQL")
    
    # Get engine kwargs from dialect config and merge with user-provided kwargs
    engine_kwargs = dialect_config.get_engine_kwargs()
    engine_kwargs.update(kwargs)
    
    # Create engine and session
    if async_mode:
        engine = create_async_engine(connection_string, **engine_kwargs)
        session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        session = session_maker()
    else:
        engine = create_engine(connection_string, **engine_kwargs)
        session_maker = sessionmaker(engine, class_=Session, expire_on_commit=False)
        session = session_maker()
    
    logger.info(f"Created {dialect} session")
    
    # Ensure tables exist
    if engine:
        try:
            if async_mode:
                # For async, create tables using async context
                # We need to use asyncio.run() since this is a sync function
                import asyncio
                async def create_tables_async():
                    async with engine.begin() as conn:
                        await conn.run_sync(Base.metadata.create_all)
                # Check if we're already in an event loop
                try:
                    loop = asyncio.get_running_loop()
                    # If we're in an event loop, we can't use asyncio.run()
                    # In this case, we'll skip table creation here and let it happen later
                    # when the async session is actually used (e.g., in main.py)
                    logger.debug("Skipping async table creation (already in event loop, will be created in main.py)")
                except RuntimeError:
                    # No event loop running, we can use asyncio.run()
                    try:
                        asyncio.run(create_tables_async())
                    except Exception as e:
                        logger.warning(f"Could not create tables automatically (async): {str(e)}")
            else:
                Base.metadata.create_all(engine)
        except Exception as e:
            logger.warning(f"Could not create tables automatically: {str(e)}")
    
    return session


def get_default_session(
    connection_string: Optional[str] = None,
    path: Optional[Union[str, Path]] = None,
    async_mode: Optional[bool] = None,
    **kwargs
) -> Union[Session, AsyncSession]:
    """
    Get default database session (singleton)
    
    Supports both DuckDB (default) and PostgreSQL (via connection_string or DATABASE_URL environment variable).
    
    This function is designed for library usage - external projects can call this to set up database connection.
    
    Args:
        connection_string: Full database connection string. If provided, uses it directly.
            If None, checks DATABASE_URL or AIPARTNERUPFLOW_DATABASE_URL environment variable.
            Examples:
            - PostgreSQL: "postgresql://user:password@host:port/dbname" (automatically converted to postgresql+asyncpg:// for async mode)
            - PostgreSQL: "postgresql+asyncpg://user:password@host:port/dbname?sslmode=require"
            - DuckDB: "duckdb:///path/to/file.duckdb"
            Note: For PostgreSQL, if connection_string is "postgresql://..." (without driver),
                  it will be automatically normalized to "postgresql+asyncpg://..." for async mode
                  or "postgresql+psycopg2://..." for sync mode.
        path: Database file path (DuckDB only, used when connection_string is None).
            If None:
              - Checks DATABASE_URL or AIPARTNERUPFLOW_DATABASE_URL environment variable first
              - If PostgreSQL URL, uses PostgreSQL
              - Otherwise, uses AIPARTNERUPFLOW_DB_PATH if set
              - Otherwise, uses persistent database at ~/.aipartnerup/data/aipartnerupflow.duckdb
        async_mode: Whether to use async mode. If None:
                   - For PostgreSQL: defaults to True (async mode)
                   - For DuckDB: defaults to False (sync mode, since DuckDB doesn't support async drivers)
        **kwargs: Additional engine parameters
    
    Returns:
        Default database session
    
    Examples:
        # Use environment variable DATABASE_URL
        session = get_default_session()
        
        # Programmatically set PostgreSQL connection (for library usage)
        session = get_default_session(
            connection_string="postgresql+asyncpg://user:password@localhost/dbname"
        )
        
        # Programmatically set PostgreSQL with SSL
        session = get_default_session(
            connection_string="postgresql+asyncpg://user:password@host:port/dbname?sslmode=require&sslrootcert=/path/to/ca.crt"
        )
        
        # Use DuckDB file
        session = get_default_session(path="./data/app.duckdb")
    """
    global _default_session
    
    if _default_session is None:
        # If connection_string not provided, check environment variable
        if connection_string is None:
            connection_string = _get_database_url_from_env()
        
        _default_session = create_session(
            connection_string=connection_string,
            path=path,
            async_mode=async_mode,
            **kwargs
        )
    
    return _default_session


def set_default_session(session: Union[Session, AsyncSession]):
    """
    Set default session (for testing or library usage)
    
    This function allows external projects to set a custom database session.
    Useful for testing or when you need to use a pre-configured session.
    
    Args:
        session: Session to set as default
    
    Examples:
        # For library usage - set a custom session
        from aipartnerupflow.core.storage.factory import set_default_session, create_session
        
        session = create_session(
            connection_string="postgresql+asyncpg://user:password@localhost/dbname"
        )
        set_default_session(session)
    """
    global _default_session
    _default_session = session


def reset_default_session():
    """
    Reset default session (for testing or reconfiguration)
    
    This function allows external projects to reset the default session,
    useful when you need to reconfigure the database connection.
    
    Examples:
        # Reset and reconfigure
        from aipartnerupflow.core.storage.factory import reset_default_session, get_default_session
        
        reset_default_session()
        session = get_default_session(
            connection_string="postgresql+asyncpg://user:password@localhost/dbname"
        )
    """
    global _default_session
    if _default_session:
        if isinstance(_default_session, AsyncSession):
            # Note: close() is async, but this is for testing only
            pass
        else:
            _default_session.close()
    _default_session = None


def configure_database(
    connection_string: Optional[str] = None,
    path: Optional[Union[str, Path]] = None,
    async_mode: Optional[bool] = None,
    **kwargs
) -> Union[Session, AsyncSession]:
    """
    Configure and get default database session (convenience function for library usage)
    
    This is a convenience function for external projects to configure the database connection.
    It resets any existing session and creates a new one with the provided configuration.
    
    Args:
        connection_string: Full database connection string. Examples:
            - PostgreSQL: "postgresql+asyncpg://user:password@host:port/dbname"
            - PostgreSQL with SSL: "postgresql+asyncpg://user:password@host:port/dbname?sslmode=require"
            - PostgreSQL with SSL cert: "postgresql+asyncpg://user:password@host:port/dbname?sslrootcert=/path/to/ca.crt"
            - DuckDB: "duckdb:///path/to/file.duckdb"
        path: Database file path (DuckDB only, used when connection_string is None)
        async_mode: Whether to use async mode
        **kwargs: Additional engine parameters
    
    Returns:
        Configured database session
    
    Examples:
        # Configure PostgreSQL connection (for library usage)
        from aipartnerupflow.core.storage.factory import configure_database
        
        session = configure_database(
            connection_string="postgresql+asyncpg://user:password@localhost/dbname"
        )
        
        # Configure PostgreSQL with SSL
        session = configure_database(
            connection_string="postgresql+asyncpg://user:password@host:port/dbname?sslmode=require&sslrootcert=/path/to/ca.crt"
        )
        
        # Configure DuckDB
        session = configure_database(path="./data/app.duckdb")
    """
    reset_default_session()
    return get_default_session(
        connection_string=connection_string,
        path=path,
        async_mode=async_mode,
        **kwargs
    )


# Backward compatibility aliases (deprecated)
def create_storage(*args, **kwargs):
    """Deprecated: Use create_session instead"""
    logger.warning("create_storage() is deprecated, use create_session() instead")
    return create_session(*args, **kwargs)


def get_default_storage(*args, **kwargs):
    """Deprecated: Use get_default_session instead"""
    logger.warning("get_default_storage() is deprecated, use get_default_session() instead")
    return get_default_session(*args, **kwargs)


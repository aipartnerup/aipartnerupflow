"""
Database session factory for creating database sessions
"""

from typing import Optional, Union, Dict, Any
from pathlib import Path
import os
import time
from threading import Lock
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine, Engine
from aipartnerupflow.core.storage.sqlalchemy.models import Base
from aipartnerupflow.core.storage.dialects.registry import get_dialect_config
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class SessionRegistry:
    """
    Registry for managing database sessions and session pool manager.
    
    This class encapsulates session state to avoid module-level resource creation,
    following dependency injection principles.
    """
    
    _default_session: Optional[Union[Session, AsyncSession]] = None
    _session_pool_manager: Optional["SessionPoolManager"] = None
    _session_pool_lock = Lock()
    
    @classmethod
    def get_default_session(cls) -> Optional[Union[Session, AsyncSession]]:
        """Get the default session instance"""
        return cls._default_session
    
    @classmethod
    def set_default_session(cls, session: Union[Session, AsyncSession]) -> None:
        """Set the default session instance"""
        cls._default_session = session
    
    @classmethod
    def reset_default_session(cls) -> None:
        """Reset the default session instance"""
        if cls._default_session:
            if isinstance(cls._default_session, AsyncSession):
                # Note: close() is async, but this is for testing only
                pass
            else:
                cls._default_session.close()
        cls._default_session = None
    
    @classmethod
    def get_session_pool_manager(cls) -> Optional["SessionPoolManager"]:
        """Get the session pool manager instance"""
        return cls._session_pool_manager
    
    @classmethod
    def set_session_pool_manager(cls, manager: "SessionPoolManager") -> None:
        """Set the session pool manager instance"""
        cls._session_pool_manager = manager
    
    @classmethod
    def reset_session_pool_manager(cls) -> None:
        """Reset the session pool manager instance"""
        with cls._session_pool_lock:
            if cls._session_pool_manager is not None:
                # Dispose engine if exists
                if cls._session_pool_manager._engine is not None:
                    try:
                        if isinstance(cls._session_pool_manager._engine, AsyncEngine):
                            # For async engines, we can't dispose synchronously
                            # The engine will be cleaned up when the process ends
                            pass
                        else:
                            cls._session_pool_manager._engine.dispose()
                    except Exception as e:
                        logger.warning(f"Error disposing session pool manager engine: {str(e)}")
                
                # Clear active sessions
                cls._session_pool_manager._active_sessions.clear()
                
                # Reset state
                cls._session_pool_manager._engine = None
                cls._session_pool_manager._sessionmaker = None
                cls._session_pool_manager._connection_string = None
                cls._session_pool_manager._path = None
                cls._session_pool_manager._async_mode = None
            
            cls._session_pool_manager = None
    
    @classmethod
    def get_session_pool_lock(cls) -> Lock:
        """Get the session pool lock"""
        return cls._session_pool_lock


class SessionLimitExceeded(Exception):
    """Exception raised when session limit is exceeded"""
    pass


def get_max_sessions() -> int:
    """
    Get maximum concurrent sessions limit
    
    Returns:
        Maximum number of concurrent sessions (default: 50)
    """
    max_sessions = os.getenv("AIPARTNERUPFLOW_MAX_SESSIONS", "50")
    try:
        return int(max_sessions)
    except ValueError:
        logger.warning(f"Invalid AIPARTNERUPFLOW_MAX_SESSIONS value: {max_sessions}, using default 50")
        return 50


def get_session_timeout() -> int:
    """
    Get session timeout in seconds
    
    Returns:
        Session timeout in seconds (default: 1800 = 30 minutes)
    """
    timeout = os.getenv("AIPARTNERUPFLOW_SESSION_TIMEOUT", "1800")
    try:
        return int(timeout)
    except ValueError:
        logger.warning(f"Invalid AIPARTNERUPFLOW_SESSION_TIMEOUT value: {timeout}, using default 1800")
        return 1800


class SessionPoolManager:
    """
    Manages database session pool for concurrent task tree executions
    
    Maintains a single engine per database configuration and provides
    session factory for creating isolated sessions with limits.
    """
    
    def __init__(self):
        self._engine: Optional[Union[Engine, AsyncEngine]] = None
        self._sessionmaker: Optional[Union[sessionmaker, async_sessionmaker]] = None
        self._active_sessions: Dict[Union[Session, AsyncSession], float] = {}
        self._lock = Lock()
        self._max_sessions: int = get_max_sessions()
        self._session_timeout: int = get_session_timeout()
        self._connection_string: Optional[str] = None
        self._path: Optional[str] = None
        self._async_mode: Optional[bool] = None
        self._engine_kwargs: Dict[str, Any] = {}
        logger.info(f"SessionPoolManager initialized: max_sessions={self._max_sessions}, timeout={self._session_timeout}s")
    
    def _get_config_key(
        self,
        connection_string: Optional[str] = None,
        path: Optional[Union[str, Path]] = None,
        async_mode: Optional[bool] = None
    ) -> str:
        """Generate a unique key for database configuration"""
        return f"{connection_string or ''}:{path or ''}:{async_mode}"
    
    def initialize(
        self,
        connection_string: Optional[str] = None,
        path: Optional[Union[str, Path]] = None,
        async_mode: Optional[bool] = None,
        **kwargs
    ) -> None:
        """
        Initialize the pool manager with database configuration
        
        Args:
            connection_string: Database connection string
            path: Database file path (DuckDB only)
            async_mode: Whether to use async mode
            **kwargs: Additional engine parameters
        """
        with self._lock:
            if self._engine is not None:
                # Already initialized, check if config matches
                config_key = self._get_config_key(connection_string, path, async_mode)
                current_key = self._get_config_key(self._connection_string, self._path, self._async_mode)
                if config_key == current_key:
                    logger.debug("SessionPoolManager already initialized with matching config")
                    return
                else:
                    logger.warning(
                        f"SessionPoolManager reinitializing with different config. "
                        f"Old: {current_key}, New: {config_key}"
                    )
            
            # Store configuration
            self._connection_string = connection_string
            self._path = str(path) if path else None
            self._async_mode = async_mode
            self._engine_kwargs = kwargs.copy()
            
            # Determine dialect and connection string
            if connection_string is not None:
                if is_postgresql_url(connection_string):
                    dialect = "postgresql"
                    if async_mode is None:
                        async_mode = True
                    connection_string = normalize_postgresql_url(connection_string, async_mode)
                elif connection_string.startswith("duckdb://"):
                    dialect = "duckdb"
                    if async_mode is None:
                        async_mode = False
                    path = connection_string.replace("duckdb:///", "").replace("duckdb://", "")
                    if path == "" or path == ":memory:":
                        path = ":memory:"
                    else:
                        path = str(Path(path).absolute())
                        # Ensure directory exists before creating connection
                        _ensure_database_directory_exists(path)
                else:
                    raise ValueError(
                        f"Unsupported connection string format: {connection_string}. "
                        f"Supported formats: postgresql://..., postgresql+asyncpg://..., duckdb://..."
                    )
            else:
                dialect = "duckdb"
                if async_mode is None:
                    async_mode = False
                if path is None:
                    path = _get_default_db_path()
                elif path != ":memory:":
                    path = str(Path(path).absolute())
                    # Ensure directory exists before creating connection
                    _ensure_database_directory_exists(path)
            
            try:
                dialect_config = get_dialect_config(dialect)
            except ValueError:
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
                    raise ValueError("Connection string is required for PostgreSQL")
            
            # Get engine kwargs from dialect config and merge with user-provided kwargs
            engine_kwargs = dialect_config.get_engine_kwargs()
            engine_kwargs.update(kwargs)
            self._engine_kwargs = engine_kwargs
            
            # Create engine and sessionmaker
            if async_mode:
                self._engine = create_async_engine(connection_string, **engine_kwargs)
                self._sessionmaker = async_sessionmaker(
                    self._engine, class_=AsyncSession, expire_on_commit=False
                )
            else:
                self._engine = create_engine(connection_string, **engine_kwargs)
                self._sessionmaker = sessionmaker(
                    self._engine, class_=Session, expire_on_commit=False
                )
            
            logger.info(f"SessionPoolManager initialized: {dialect} engine with pool")
            
            # Ensure tables exist
            if self._engine:
                try:
                    if async_mode:
                        # For async, tables will be created on first use
                        logger.debug("Async engine created, tables will be created on first use")
                    else:
                        Base.metadata.create_all(self._engine)
                except Exception as e:
                    logger.warning(f"Could not create tables automatically: {str(e)}")
    
    def create_session(self) -> Union[Session, AsyncSession]:
        """
        Create a new session from the pool
        
        Returns:
            New database session
            
        Raises:
            SessionLimitExceeded: If maximum session limit is reached
        """
        with self._lock:
            # Clean up expired sessions
            self._cleanup_expired_sessions()
            
            # Check session limit
            active_count = len(self._active_sessions)
            if active_count >= self._max_sessions:
                logger.warning(
                    f"Session limit exceeded: {active_count}/{self._max_sessions} active sessions"
                )
                raise SessionLimitExceeded(
                    f"Maximum session limit ({self._max_sessions}) exceeded. "
                    f"Currently {active_count} active sessions. "
                    f"Please wait for some sessions to complete."
                )
            
            # Create new session
            if self._sessionmaker is None:
                raise RuntimeError(
                    "SessionPoolManager not initialized. Call initialize() first or use get_session_pool_manager()"
                )
            
            session = self._sessionmaker()
            self._active_sessions[session] = time.time()
            
            logger.debug(f"Created session from pool: {len(self._active_sessions)}/{self._max_sessions} active")
            return session
    
    def release_session(self, session: Union[Session, AsyncSession]) -> None:
        """
        Release a session back to the pool
        
        Args:
            session: Session to release
        """
        with self._lock:
            if session in self._active_sessions:
                del self._active_sessions[session]
                logger.debug(f"Released session: {len(self._active_sessions)}/{self._max_sessions} active")
            
            # Close session
            try:
                if isinstance(session, AsyncSession):
                    # For async sessions, we need to close in async context
                    # This will be handled by the context manager
                    pass
                else:
                    session.close()
            except Exception as e:
                logger.warning(f"Error closing session: {str(e)}")
    
    def _cleanup_expired_sessions(self) -> None:
        """Clean up sessions that have exceeded timeout"""
        current_time = time.time()
        expired_sessions = []
        
        for session, created_at in list(self._active_sessions.items()):
            if current_time - created_at > self._session_timeout:
                expired_sessions.append(session)
        
        for session in expired_sessions:
            logger.warning(f"Closing expired session (timeout: {self._session_timeout}s)")
            del self._active_sessions[session]
            try:
                if isinstance(session, AsyncSession):
                    # Async session cleanup will be handled by context manager
                    pass
                else:
                    session.close()
            except Exception as e:
                logger.warning(f"Error closing expired session: {str(e)}")
    
    def get_active_session_count(self) -> int:
        """Get current number of active sessions"""
        with self._lock:
            return len(self._active_sessions)
    
    def get_max_sessions(self) -> int:
        """Get maximum session limit"""
        return self._max_sessions


def get_session_pool_manager() -> SessionPoolManager:
    """
    Get or create the global session pool manager
    
    Returns:
        SessionPoolManager instance
    """
    manager = SessionRegistry.get_session_pool_manager()
    
    if manager is None:
        with SessionRegistry.get_session_pool_lock():
            manager = SessionRegistry.get_session_pool_manager()
            if manager is None:
                manager = SessionPoolManager()
                # Initialize with default configuration
                connection_string = _get_database_url_from_env()
                manager.initialize(connection_string=connection_string)
                SessionRegistry.set_session_pool_manager(manager)
    
    return manager


def reset_session_pool_manager() -> None:
    """
    Reset the global session pool manager (for testing)
    
    This function allows tests to reset the session pool manager,
    ensuring clean state between tests.
    """
    SessionRegistry.reset_session_pool_manager()


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


def _ensure_database_directory_exists(db_path: Union[str, Path]) -> None:
    """
    Ensure database directory exists before creating connection.
    
    DuckDB doesn't automatically create directories, so we need to create
    the parent directory if the database path contains a directory component.
    
    Args:
        db_path: Database file path (string or Path)
    """
    db_file_path = Path(db_path)
    
    # Skip if in-memory database
    if db_path == ":memory:":
        return
    
    # Get parent directory
    db_dir = db_file_path.parent
    
    # Skip if parent is root directory or current directory (no directory component)
    if db_dir == Path("/") or db_dir == Path("."):
        return
    
    # Create directory if it doesn't exist
    if not db_dir.exists():
        try:
            db_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created database directory: {db_dir}")
        except OSError as e:
            logger.warning(f"Failed to create database directory {db_dir}: {e}")


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
                # Ensure directory exists before creating connection
                _ensure_database_directory_exists(path)
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
            # Ensure directory exists before creating connection
            _ensure_database_directory_exists(path)
    
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
                    asyncio.get_running_loop()
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
    
    .. deprecated:: 
        This function is deprecated for API route handlers. Use `get_request_session()` instead,
        which is automatically provided by `DatabaseSessionMiddleware` for each request.
        
        For API routes:
        - Use `get_request_session()` to get the request's isolated session (recommended)
        - The session is automatically managed by middleware (commit/rollback/close)
        
        For CLI commands or library usage outside request context:
        - This function is still available for backward compatibility
        - Consider using `with_db_session_context()` for better session management
    
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
    session = SessionRegistry.get_default_session()
    
    if session is None:
        # If connection_string not provided, check environment variable
        if connection_string is None:
            connection_string = _get_database_url_from_env()
        
        session = create_session(
            connection_string=connection_string,
            path=path,
            async_mode=async_mode,
            **kwargs
        )
        SessionRegistry.set_default_session(session)
    
    return session


def set_default_session(session: Union[Session, AsyncSession]) -> None:
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
    SessionRegistry.set_default_session(session)


def reset_default_session() -> None:
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
    SessionRegistry.reset_default_session()


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


class PooledSessionContext:
    """
    Async context manager for pooled database sessions
    
    Automatically manages session lifecycle with pool limits and cleanup.
    
    Example:
        async with PooledSessionContext() as session:
            # Use session for operations
            task_manager = TaskManager(session)
            await task_manager.distribute_task_tree(task_tree)
    """
    
    def __init__(
        self,
        connection_string: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize PooledSessionContext context manager
        
        Args:
            connection_string: Database connection string (optional)
                - If starts with "postgresql://" or "postgresql+" → PostgreSQL, async_mode=True
                - If starts with "duckdb://" → DuckDB, extract path, async_mode=False
                - If None → use default DuckDB path
            **kwargs: Additional engine parameters
        """
        self._pool_manager: Optional[SessionPoolManager] = None
        self._session: Optional[Union[Session, AsyncSession]] = None
        self._connection_string = connection_string
        
        # Detect database type from connection_string
        path: Optional[Union[str, Path]] = None
        async_mode: Optional[bool] = None
        
        if connection_string is not None:
            if is_postgresql_url(connection_string):
                async_mode = True
            elif connection_string.startswith("duckdb://"):
                async_mode = False
                path = connection_string.replace("duckdb:///", "").replace("duckdb://", "")
                if path == "" or path == ":memory:":
                    path = ":memory:"
                else:
                    path = str(Path(path).absolute())
                    # Ensure directory exists before creating connection
                    _ensure_database_directory_exists(path)
        else:
            # Default to DuckDB
            async_mode = False
            path = _get_default_db_path()
            # Ensure directory exists (already handled in _get_default_db_path, but ensure for consistency)
            if path != ":memory:":
                _ensure_database_directory_exists(path)
        
        self._path = path
        self._async_mode = async_mode
        self._kwargs = kwargs
    
    async def __aenter__(self) -> Union[Session, AsyncSession]:
        """Enter context manager and create session from pool"""
        # Get or create pool manager
        self._pool_manager = get_session_pool_manager()
        
        # Initialize pool manager if needed
        if self._pool_manager._engine is None:
            connection_string = self._connection_string
            if connection_string is None:
                connection_string = _get_database_url_from_env()
            
            self._pool_manager.initialize(
                connection_string=connection_string,
                path=self._path,
                async_mode=self._async_mode,
                **self._kwargs
            )
        
        # Create session from pool
        try:
            self._session = self._pool_manager.create_session()
            return self._session
        except SessionLimitExceeded as e:
            logger.error(f"Failed to create session: {str(e)}")
            raise
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager and release session"""
        if self._session is not None:
            # Release session back to pool
            if self._pool_manager:
                self._pool_manager.release_session(self._session)
            
            # Close session
            try:
                if isinstance(self._session, AsyncSession):
                    await self._session.close()
                else:
                    self._session.close()
            except Exception as e:
                logger.warning(f"Error closing session in context manager: {str(e)}")
            
            self._session = None
        
        return False  # Don't suppress exceptions


def create_pooled_session(
    connection_string: Optional[str] = None,
    **kwargs
) -> PooledSessionContext:
    """
    Create a PooledSessionContext context manager for database operations
    
    This is the recommended way to create database sessions for concurrent executions.
    The session is automatically managed with pool limits and cleanup.
    
    Args:
        connection_string: Database connection string (optional)
        path: Database file path (DuckDB only, optional)
        async_mode: Whether to use async mode (optional)
        **kwargs: Additional engine parameters
    
    Returns:
        PooledSessionContext context manager
        
    Example:
        async with create_pooled_session() as session:
            task_executor = TaskExecutor()
            await task_executor.execute_tasks(tasks, db_session=session)
    """
    return PooledSessionContext(
        connection_string=connection_string,
        **kwargs
    )


# Aliases for backward compatibility
TaskTreeSession = PooledSessionContext
create_task_tree_session = create_pooled_session


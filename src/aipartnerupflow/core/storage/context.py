"""
Database session context management using ContextVar

This module provides request-level database session management using Python's
ContextVar, allowing automatic session handling across nested function calls.
"""

from contextvars import ContextVar
from typing import Optional, Union, Callable
from functools import wraps
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from aipartnerupflow.core.storage.factory import (
    get_default_session,
    create_pooled_session,
)
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

# Context variable to store the current request's database session
_db_session_context: ContextVar[Optional[Union[Session, AsyncSession]]] = ContextVar(
    "db_session", default=None
)


def get_request_session() -> Optional[Union[Session, AsyncSession]]:
    """
    Get the current request's database session from context
    
    Returns:
        Current database session if available, None otherwise
        
    Note:
        This function retrieves the session from the request context.
        If no session is available (e.g., outside of a request context),
        it returns None. Use this for operations that need the request's
        isolated session.
    """
    return _db_session_context.get()


def set_request_session(session: Union[Session, AsyncSession]) -> None:
    """
    Set the current request's database session in context
    
    Args:
        session: Database session to set in context
        
    Note:
        This is typically called by DatabaseSessionMiddleware.
        Manual use is generally not needed.
    """
    _db_session_context.set(session)


def clear_request_session() -> None:
    """Clear the current request's database session from context"""
    _db_session_context.set(None)


@asynccontextmanager
async def with_db_session_context(
    use_pool: bool = True,
    auto_commit: bool = True,
):
    """
    Context manager for database session with automatic cleanup
    
    Args:
        use_pool: If True, use session pool (for concurrent operations).
                 If False, use default session (for backward compatibility).
        auto_commit: If True, automatically commit on success, rollback on error.
    
    Yields:
        Database session
        
    Example:
        async with with_db_session_context(use_pool=True) as session:
            # Use session here
            task = await repository.get_task_by_id(task_id, session)
    """
    session: Optional[Union[Session, AsyncSession]] = None
    old_session = get_request_session()
    pooled_context = None
    
    try:
        if use_pool:
            # Use pooled session to ensure it's created in the current event loop
            # This prevents "Task got Future attached to a different loop" errors
            pooled_context = create_pooled_session()
            session = await pooled_context.__aenter__()
        else:
            # Use default session for backward compatibility
            session = get_default_session()
        
        # Set session in context
        set_request_session(session)
        
        yield session
        
        # Commit if auto_commit is enabled
        if auto_commit and session:
            try:
                if isinstance(session, AsyncSession):
                    await session.commit()
                else:
                    session.commit()
            except Exception as e:
                logger.error(f"Error committing session: {str(e)}", exc_info=True)
                if isinstance(session, AsyncSession):
                    await session.rollback()
                else:
                    session.rollback()
                raise
        
    except Exception:
        # Rollback on error
        if session and auto_commit:
            try:
                if isinstance(session, AsyncSession):
                    await session.rollback()
                else:
                    session.rollback()
            except Exception as rollback_error:
                logger.error(f"Error rolling back session: {str(rollback_error)}", exc_info=True)
        raise
    finally:
        # Clean up pooled session if used
        if pooled_context is not None:
            try:
                await pooled_context.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing pooled session: {str(e)}")
        
        # Restore old session in context
        if old_session is not None:
            set_request_session(old_session)
        else:
            clear_request_session()


def with_db_session(
    use_pool: bool = True,
    auto_commit: bool = True,
):
    """
    Decorator to automatically provide database session to function
    
    Args:
        use_pool: If True, use session pool (for concurrent operations).
                 If False, use default session (for backward compatibility).
        auto_commit: If True, automatically commit on success, rollback on error.
    
    The decorated function should accept a `db_session` parameter, which will
    be automatically provided. If the function already has a session in context,
    it will be used instead.
    
    Example:
        @with_db_session(use_pool=True)
        async def my_handler(params: dict, db_session: AsyncSession):
            # db_session is automatically provided
            repository = TaskRepository(db_session)
            task = await repository.get_task_by_id(task_id)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Check if session is already in context (from middleware)
            session = get_request_session()
            
            if session is None:
                # No session in context, create one
                async with with_db_session_context(use_pool=use_pool, auto_commit=auto_commit) as new_session:
                    kwargs['db_session'] = new_session
                    return await func(*args, **kwargs)
            else:
                # Use existing session from context
                kwargs['db_session'] = session
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Check if session is already in context (from middleware)
            session = get_request_session()
            
            if session is None:
                # No session in context, create one
                # For sync functions, we need to handle this differently
                from aipartnerupflow.core.storage.factory import get_default_session
                new_session = get_default_session()
                kwargs['db_session'] = new_session
                try:
                    result = func(*args, **kwargs)
                    if auto_commit:
                        new_session.commit()
                    return result
                except Exception:
                    if auto_commit:
                        new_session.rollback()
                    raise
                finally:
                    # Note: We don't close default session here as it's managed globally
                    pass
            else:
                # Use existing session from context
                kwargs['db_session'] = session
                return func(*args, **kwargs)
        
        # Determine if function is async
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


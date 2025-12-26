"""
Database session middleware for automatic request-level session management

This middleware automatically creates and manages database sessions for each
request, ensuring proper isolation and concurrent operation support.
"""

from typing import Optional, Union
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from aipartnerupflow.core.storage.context import (
    set_request_session,
    clear_request_session,
)
from aipartnerupflow.core.storage.factory import (
    create_session,
)
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseSessionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to automatically manage database sessions for each request
    
    This middleware:
    1. Creates an isolated database session for each request
    2. Stores the session in ContextVar for nested access
    3. Automatically commits on success, rolls back on error
    4. Ensures proper session cleanup
    
    The session is available via get_request_session() throughout the request lifecycle.
    """
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request with automatic database session management
        
        Args:
            request: Starlette request
            call_next: Next middleware/handler in chain
            
        Returns:
            Response with proper session handling
        """
        session: Optional[Union[Session, AsyncSession]] = None
        
        try:
            # Create a new session for this request
            # This ensures each request has an isolated session
            try:
                session = create_session()
                
                # Store session in context for nested access
                set_request_session(session)
                
                logger.debug(f"Created database session for request {request.url.path}")
                
            except Exception as e:
                logger.error(f"Error creating database session: {str(e)}", exc_info=True)
                # Continue without session (fallback to default behavior)
                # This allows backward compatibility
                pass
            
            # Process request
            response = await call_next(request)
            
            # Commit session on successful response (2xx, 3xx status codes)
            if session and 200 <= response.status_code < 400:
                try:
                    if isinstance(session, AsyncSession):
                        await session.commit()
                    else:
                        session.commit()
                    logger.debug(f"Committed database session for request {request.url.path}")
                except Exception as e:
                    logger.error(f"Error committing session: {str(e)}", exc_info=True)
                    if isinstance(session, AsyncSession):
                        await session.rollback()
                    else:
                        session.rollback()
            
            return response
            
        except Exception as e:
            # Rollback session on error
            if session:
                try:
                    if isinstance(session, AsyncSession):
                        await session.rollback()
                    else:
                        session.rollback()
                    logger.debug(f"Rolled back database session due to error: {str(e)}")
                except Exception as rollback_error:
                    logger.error(f"Error rolling back session: {str(rollback_error)}", exc_info=True)
            
            # Re-raise exception to be handled by error handlers
            raise
            
        finally:
            # Clean up session
            if session:
                try:
                    if isinstance(session, AsyncSession):
                        await session.close()
                    else:
                        session.close()
                except Exception as e:
                    logger.warning(f"Error closing session: {str(e)}")
            
            # Clear session from context
            clear_request_session()
            
            logger.debug(f"Cleaned up database session for request {request.url.path}")


"""
aipartnerupflow API module

This module provides functions for creating and configuring API applications.
"""

from aipartnerupflow.api.app import create_app_by_protocol
from aipartnerupflow.api.extensions import initialize_extensions, _load_custom_task_model
from aipartnerupflow.api.main import create_runnable_app, main

__all__ = [
    "create_app_by_protocol",
    "create_runnable_app",
    "initialize_extensions",
    "main",
    "setup_app",
]


def setup_app(
    protocol: str = "a2a",
    auto_initialize_extensions: bool = True,
    load_custom_task_model: bool = True,
    custom_routes=None,
    custom_middleware=None,
    task_routes_class=None,
    **kwargs
):
    """
    Setup and create API application with all necessary initialization
    
    This is a convenience function that handles all the initialization steps
    that main.py does, making it easy to use aipartnerupflow as a library.
    
    Args:
        protocol: Protocol type ("a2a", "mcp", etc.). Default: "a2a"
        auto_initialize_extensions: If True, automatically initialize all extensions
                                   before creating the app (default: True)
        load_custom_task_model: If True, load custom TaskModel from environment variable
                               AIPARTNERUPFLOW_TASK_MODEL_CLASS (default: True)
        custom_routes: Optional list of custom Starlette Route objects
        custom_middleware: Optional list of custom Starlette BaseHTTPMiddleware classes
        task_routes_class: Optional custom TaskRoutes class
        **kwargs: Additional arguments passed to create_app_by_protocol
    
    Returns:
        Configured Starlette/FastAPI application instance
    
    Examples:
        # Basic usage
        from aipartnerupflow.api import setup_app
        
        app = setup_app()
        
        # With custom routes and middleware
        from starlette.routing import Route
        from starlette.middleware.base import BaseHTTPMiddleware
        
        custom_routes = [Route("/health", health_handler, methods=["GET"])]
        custom_middleware = [LoggingMiddleware]
        
        app = setup_app(
            custom_routes=custom_routes,
            custom_middleware=custom_middleware
        )
    """
    # Initialize extensions if requested
    if auto_initialize_extensions:
        initialize_extensions(
            load_custom_task_model=load_custom_task_model,
            auto_init_examples=False,  # Examples are deprecated, skip
        )
    elif load_custom_task_model:
        # Only load custom TaskModel if extensions not initialized
        _load_custom_task_model()
    
    # Create and return app
    return create_app_by_protocol(
        protocol=protocol,
        auto_initialize_extensions=False,  # Already initialized above
        task_routes_class=task_routes_class,
        custom_routes=custom_routes,
        custom_middleware=custom_middleware,
        **kwargs
    )

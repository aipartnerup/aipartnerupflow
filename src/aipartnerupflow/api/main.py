"""
Main entry point for aipartnerupflow API service

This is the application layer where environment variables can be used
for service deployment configuration.

Supports multiple network protocols:
- A2A Protocol Server (default): Agent-to-Agent communication protocol
- REST API (future): Direct HTTP REST endpoints

Protocol selection via AIPARTNERUPFLOW_API_PROTOCOL environment variable:
- "a2a" (default): A2A Protocol Server
- "rest" (future): REST API server
"""

import os
import sys
import time
import uvicorn
import warnings
from pathlib import Path
from typing import Optional

from aipartnerupflow.api.app import create_app_by_protocol
from aipartnerupflow.api.extensions import initialize_extensions, _auto_init_examples_if_needed, _load_custom_task_model
from aipartnerupflow.api.protocols import get_protocol_from_env
from aipartnerupflow.core.utils.logger import get_logger

# Initialize logger early
logger = get_logger(__name__)

# Global start time for measuring initialization duration
_start_time: Optional[float] = None


def _load_env_file():
    """
    Load .env file from appropriate location
    
    Priority order:
    1. Current working directory (where script is run from)
    2. Directory of the main script (if running as a script)
    3. Library's own directory (only when running library's own main.py directly)
    
    This ensures that when used as a library, it loads .env from the calling project,
    not from the library's installation directory.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        # python-dotenv not installed, skip .env loading
        return
    
    possible_paths = []
    
    # 1. Current working directory (where the script is run from)
    # This is the most common case when running from project root
    try:
        possible_paths.append(Path.cwd() / ".env")
    except Exception:
        pass  # Ignore errors in getting current working directory
    
    # 2. Directory of the main script (if running as a script)
    # This finds .env in the same directory as the script that calls main()
    if sys.argv and len(sys.argv) > 0:
        try:
            main_script = Path(sys.argv[0]).resolve()
            if main_script.is_file():
                possible_paths.append(main_script.parent / ".env")
        except Exception:
            pass  # Ignore errors in resolving script path
    
    # 3. Library's own directory (only for library development)
    # Check if we're running aipartnerupflow's own main.py directly
    # This helps when developing the library itself
    try:
        lib_root = Path(__file__).parent.parent.parent.parent
        # Only add if this looks like the library's own directory structure
        # (not when installed as a package in site-packages)
        if "site-packages" not in str(lib_root) and "dist-packages" not in str(lib_root):
            possible_paths.append(lib_root / ".env")
    except Exception:
        pass  # Ignore errors
    
    # Try each path and load the first one that exists
    for env_path in possible_paths:
        if env_path.exists():
            try:
                load_dotenv(env_path, override=False)  # override=False to respect existing env vars
                logger.debug(f"Loaded .env file from {env_path}")
                return
            except Exception as e:
                logger.debug(f"Failed to load .env from {env_path}: {e}")
                continue


def _setup_development_environment():
    """
    Setup development environment (only when running library's own main.py directly)
    
    This includes:
    - Suppressing specific warnings for cleaner output
    - Adding project root to Python path (for development mode)
    
    This should NOT run when used as a library to avoid affecting the calling project.
    """
    # Check if we're running aipartnerupflow's own main.py directly
    # (not when imported as a library)
    try:
        lib_root = Path(__file__).parent.parent.parent.parent
        # Only setup if this looks like the library's own directory structure
        # (not when installed as a package in site-packages)
        if "site-packages" in str(lib_root) or "dist-packages" in str(lib_root):
            return  # Installed as package, skip development setup
    except Exception:
        return  # Can't determine, skip to be safe
    
    # Suppress specific warnings for cleaner output (only in development)
    warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="websockets")
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="uvicorn")
    
    # Add project root to Python path for development (only when running directly)
    # This helps when running: python -m aipartnerupflow.api.main
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def create_runnable_app(**kwargs):
    """
    Create a runnable application based on protocol type
    
    This function handles all initialization steps and returns a configured
    application instance. Use this when you need the app object but want to
    run the server yourself (e.g., with custom uvicorn configuration).
    
    Args:
        **kwargs: Additional arguments passed to create_app_by_protocol():
            - protocol: Protocol type (overrides AIPARTNERUPFLOW_API_PROTOCOL env var)
            - custom_routes: Optional list of custom Starlette Route objects
            - custom_middleware: Optional list of custom Starlette BaseHTTPMiddleware classes
            - task_routes_class: Optional custom TaskRoutes class
            - verify_token_func: Optional custom JWT token verification function.
                              If provided, it will be used to verify JWT tokens.
                              If None and AIPARTNERUPFLOW_JWT_SECRET_KEY is set, a default verifier will be created.
                              Signature: verify_token_func(token: str) -> Optional[dict]
            - verify_permission_func: Optional function to verify user permissions.
                                    If provided, it will be used to verify user permissions for accessing resources.
                                    If None, permission checking is disabled.
                                    Signature: verify_permission_func(user_id: str, target_user_id: Optional[str], roles: Optional[list]) -> bool
            - auto_initialize_extensions: If True, automatically initialize extensions (default: True)
            - And any other arguments supported by create_app_by_protocol()
    
    Returns:
        Configured Starlette/FastAPI application instance
    
    Examples:
        # Basic usage (uses environment variables)
        from aipartnerupflow.api.main import create_runnable_app
        app = create_runnable_app()
        
        # With custom routes and middleware
        from starlette.routing import Route
        from starlette.middleware.base import BaseHTTPMiddleware
        
        app = create_runnable_app(
            custom_routes=[Route("/health", health_handler, methods=["GET"])],
            custom_middleware=[LoggingMiddleware]
        )
        
        # With custom protocol
        app = create_runnable_app(protocol="mcp")
        
        # Run with custom uvicorn configuration
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8080, workers=4)
    """
    global _start_time
    
    # Initialize start time if not set
    if _start_time is None:
        _start_time = time.time()
    
    # Load .env file (from calling project's directory when used as library)
    _load_env_file()
    
    # Setup development environment (only when running library's own main.py directly)
    _setup_development_environment()
    
    logger.info("Starting aipartnerupflow service")
    
    # Auto-discover built-in extensions (optional, extensions register via @executor_register, @storage_register, @hook_register decorators)
    # This ensures extensions are available when TaskManager is used
    auto_initialize_extensions = kwargs.pop("auto_initialize_extensions", True)
    if auto_initialize_extensions:
        try:
            initialize_extensions()
        except Exception as e:
            # Don't fail if extension initialization fails
            logger.warning(f"Failed to auto-initialize extensions: {e}")
    
    # Log startup time
    startup_time = time.time() - _start_time
    logger.info(f"Service initialization completed in {startup_time:.2f} seconds")

    # Load custom TaskModel if specified
    _load_custom_task_model()

    # Auto-initialize examples data if database is empty
    _auto_init_examples_if_needed()

    # Determine protocol (default to A2A for backward compatibility)
    protocol = kwargs.pop("protocol", None) or get_protocol_from_env()
    logger.info(f"Starting API service with protocol: {protocol}")

    # Create app based on protocol (pass remaining kwargs)
    return create_app_by_protocol(
        protocol=protocol,
        auto_initialize_extensions=False,  # Already initialized above if needed
        **kwargs
    )


def main(**kwargs):
    """
    Main entry point for API service (can be called via entry point or as a library)
    
    This function handles all initialization steps, creates the application, and runs
    the uvicorn server. Use this when you want a complete ready-to-run server.
    
    Can be called directly from external projects (e.g., aipartnerupflow-demo) with
    custom configuration.
    
    Args:
        **kwargs: Arguments can include:
            - Application configuration (passed to create_runnable_app()):
                - protocol: Protocol type (overrides AIPARTNERUPFLOW_API_PROTOCOL env var)
                - custom_routes: Optional list of custom Starlette Route objects
                - custom_middleware: Optional list of custom Starlette BaseHTTPMiddleware classes
                - task_routes_class: Optional custom TaskRoutes class
                - verify_token_func: Optional custom JWT token verification function.
                                  If provided, it will be used to verify JWT tokens.
                                  If None and AIPARTNERUPFLOW_JWT_SECRET_KEY is set, a default verifier will be created.
                                  Signature: verify_token_func(token: str) -> Optional[dict]
                - verify_permission_func: Optional function to verify user permissions.
                                        If provided, it will be used to verify user permissions for accessing resources.
                                        If None, permission checking is disabled.
                                        Signature: verify_permission_func(user_id: str, target_user_id: Optional[str], roles: Optional[list]) -> bool
                - auto_initialize_extensions: If True, automatically initialize extensions (default: True)
            - Server configuration (for uvicorn.run()):
                - host: Server host (default: from AIPARTNERUPFLOW_API_HOST or API_HOST env var, or "0.0.0.0")
                - port: Server port (default: from AIPARTNERUPFLOW_API_PORT or API_PORT env var, or 8000)
                - workers: Number of worker processes (default: 1)
                - loop: Event loop type (default: "asyncio")
                - limit_concurrency: Maximum concurrent connections (default: 100)
                - limit_max_requests: Maximum requests per worker (default: 1000)
                - access_log: Enable access logging (default: True)
    
    Examples:
        # Basic usage (uses environment variables)
        from aipartnerupflow.api.main import main
        main()
        
        # With custom routes and server configuration
        from starlette.routing import Route
        
        main(
            custom_routes=[Route("/health", health_handler, methods=["GET"])],
            host="0.0.0.0",
            port=8080,
            workers=4
        )
    """
    # Extract uvicorn-specific parameters from kwargs (use pop to avoid KeyError)
    # Use explicit None check to handle 0 as a valid value
    host = kwargs.pop("host", None)
    if host is None:
        host = os.getenv("AIPARTNERUPFLOW_API_HOST", os.getenv("API_HOST", "0.0.0.0"))
    
    port = kwargs.pop("port", None)
    if port is None:
        port = int(os.getenv("AIPARTNERUPFLOW_API_PORT", os.getenv("API_PORT", "8000")))
    else:
        port = int(port)
    
    workers = kwargs.pop("workers", 1)
    loop = kwargs.pop("loop", "asyncio")
    limit_concurrency = kwargs.pop("limit_concurrency", 100)
    limit_max_requests = kwargs.pop("limit_max_requests", 1000)
    access_log = kwargs.pop("access_log", True)
    
    # Create app with remaining kwargs (application configuration)
    app = create_runnable_app(**kwargs)
        
    # Run server
    uvicorn.run(
        app,
        host=host,
        port=port,
        workers=workers,
        loop=loop,
        limit_concurrency=limit_concurrency,
        limit_max_requests=limit_max_requests,
        access_log=access_log,
    )


if __name__ == "__main__":
    main()

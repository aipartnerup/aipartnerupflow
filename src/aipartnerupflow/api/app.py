"""
Application creation for aipartnerupflow

This module provides functions to create API applications based on different protocols.
"""

import os
from typing import Any, Optional, Type, List, TYPE_CHECKING

from aipartnerupflow import __version__
from aipartnerupflow.api.extensions import initialize_extensions
from aipartnerupflow.api.protocols import (
    check_protocol_dependency,
    get_protocol_dependency_info,
    get_protocol_from_env,
)
from aipartnerupflow.core.utils.helpers import get_url_with_host_and_port
from aipartnerupflow.core.utils.logger import get_logger

if TYPE_CHECKING:
    from aipartnerupflow.api.routes.tasks import TaskRoutes

logger = get_logger(__name__)


def create_a2a_server(
    jwt_secret_key: Optional[str],
    jwt_algorithm: str,
    base_url: str,
    enable_system_routes: bool,
    enable_docs: bool = True,
    task_routes_class: Optional["Type[TaskRoutes]"] = None,
    custom_routes: Optional[List] = None,
    custom_middleware: Optional[List] = None,
    verify_token_func: Optional[Any] = None,
    verify_permission_func: Optional[Any] = None,
) -> Any:
    """
    Create A2A Protocol Server
    
    Args:
        jwt_secret_key: JWT secret key for token verification (used if verify_token_func is None)
        jwt_algorithm: JWT algorithm (default: "HS256")
        base_url: Base URL of the service
        enable_system_routes: Whether to enable system routes
        enable_docs: Whether to enable API documentation
        task_routes_class: Optional custom TaskRoutes class
        custom_routes: Optional list of custom Starlette Route objects
        custom_middleware: Optional list of custom Starlette BaseHTTPMiddleware classes
        verify_token_func: Optional custom JWT token verification function.
                         If provided, it will be used to verify JWT tokens.
                         If None and jwt_secret_key is provided, a default verifier will be created.
                         Signature: verify_token_func(token: str) -> Optional[dict]
        verify_permission_func: Optional function to verify user permissions.
                              If provided, it will be used to verify user permissions for accessing resources.
                              If None, permission checking is disabled.
                              Signature: verify_permission_func(user_id: str, target_user_id: Optional[str], roles: Optional[list]) -> bool
    """
    from aipartnerupflow.api.a2a.server import create_a2a_server

    # Get TaskModel class from registry for logging
    from aipartnerupflow.core.config import get_task_model_class

    task_model_class = get_task_model_class()

    logger.info(
        f"A2A Protocol Server configuration: "
        f"JWT enabled={bool(jwt_secret_key or verify_token_func)}, "
        f"System routes={enable_system_routes}, "
        f"Docs={enable_docs}, "
        f"TaskModel={task_model_class.__name__}"
    )

    a2a_server_instance = create_a2a_server(
        verify_token_func=verify_token_func,
        verify_token_secret_key=jwt_secret_key,
        verify_token_algorithm=jwt_algorithm,
        base_url=base_url,
        enable_system_routes=enable_system_routes,
        enable_docs=enable_docs,
        task_routes_class=task_routes_class,
        custom_routes=custom_routes,
        custom_middleware=custom_middleware,
        verify_permission_func=verify_permission_func,
    )

    # Note: build() is now optional - CustomA2AStarletteApplication is directly ASGI callable
    # We call it explicitly here for backward compatibility and to get the built app immediately
    return a2a_server_instance.build()


def create_mcp_server(
    base_url: str,
    enable_system_routes: bool,
    enable_docs: bool = True,
    task_routes_class: Optional["Type[TaskRoutes]"] = None,
) -> Any:
    """Create MCP (Model Context Protocol) Server"""
    from fastapi import FastAPI
    from aipartnerupflow.api.mcp.server import McpServer

    logger.info(
        f"MCP Server configuration: "
        f"System routes={enable_system_routes}, "
        f"Docs={enable_docs}"
    )

    # Create FastAPI app
    app = FastAPI(
        title="aipartnerupflow MCP Server",
        description="Model Context Protocol server for task orchestration",
        version=__version__,
    )

    # Create MCP server instance
    mcp_server = McpServer(task_routes_class=task_routes_class)

    # Add MCP HTTP routes
    mcp_routes = mcp_server.get_http_routes()
    for route in mcp_routes:
        app.routes.append(route)

    # Add system routes if enabled
    if enable_system_routes:
        from starlette.routing import Route
        from aipartnerupflow.api.routes.system import SystemRoutes

        system_routes = SystemRoutes()

        async def system_handler(request):
            return await system_routes.handle_system_requests(request)

        app.routes.append(Route("/system", system_handler, methods=["POST"]))

    # Add docs if enabled
    if enable_docs:
        from aipartnerupflow.api.docs.swagger_ui import setup_swagger_ui

        setup_swagger_ui(app)

    return app


def create_rest_server() -> Any:
    """Create REST API Server (future implementation)"""
    # TODO: Implement REST API server when ready
    raise NotImplementedError(
        "REST API server is not yet implemented. "
        "Please use A2A Protocol Server (set AIPARTNERUPFLOW_API_PROTOCOL=a2a or leave unset)."
    )


def create_app_by_protocol(
    protocol: Optional[str] = None,
    auto_initialize_extensions: bool = True,
    task_routes_class: Optional["Type[TaskRoutes]"] = None,
    custom_routes: Optional[List] = None,
    custom_middleware: Optional[List] = None,
    verify_token_func: Optional[Any] = None,
    verify_permission_func: Optional[Any] = None,
) -> Any:
    """
    Create application based on protocol type

    This is the main function for creating API applications. It should be used
    by both CLI commands and programmatic API usage.

    Args:
        protocol: Protocol type. If None, uses environment variable
                  AIPARTNERUPFLOW_API_PROTOCOL or defaults to "a2a"
        auto_initialize_extensions: If True, automatically initialize all extensions
                                   before creating the app (default: True)
        task_routes_class: Optional custom TaskRoutes class to use instead of default TaskRoutes.
                         Allows extending TaskRoutes functionality without monkey patching.
                         Example: task_routes_class=MyCustomTaskRoutes
        custom_routes: Optional list of custom Starlette Route objects to add to the application.
                      Routes are merged after default routes (custom routes can override defaults if needed).
                      Example: [Route("/custom", custom_handler, methods=["GET"])]
        custom_middleware: Optional list of custom Starlette BaseHTTPMiddleware classes to add to the application.
                          Middleware will be added in the order provided, after default middleware (CORS, LLM API key, JWT).
                          Each middleware class should be a subclass of BaseHTTPMiddleware.
                          Example: [MyCustomMiddleware, AnotherMiddleware]
        verify_token_func: Optional custom JWT token verification function.
                         If provided, it will be used to verify JWT tokens.
                         If None and AIPARTNERUPFLOW_JWT_SECRET_KEY is set, a default verifier will be created.
                         Signature: verify_token_func(token: str) -> Optional[dict]
        verify_permission_func: Optional function to verify user permissions.
                               If provided, it will be used to verify user permissions for accessing resources.
                               If None, permission checking is disabled.
                               Signature: verify_permission_func(user_id: str, target_user_id: Optional[str], roles: Optional[list]) -> bool

    Returns:
        Starlette/FastAPI application instance

    Raises:
        ValueError: If protocol is not supported
        ImportError: If protocol dependencies are not installed
    """
    # Auto-initialize extensions if requested
    if auto_initialize_extensions:
        initialize_extensions()

    # Determine protocol
    if protocol is None:
        protocol = get_protocol_from_env()
    else:
        protocol = protocol.lower()

    # Check if protocol is supported and dependencies are installed
    check_protocol_dependency(protocol)

    # Get protocol dependency info for logging
    _, _, description = get_protocol_dependency_info(protocol)
    logger.info(f"Creating {description} application")
    # Common configuration
    jwt_secret_key = os.getenv("AIPARTNERUPFLOW_JWT_SECRET_KEY")
    jwt_algorithm = os.getenv("AIPARTNERUPFLOW_JWT_ALGORITHM", "HS256")
    enable_system_routes = (
        os.getenv("AIPARTNERUPFLOW_ENABLE_SYSTEM_ROUTES", "true").lower()
        in ("true", "1", "yes")
    )
    enable_docs = (
        os.getenv("AIPARTNERUPFLOW_ENABLE_DOCS", "true").lower() in ("true", "1", "yes")
    )
    host = os.getenv("AIPARTNERUPFLOW_API_HOST", os.getenv("API_HOST", "0.0.0.0"))
    port = int(os.getenv("AIPARTNERUPFLOW_API_PORT", os.getenv("API_PORT", "8000")))
    default_url = get_url_with_host_and_port(host, port)
    base_url = os.getenv("AIPARTNERUPFLOW_BASE_URL", default_url)

    # Create app based on protocol
    if protocol == "a2a":
        return create_a2a_server(
            jwt_secret_key=jwt_secret_key,
            jwt_algorithm=jwt_algorithm,
            base_url=base_url,
            enable_system_routes=enable_system_routes,
            enable_docs=enable_docs,
            task_routes_class=task_routes_class,
            custom_routes=custom_routes,
            custom_middleware=custom_middleware,
            verify_token_func=verify_token_func,
            verify_permission_func=verify_permission_func,
        )
    elif protocol == "mcp":
        return create_mcp_server(
            base_url=base_url,
            enable_system_routes=enable_system_routes,
            enable_docs=enable_docs,
            task_routes_class=task_routes_class,
        )
    elif protocol == "rest":
        return create_rest_server()
    else:
        raise ValueError(
            f"Unknown protocol: {protocol}. "
            f"Supported protocols: 'a2a', 'mcp', 'rest' (future). "
            f"Set AIPARTNERUPFLOW_API_PROTOCOL environment variable."
        )


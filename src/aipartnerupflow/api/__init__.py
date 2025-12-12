"""
API service layer for aipartnerupflow

This module provides unified external API interfaces supporting multiple network protocols.
Currently implements A2A (Agent-to-Agent) Protocol Server. Future versions may include
additional protocols such as REST API.
"""

from typing import Optional

# Lazy import to allow checking if a2a dependencies are installed
# Import is deferred until create_app() or create_a2a_server() is called
# This allows the module to be imported even if [a2a] extra is not installed

# Backward compatibility: also export from top-level for old imports
# This allows: from aipartnerupflow.api import create_a2a_server
# to continue working
__all__ = [
    "create_app",
    "create_a2a_server",
]


def _get_create_a2a_server():
    """
    Lazy import of create_a2a_server function
    
    Raises:
        ImportError: If a2a dependencies are not installed
    """
    try:
        from aipartnerupflow.api.a2a.server import create_a2a_server
        return create_a2a_server
    except ImportError as e:
        error_msg = str(e)
        if "a2a" in error_msg.lower() or "a2a-sdk" in error_msg.lower():
            raise ImportError(
                "A2A Protocol Server dependencies are not installed. "
                "Please install them using: pip install aipartnerupflow[a2a]"
            ) from e
        raise


def create_a2a_server(
    verify_token_secret_key: Optional[str] = None,
    verify_token_algorithm: str = "HS256",
    base_url: Optional[str] = None,
    enable_system_routes: bool = True,
):
    """
    Create A2A server instance with configuration
    
    This function is a wrapper that lazily imports the actual create_a2a_server
    from the a2a submodule. This allows the module to be imported even if
    [a2a] extra is not installed.
    
    Args:
        verify_token_secret_key: JWT secret key for token verification (optional)
        verify_token_algorithm: JWT algorithm (default: "HS256")
        base_url: Base URL of the service (optional)
        enable_system_routes: Whether to enable system routes like /system (default: True)
    
    Returns:
        CustomA2AStarletteApplication instance
    
    Raises:
        ImportError: If a2a dependencies are not installed
    """
    create_a2a_server_func = _get_create_a2a_server()
    return create_a2a_server_func(
        verify_token_secret_key=verify_token_secret_key,
        verify_token_algorithm=verify_token_algorithm,
        base_url=base_url,
        enable_system_routes=enable_system_routes,
    )


def create_app(
    verify_token_secret_key: Optional[str] = None,
    verify_token_algorithm: str = "HS256",
    base_url: Optional[str] = None,
    enable_system_routes: bool = True,
    protocol: Optional[str] = None,
):
    """
    Create API server application based on protocol
    
    This is a convenience function that creates a server instance based on the specified protocol.
    It delegates to api/main.py's create_app_by_protocol() for unified protocol handling.
    
    Note: For A2A protocol, you can use create_a2a_server() directly for more control.
    For other protocols, this function uses the unified protocol handler.
    
    Args:
        verify_token_secret_key: JWT secret key for token verification (optional)
        verify_token_algorithm: JWT algorithm (default: "HS256")
        base_url: Base URL of the service (optional)
        enable_system_routes: Whether to enable system routes like /system (default: True)
        protocol: Protocol type ("a2a", "rest", etc.). If None, uses environment variable
                  AIPARTNERUPFLOW_API_PROTOCOL or defaults to "a2a"
    
    Returns:
        Starlette/FastAPI application instance
    
    Raises:
        ImportError: If protocol dependencies are not installed
        ValueError: If protocol is not supported
    """
    # For A2A protocol, use the direct function for backward compatibility
    # For other protocols, delegate to the unified protocol handler
    if protocol is None:
        from aipartnerupflow.api.protocols import get_protocol_from_env
        protocol = get_protocol_from_env()
    else:
        protocol = protocol.lower()

    if protocol == "a2a":
        # Use direct A2A server creation for backward compatibility
        a2a_server_instance = create_a2a_server(
            verify_token_secret_key=verify_token_secret_key,
            verify_token_algorithm=verify_token_algorithm,
            base_url=base_url,
            enable_system_routes=enable_system_routes,
        )
        return a2a_server_instance.build()
    else:
        # For other protocols, use the unified protocol handler from api/app.py
        from aipartnerupflow.api.app import create_app_by_protocol
        return create_app_by_protocol(protocol=protocol)


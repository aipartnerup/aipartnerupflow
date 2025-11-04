"""
API service layer for aipartnerupflow
"""

from typing import Optional
from aipartnerupflow.api.a2a_server import create_a2a_server

__all__ = [
    "create_app",
    "create_a2a_server",
]


def create_app(
    verify_token_secret_key: Optional[str] = None,
    verify_token_algorithm: str = "HS256",
    base_url: Optional[str] = None,
    enable_system_routes: bool = True,
):
    """
    Create A2A protocol server application (convenience wrapper)
    
    This is a convenience function that creates an A2A server instance and builds the app.
    For more control, use create_a2a_server() directly.
    
    Args:
        verify_token_secret_key: JWT secret key for token verification (optional)
        verify_token_algorithm: JWT algorithm (default: "HS256")
        base_url: Base URL of the service (optional)
        enable_system_routes: Whether to enable system routes like /system (default: True)
    
    Returns:
        Starlette/FastAPI application instance (A2A protocol server)
    """
    a2a_server_instance = create_a2a_server(
        verify_token_secret_key=verify_token_secret_key,
        verify_token_algorithm=verify_token_algorithm,
        base_url=base_url,
        enable_system_routes=enable_system_routes,
    )
    return a2a_server_instance.build()


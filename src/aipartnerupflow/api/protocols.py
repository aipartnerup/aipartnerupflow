"""
Protocol management for aipartnerupflow

This module handles protocol selection, dependency checking, and protocol configuration.
"""

import os

# Protocol dependency mapping: protocol -> (module_path, extra_name, description)
# This is the single source of truth for protocol configuration
PROTOCOL_DEPENDENCIES = {
    "a2a": (
        "aipartnerupflow.api.a2a.server",
        "a2a",
        "A2A Protocol Server",
    ),
    "mcp": (
        "aipartnerupflow.api.mcp.server",
        "a2a",  # MCP uses a2a dependencies (httpx, fastapi, starlette)
        "MCP (Model Context Protocol) Server",
    ),
    # Future protocols can be added here:
    # "rest": (
    #     "aipartnerupflow.api.rest.server",
    #     "rest",
    #     "REST API Server",
    # ),
    # "rpc": (
    #     "aipartnerupflow.api.rpc.server",
    #     "rpc",
    #     "RPC API Server",
    # ),
}

# Default protocol
DEFAULT_PROTOCOL = "a2a"


def get_supported_protocols() -> list[str]:
    """
    Get list of supported protocol names

    Returns:
        List of supported protocol names
    """
    return list(PROTOCOL_DEPENDENCIES.keys())


def get_protocol_dependency_info(protocol: str) -> tuple[str, str, str]:
    """
    Get dependency information for a protocol

    Args:
        protocol: Protocol name

    Returns:
        Tuple of (module_path, extra_name, description)

    Raises:
        ValueError: If protocol is not supported
    """
    if protocol not in PROTOCOL_DEPENDENCIES:
        supported = ", ".join(get_supported_protocols())
        raise ValueError(
            f"Unsupported protocol '{protocol}'. " f"Supported protocols: {supported}"
        )
    return PROTOCOL_DEPENDENCIES[protocol]


def get_default_protocol() -> str:
    """
    Get default protocol name

    Returns:
        Default protocol name
    """
    return DEFAULT_PROTOCOL


def get_protocol_from_env() -> str:
    """
    Get protocol from environment variable or return default

    Returns:
        Protocol name (lowercased)
    """
    protocol = os.getenv("AIPARTNERUPFLOW_API_PROTOCOL", DEFAULT_PROTOCOL)
    return protocol.lower()


def check_protocol_dependency(protocol: str) -> None:
    """
    Check if dependencies for the specified protocol are installed

    Args:
        protocol: Protocol name

    Raises:
        ValueError: If protocol is not supported
        ImportError: If protocol dependencies are not installed
    """
    module_path, extra_name, description = get_protocol_dependency_info(protocol)

    try:
        # Try to import the protocol server module to check if dependencies are installed
        __import__(module_path)
    except ImportError as e:
        error_msg = str(e)
        # Check if it's a dependency-related error
        if extra_name in error_msg.lower() or "No module named" in error_msg:
            raise ImportError(
                f"{description} dependencies are not installed. "
                f"Please install them using: pip install aipartnerupflow[{extra_name}]"
            ) from e
        raise


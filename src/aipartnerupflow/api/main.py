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

from aipartnerupflow.api.app import create_app_by_protocol
from aipartnerupflow.api.extensions import initialize_extensions, _auto_init_examples_if_needed, _load_custom_task_model
from aipartnerupflow.api.protocols import get_protocol_from_env
from aipartnerupflow.core.utils.logger import get_logger

# Suppress specific warnings for cleaner output
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="websockets")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="uvicorn")

# Add project root to Python path for development
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Initialize logger
logger = get_logger(__name__)
start_time = time.time()
logger.info("Starting aipartnerupflow service")

# Auto-discover built-in extensions (optional, extensions register via @executor_register, @storage_register, @hook_register decorators)
# This ensures extensions are available when TaskManager is used
# Note: This is called at module level for backward compatibility when main.py is imported directly
# For programmatic usage, call initialize_extensions() explicitly before create_app_by_protocol()
try:
    initialize_extensions()
except Exception as e:
    # Don't fail module import if extension initialization fails
    logger.warning(f"Failed to auto-initialize extensions at module level: {e}")


def main():
    """
    Main entry point for API service (can be called via entry point)

    Protocol selection via AIPARTNERUPFLOW_API_PROTOCOL environment variable:
    - "a2a" (default): A2A Protocol Server
    - "mcp": MCP (Model Context Protocol) Server
    - "rest" (future): REST API server
    """
    # Log startup time
    startup_time = time.time() - start_time
    logger.info(f"Service initialization completed in {startup_time:.2f} seconds")

    # Load custom TaskModel if specified
    _load_custom_task_model()

    # Auto-initialize examples data if database is empty
    _auto_init_examples_if_needed()

    # Determine protocol (default to A2A for backward compatibility)
    protocol = get_protocol_from_env()
    logger.info(f"Starting API service with protocol: {protocol}")

    # Create app based on protocol
    app = create_app_by_protocol(protocol)

    # Service-level configuration
    host = os.getenv("AIPARTNERUPFLOW_API_HOST", os.getenv("API_HOST", "0.0.0.0"))
    port = int(os.getenv("AIPARTNERUPFLOW_API_PORT", os.getenv("PORT", "8000")))

    # Run server
    uvicorn.run(
        app,
        host=host,
        port=port,
        workers=1,  # Single worker for async app
        loop="asyncio",  # Use asyncio event loop
        limit_concurrency=100,  # Increase concurrency limit
        limit_max_requests=1000,  # Increase max requests
        access_log=True,  # Enable access logging for debugging
    )


if __name__ == "__main__":
    main()

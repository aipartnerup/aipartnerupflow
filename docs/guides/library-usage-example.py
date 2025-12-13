"""
Complete example: Implementing main.py functionality in your own project

This example shows how to use aipartnerupflow as a library and implement
all the functionality that main.py provides.
"""

import os
import sys
import time
import warnings
from pathlib import Path

# ============================================================================
# Step 1: Load .env file (optional but recommended)
# ============================================================================
try:
    from dotenv import load_dotenv
    # Try multiple possible locations
    possible_paths = [
        Path.cwd() / ".env",  # Current working directory
        Path(__file__).parent / ".env",  # Same directory as this file
    ]
    for env_path in possible_paths:
        if env_path.exists():
            load_dotenv(env_path)
            print(f"Loaded .env file from {env_path}")
            break
except ImportError:
    # python-dotenv not installed, skip .env loading
    pass

# ============================================================================
# Step 2: Suppress warnings (optional, for cleaner output)
# ============================================================================
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="websockets")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="uvicorn")

# ============================================================================
# Step 3: Configure database (REQUIRED)
# ============================================================================
from aipartnerupflow.core.storage.factory import configure_database

# Option A: Use environment variable (recommended)
database_url = os.getenv("DATABASE_URL")
if database_url:
    configure_database(connection_string=database_url)
else:
    # Option B: Configure programmatically
    configure_database(path="./data/app.duckdb")  # DuckDB
    # Or for PostgreSQL:
    # configure_database(
    #     connection_string="postgresql+asyncpg://user:password@localhost/dbname"
    # )

# ============================================================================
# Step 4: Initialize extensions (REQUIRED for executors to work)
# ============================================================================
from aipartnerupflow.api.extensions import initialize_extensions

# This registers all available executors, hooks, and storage backends
initialize_extensions(
    load_custom_task_model=True,  # Load custom TaskModel from env var if specified
    auto_init_examples=False,  # Examples are deprecated, skip
)

# ============================================================================
# Step 5: Load custom TaskModel (optional)
# ============================================================================
from aipartnerupflow.api.extensions import _load_custom_task_model

# This is already called by initialize_extensions above, but you can call it manually
# if you set auto_initialize_extensions=False
# _load_custom_task_model()

# ============================================================================
# Step 6: Create application
# ============================================================================
from starlette.routing import Route
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Option A: Use setup_app() (RECOMMENDED - handles steps 4-5 automatically)
from aipartnerupflow.api import setup_app

# Define custom routes
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "service": "my-custom-service"
    })

custom_routes = [
    Route("/health", health_check, methods=["GET"]),
]

# Define custom middleware
class LoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests"""
    async def dispatch(self, request: Request, call_next):
        print(f"Request: {request.method} {request.url.path}")
        response = await call_next(request)
        print(f"Response: {response.status_code}")
        return response

custom_middleware = [LoggingMiddleware]

# Create app with setup_app() - this handles all initialization
app = setup_app(
    protocol="a2a",
    custom_routes=custom_routes,
    custom_middleware=custom_middleware,
)

# Option B: Manual setup (if you need more control)
# from aipartnerupflow.api.app import create_app_by_protocol
# app = create_app_by_protocol(
#     protocol="a2a",
#     auto_initialize_extensions=False,  # Already initialized above
#     custom_routes=custom_routes,
#     custom_middleware=custom_middleware,
# )

# ============================================================================
# Step 7: Run server
# ============================================================================
if __name__ == "__main__":
    import uvicorn
    
    start_time = time.time()
    print("Starting aipartnerupflow service...")
    
    # Service-level configuration
    host = os.getenv("AIPARTNERUPFLOW_API_HOST", os.getenv("API_HOST", "0.0.0.0"))
    port = int(os.getenv("AIPARTNERUPFLOW_API_PORT", os.getenv("API_PORT", "8000")))
    
    startup_time = time.time() - start_time
    print(f"Service initialization completed in {startup_time:.2f} seconds")
    print(f"Starting API service on {host}:{port}")
    
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


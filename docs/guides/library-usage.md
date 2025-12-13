# Using aipartnerupflow as a Library

This guide shows how to use `aipartnerupflow` as a library in your own project (e.g., `aipartnerupflow-demo`) and customize it with your own routes, middleware, and configurations.

## Table of Contents

- [Understanding main.py](#understanding-mainpy)
- [Basic Setup](#basic-setup)
- [Database Configuration](#database-configuration)
- [Custom Routes](#custom-routes)
- [Custom Middleware](#custom-middleware)
- [Custom TaskRoutes](#custom-taskroutes)
- [Complete Example](#complete-example)

## Understanding main.py

When using `aipartnerupflow` as a library, you need to understand what `main.py` does and why:

### What main.py Does

The `main.py` file in aipartnerupflow performs several initialization steps:

1. **Load .env file** - Loads environment variables from `.env` file
2. **Suppress warnings** - Suppresses specific warnings for cleaner output
3. **Initialize extensions** - Registers all available executors, hooks, and storage backends
4. **Load custom TaskModel** - Loads custom TaskModel class from environment variable
5. **Create application** - Creates the API application with proper configuration
6. **Run server** - Starts the uvicorn server

### Why You Need These Steps

- **Extensions initialization**: Without this, executors (like `crewai_executor`, `command_executor`) won't be available
- **Custom TaskModel**: Allows you to extend the TaskModel with custom fields
- **Database configuration**: Ensures database connection is set up before the app starts

### Solution: Use `setup_app()`

Instead of manually implementing all these steps, use the `setup_app()` function which handles everything automatically:

```python
from aipartnerupflow.api import setup_app

# This one function does everything main.py does!
app = setup_app()
```

If you need more control, you can manually call each step (see Option B in Basic Setup).

## Basic Setup

### 1. Install as Dependency

Add `aipartnerupflow` to your project's dependencies:

```bash
# In your project (e.g., aipartnerupflow-demo)
pip install aipartnerupflow[a2a]
# Or with all features
pip install aipartnerupflow[all]
```

### 2. Create Your Application

**Option A: Using `main()` (Recommended - Simplest)**

The `main()` function handles all initialization steps and runs the server automatically:

```python
from aipartnerupflow.api.main import main
from aipartnerupflow.core.storage.factory import configure_database

# Configure database (optional, can use DATABASE_URL env var instead)
configure_database(
    connection_string="postgresql+asyncpg://user:password@localhost/dbname"
)

# Run server with all initialization handled automatically
if __name__ == "__main__":
    main()
```

**Option A-2: Using `create_runnable_app()` (If you need the app object without running server)**

If you need the app object but want to run the server yourself:

```python
from aipartnerupflow.api.main import create_runnable_app
from aipartnerupflow.core.storage.factory import configure_database
import uvicorn

# Configure database
configure_database(
    connection_string="postgresql+asyncpg://user:password@localhost/dbname"
)

# Create app with all initialization handled automatically
app = create_runnable_app(protocol="a2a")

# Run with uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Note**: `create_runnable_app()` is the recommended function name. There's also `setup_app()` in `aipartnerupflow.api` which provides similar functionality.

**Option B: Manual Setup (More Control)**

If you need more control, you can manually handle initialization:

```python
import os
import warnings
from pathlib import Path
from aipartnerupflow.api.app import create_app_by_protocol
from aipartnerupflow.api.extensions import initialize_extensions, _load_custom_task_model
from aipartnerupflow.core.storage.factory import configure_database
import uvicorn

# 1. Load .env file (optional)
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# 2. Suppress warnings (optional)
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="websockets")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="uvicorn")

# 3. Configure database
configure_database(
    connection_string=os.getenv("DATABASE_URL")
)

# 4. Initialize extensions (registers executors, hooks, etc.)
initialize_extensions(
    load_custom_task_model=True,
    auto_init_examples=False,  # Examples are deprecated
)

# 5. Load custom TaskModel if specified in env var
_load_custom_task_model()

# 6. Create app
app = create_app_by_protocol(
    protocol="a2a",
    auto_initialize_extensions=False,  # Already initialized above
)

# 7. Run server
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Database Configuration

### Using Environment Variable

Create a `.env` file in your project root:

```bash
# .env (in your project root, e.g., aipartnerupflow-demo/.env)
DATABASE_URL=postgresql+asyncpg://user:password@localhost/dbname?sslmode=require
```

**Important**: When using aipartnerupflow as a library, the `.env` file should be in **your project's root directory**, not in the library's installation directory. The library will automatically look for `.env` in:

1. Current working directory (where you run the script)
2. Directory of the main script (where your `main.py` or entry script is located)
3. Library's own directory (only when developing the library itself, not when installed as a package)

This ensures that your project's `.env` file is loaded, not the library's `.env` file.

### Using Code

```python
from aipartnerupflow.core.storage.factory import configure_database

# PostgreSQL with SSL
configure_database(
    connection_string="postgresql+asyncpg://user:password@host:port/dbname?sslmode=require&sslrootcert=/path/to/ca.crt"
)

# DuckDB
configure_database(path="./data/app.duckdb")
```

## Custom Routes

Add your own API routes to extend the application:

**Using `main()` (Recommended):**

```python
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse
from aipartnerupflow.api.main import main

# Define custom route handlers
async def health_check(request: Request) -> JSONResponse:
    """Custom health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "service": "my-custom-service"
    })

async def custom_api_handler(request: Request) -> JSONResponse:
    """Custom API endpoint"""
    data = await request.json()
    return JSONResponse({
        "message": "Custom endpoint",
        "received": data
    })

# Create custom routes
custom_routes = [
    Route("/health", health_check, methods=["GET"]),
    Route("/api/custom", custom_api_handler, methods=["POST"]),
]

# Run server with custom routes
if __name__ == "__main__":
    main(custom_routes=custom_routes)
```

**Using `create_runnable_app()` or `setup_app()`:**

```python
from aipartnerupflow.api.main import create_runnable_app

# Create app with custom routes
app = create_runnable_app(
    protocol="a2a",
    custom_routes=custom_routes
)
```

## Custom Middleware

Add custom middleware for request processing, logging, authentication, etc.:

**Using `main()` (Recommended):**

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import time
from aipartnerupflow.api.main import main

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Custom middleware to log all requests"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log request
        print(f"Request: {request.method} {request.url.path}")
        
        # Process request
        response = await call_next(request)
        
        # Log response
        process_time = time.time() - start_time
        print(f"Response: {response.status_code} ({process_time:.3f}s)")
        
        return response

class CustomAuthMiddleware(BaseHTTPMiddleware):
    """Custom authentication middleware"""
    
    async def dispatch(self, request: Request, call_next):
        # Skip auth for certain paths
        if request.url.path in ["/health", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        # Check custom header
        api_key = request.headers.get("X-API-KEY")
        if not api_key or api_key != "your-secret-key":
            return JSONResponse(
                {"error": "Unauthorized"},
                status_code=401
            )
        
        return await call_next(request)

# Run server with custom middleware
if __name__ == "__main__":
    main(
        custom_middleware=[
            RequestLoggingMiddleware,
            CustomAuthMiddleware,
        ]
    )
```

**Using `create_runnable_app()` or `setup_app()`:**

```python
from aipartnerupflow.api.main import create_runnable_app

app = create_runnable_app(
    protocol="a2a",
    custom_middleware=[
        RequestLoggingMiddleware,
        CustomAuthMiddleware,
    ]
)
```

**Note**: Custom middleware is added **after** default middleware (CORS, LLM API key, JWT), so it runs in the order you provide.

## Custom TaskRoutes

Extend TaskRoutes to customize task management behavior:

```python
from aipartnerupflow.api.routes.tasks import TaskRoutes
from starlette.requests import Request
from starlette.responses import JSONResponse
from aipartnerupflow.api.app import create_app_by_protocol

class MyCustomTaskRoutes(TaskRoutes):
    """Custom TaskRoutes with additional functionality"""
    
    async def handle_task_requests(self, request: Request) -> JSONResponse:
        # Add custom logic before handling request
        print(f"Custom task request: {request.method} {request.url.path}")
        
        # Call parent implementation
        response = await super().handle_task_requests(request)
        
        # Add custom logic after handling request
        # (e.g., custom logging, metrics, etc.)
        
        return response

# Create app with custom TaskRoutes
app = create_app_by_protocol(
    protocol="a2a",
    task_routes_class=MyCustomTaskRoutes
)
```

## Complete Example

Here's a complete example combining all features using `setup_app()`:

```python
"""
aipartnerupflow-demo: Custom application using aipartnerupflow as a library
"""
import os
from pathlib import Path
from starlette.routing import Route
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import uvicorn

# Try to load .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

from aipartnerupflow.api import setup_app
from aipartnerupflow.core.storage.factory import configure_database
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

# ============================================================================
# Database Configuration
# ============================================================================

# Option 1: Use environment variable (recommended)
# DATABASE_URL=postgresql+asyncpg://user:password@localhost/dbname

# Option 2: Configure programmatically
# configure_database(
#     connection_string="postgresql+asyncpg://user:password@localhost/dbname"
# )

# ============================================================================
# Custom Routes
# ============================================================================

async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "service": "aipartnerupflow-demo",
        "version": "1.0.0"
    })

async def custom_api(request: Request) -> JSONResponse:
    """Custom API endpoint"""
    data = await request.json()
    return JSONResponse({
        "message": "Custom API endpoint",
        "received": data
    })

custom_routes = [
    Route("/health", health_check, methods=["GET"]),
    Route("/api/custom", custom_api, methods=["POST"]),
]

# ============================================================================
# Custom Middleware
# ============================================================================

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests"""
    
    async def dispatch(self, request: Request, call_next):
        logger.info(f"{request.method} {request.url.path}")
        response = await call_next(request)
        logger.info(f"Response: {response.status_code}")
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware"""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts = {}
    
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        # Simple rate limiting logic here
        # (In production, use Redis or similar)
        return await call_next(request)

custom_middleware = [
    RequestLoggingMiddleware,
    RateLimitMiddleware,
]

# ============================================================================
# Create Application
# ============================================================================

def create_app():
    """Create and configure the application"""
    # Using create_runnable_app() handles all initialization automatically
    from aipartnerupflow.api.main import create_runnable_app
    
    app = create_runnable_app(
        protocol="a2a",
        custom_routes=custom_routes,
        custom_middleware=custom_middleware,
    )
    return app

# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    app = create_app()
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )
```

## Running Your Application

```bash
# With environment variable
export DATABASE_URL="postgresql+asyncpg://user:password@localhost/dbname"
python app.py

# Or with .env file
# .env
DATABASE_URL=postgresql+asyncpg://user:password@localhost/dbname

python app.py
```

## Middleware Order

Middleware is added in the following order:

1. **Default middleware** (added by aipartnerupflow):
   - CORS middleware
   - LLM API key middleware
   - JWT authentication middleware (if enabled)

2. **Custom middleware** (added by you):
   - Added in the order you provide in `custom_middleware` list

This means your custom middleware runs **after** the default middleware, so it can:
- Access JWT-authenticated user information
- Modify responses from default routes
- Add additional logging/metrics

## Best Practices

1. **Use environment variables** for configuration (database URL, secrets, etc.)
2. **Load .env files** early in your application startup
3. **Configure database** before creating the app
4. **Keep custom routes** focused and well-documented
5. **Test middleware** thoroughly as it affects all requests
6. **Use type hints** for better code clarity

## Quick Reference: What main.py Does

For reference, here's what `aipartnerupflow.api.main.main()` does:

1. ✅ Loads `.env` file
2. ✅ Suppresses warnings
3. ✅ Initializes extensions (`initialize_extensions()`)
4. ✅ Loads custom TaskModel (`_load_custom_task_model()`)
5. ✅ Auto-initializes examples (deprecated, skipped)
6. ✅ Creates app (`create_app_by_protocol()`)
7. ✅ Runs uvicorn server

**Using `setup_app()`**: Steps 3-5 are handled automatically.

**Manual setup**: You need to call steps 3-5 yourself before creating the app.

See `docs/guides/library-usage-example.py` for a complete working example.

## Next Steps

- See [API Documentation](../api/quick-reference.md) for available APIs
- See [Task Management Guide](./task-management.md) for task operations
- See [Extension Development](./extension-development.md) for creating custom executors
- See `library-usage-example.py` for a complete working example


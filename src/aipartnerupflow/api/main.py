"""
Main entry point for aipartnerupflow API service

This is the application layer where environment variables can be used
for service deployment configuration.
"""

import os
import sys
import warnings
import uvicorn
import time

from aipartnerupflow.api.a2a_server import create_a2a_server
from aipartnerupflow.core.utils.helpers import get_url_with_host_and_port
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

# Auto-discover built-in extensions (optional, extensions register via @extension_register decorator)
# This ensures extensions are available when TaskManager is used
try:
    from aipartnerupflow.extensions.stdio import StdioExecutor  # noqa: F401
    logger.debug("Discovered stdio extension")
except ImportError:
    logger.debug("Stdio extension not available (optional)")
except Exception as e:
    logger.warning(f"Failed to discover stdio extension: {e}")

try:
    from aipartnerupflow.extensions.crewai import CrewManager  # noqa: F401
    logger.debug("Discovered crewai extension")
except ImportError:
    logger.debug("CrewAI extension not available (requires [crewai] extra)")
except Exception as e:
    logger.warning(f"Failed to discover crewai extension: {e}")


def main():
    """Main entry point for API service (can be called via entry point)"""
    # Log startup time
    startup_time = time.time() - start_time
    logger.info(f"Service initialization completed in {startup_time:.2f} seconds")
    
    
    jwt_secret_key = os.getenv("AIPARTNERUPFLOW_JWT_SECRET_KEY")
    jwt_algorithm = os.getenv("AIPARTNERUPFLOW_JWT_ALGORITHM", "HS256")
    enable_system_routes = os.getenv("AIPARTNERUPFLOW_ENABLE_SYSTEM_ROUTES", "true").lower() in ("true", "1", "yes")
    # Service-level configuration (application layer, not library layer)
    host = os.getenv("AIPARTNERUPFLOW_API_HOST", os.getenv("API_HOST", "0.0.0.0"))
    port = int(os.getenv("AIPARTNERUPFLOW_API_PORT", os.getenv("PORT", "8000")))
    default_url = get_url_with_host_and_port(host, port)
    base_url = os.getenv("AIPARTNERUPFLOW_BASE_URL", default_url)
    
    # Optional: Load custom TaskModel class from environment or module
    # Users can set AIPARTNERUPFLOW_TASK_MODEL_CLASS to import their custom model
    # Example: AIPARTNERUPFLOW_TASK_MODEL_CLASS="my_project.models.MyTaskModel"
    task_model_class_path = os.getenv("AIPARTNERUPFLOW_TASK_MODEL_CLASS")
    if task_model_class_path:
        try:
            from importlib import import_module
            from aipartnerupflow import set_task_model_class
            module_path, class_name = task_model_class_path.rsplit(".", 1)
            module = import_module(module_path)
            task_model_class = getattr(module, class_name)
            set_task_model_class(task_model_class)
            logger.info(f"Loaded custom TaskModel: {task_model_class_path}")
        except Exception as e:
            logger.warning(f"Failed to load custom TaskModel from {task_model_class_path}: {e}")
    
    # Get TaskModel class from registry for logging
    from aipartnerupflow.core.config import get_task_model_class
    task_model_class = get_task_model_class()
    
    # Create A2A server with configuration (from env vars or defaults)
    logger.info(
        f"Service configuration: "
        f"JWT enabled={bool(jwt_secret_key)}, "
        f"System routes={enable_system_routes}, "
        f"TaskModel={task_model_class.__name__}"
    )
    a2a_server_instance = create_a2a_server(
        verify_token_secret_key=jwt_secret_key,
        verify_token_algorithm=jwt_algorithm,
        base_url=base_url,
        enable_system_routes=enable_system_routes,
    )
    
    # Build and run A2A server
    app = a2a_server_instance.build()

    uvicorn.run(
        app,
        host=host,
        port=port,
        workers=1,  # Single worker for async app
        loop="asyncio",  # Use asyncio event loop
        limit_concurrency=100,  # Increase concurrency limit
        limit_max_requests=1000,  # Increase max requests
        access_log=True  # Enable access logging for debugging
    )


if __name__ == "__main__":
    main()


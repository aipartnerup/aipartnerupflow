"""
Extension management for aipartnerupflow

This module handles initialization and configuration of optional extensions.
Extensions are automatically detected based on installed dependencies.
"""

import os
from typing import Any, Optional

from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

# Extension configuration: maps extension names to their dependencies and module paths
# This aligns with pyproject.toml optional-dependencies
EXTENSION_CONFIG: dict[str, dict[str, Any]] = {
    "stdio": {
        "dependencies": [],  # Always available (stdlib)
        "module": "aipartnerupflow.extensions.stdio",
        "classes": [
            ("SystemInfoExecutor", "system_info_executor"),
            ("CommandExecutor", "command_executor"),
        ],
        "always_available": True,
    },
    "crewai": {
        "dependencies": ["crewai"],  # From [crewai] extra
        "module": "aipartnerupflow.extensions.crewai",
        "classes": [("CrewManager", "crewai_executor")],
    },
    "http": {
        "dependencies": ["httpx"],  # From [a2a] extra
        "module": "aipartnerupflow.extensions.http",
        "classes": [("RestExecutor", "rest_executor")],
    },
    "ssh": {
        "dependencies": ["asyncssh"],  # From [ssh] extra
        "module": "aipartnerupflow.extensions.ssh",
        "classes": [("SshExecutor", "ssh_executor")],
    },
    "docker": {
        "dependencies": ["docker"],  # From [docker] extra
        "module": "aipartnerupflow.extensions.docker",
        "classes": [("DockerExecutor", "docker_executor")],
    },
    "grpc": {
        "dependencies": ["grpcio"],  # From [grpc] extra
        "module": "aipartnerupflow.extensions.grpc",
        "classes": [("GrpcExecutor", "grpc_executor")],
    },
    "websocket": {
        "dependencies": ["websockets"],  # From [a2a] extra
        "module": "aipartnerupflow.extensions.websocket",
        "classes": [("WebSocketExecutor", "websocket_executor")],
    },
    "apflow": {
        "dependencies": [],  # Core extension, always available
        "module": "aipartnerupflow.extensions.apflow",
        "classes": [("ApFlowApiExecutor", "apflow_api_executor")],
        "always_available": True,
    },
    "mcp": {
        "dependencies": [],  # Uses stdlib, always available
        "module": "aipartnerupflow.extensions.mcp",
        "classes": [("McpExecutor", "mcp_executor")],
        "always_available": True,
    },
}


def _is_package_installed(package_name: str) -> bool:
    """
    Check if a package is installed using importlib.metadata

    For standard library packages, this function tries to import them directly.
    For third-party packages, it checks installed distributions.

    Args:
        package_name: Package name to check (e.g., "crewai", "httpx", "os")

    Returns:
        True if package is installed/available, False otherwise
    """
    # First, try importing directly (works for stdlib and installed packages)
    try:
        __import__(package_name)
        return True
    except ImportError:
        # If direct import fails, check installed distributions
        # This handles cases where package name differs from import name
        pass

    # Check installed distributions for third-party packages
    try:
        # Python 3.8+ has importlib.metadata in stdlib
        from importlib.metadata import distributions
    except ImportError:
        # Python 3.7 fallback (shouldn't be needed as we require 3.10+)
        try:
            from importlib_metadata import distributions
        except ImportError:
            return False

    # Check all installed distributions
    for dist in distributions():
        # Normalize package name (handle case differences, hyphens vs underscores)
        dist_name = dist.metadata.get("Name", "").lower().replace("-", "_")
        package_normalized = package_name.lower().replace("-", "_")

        if dist_name == package_normalized:
            return True

    return False


def _get_extension_enablement_from_env() -> dict[str, bool]:
    """
    Parse environment variables to determine which extensions to enable

    Supports two formats:
    1. AIPARTNERUPFLOW_EXTENSIONS=stdio,http,crewai (comma-separated list)
    2. AIPARTNERUPFLOW_ENABLE_<EXTENSION>=true/false (individual flags)

    Returns:
        Dictionary mapping extension names to enablement status
    """
    result: dict[str, bool] = {}

    # Format 1: Comma-separated list
    extensions_env = os.getenv("AIPARTNERUPFLOW_EXTENSIONS", "").strip()
    if extensions_env:
        enabled_extensions = [e.strip().lower() for e in extensions_env.split(",") if e.strip()]
        # If list is provided, only those are enabled
        for ext_name in EXTENSION_CONFIG.keys():
            result[ext_name] = ext_name.lower() in enabled_extensions
        return result

    # Format 2: Individual flags (AIPARTNERUPFLOW_ENABLE_<EXTENSION>)
    for ext_name in EXTENSION_CONFIG.keys():
        env_var = f"AIPARTNERUPFLOW_ENABLE_{ext_name.upper()}"
        env_value = os.getenv(env_var, "").strip().lower()
        if env_value:
            result[ext_name] = env_value in ("true", "1", "yes", "on")
        # If not set, will be determined by auto-detection

    return result


def _ensure_extension_registered(executor_class: Any, extension_id: str) -> None:
    """
    Ensure an extension is registered in the registry

    This function checks if an extension is already registered, and if not,
    manually registers it. This handles the case where modules were imported
    before but the registry was cleared (e.g., in tests).

    Args:
        executor_class: Executor class to register
        extension_id: Expected extension ID
    """
    from aipartnerupflow.core.extensions import get_registry

    registry = get_registry()

    # If already registered, nothing to do
    if registry.is_registered(extension_id):
        return

    # Module was imported but extension not registered (e.g., registry was cleared)
    # Manually register it
    try:
        from aipartnerupflow.core.extensions.decorators import _register_extension
        from aipartnerupflow.core.extensions.types import ExtensionCategory

        _register_extension(executor_class, ExtensionCategory.EXECUTOR, override=True)
        logger.debug(f"Manually registered extension '{extension_id}'")
    except Exception as reg_error:
        logger.warning(f"Failed to manually register {executor_class.__name__}: {reg_error}")


def _load_custom_task_model() -> None:
    """Load custom TaskModel class from environment variable if specified"""
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


def _auto_init_examples_if_needed() -> None:
    """
    Auto-initialize examples data if database is empty and examples are available

    DEPRECATED: This function is deprecated. The examples module has been removed
    from aipartnerupflow core library. For demo task initialization, please use
    aipartnerupflow-demo project instead.

    This function is kept for backward compatibility but will be removed in a future version.
    """
    # Examples module has been removed from core library
    # Demo task initialization should be handled by aipartnerupflow-demo
    logger.debug("Examples auto-initialization is deprecated. Use aipartnerupflow-demo for demo tasks.")
    return


def initialize_extensions(
    include_stdio: Optional[bool] = None,
    include_crewai: Optional[bool] = None,
    include_http: Optional[bool] = None,
    include_ssh: Optional[bool] = None,
    include_docker: Optional[bool] = None,
    include_grpc: Optional[bool] = None,
    include_websocket: Optional[bool] = None,
    include_apflow: Optional[bool] = None,
    include_mcp: Optional[bool] = None,
    auto_init_examples: bool = True,
    load_custom_task_model: bool = True,
) -> None:
    """
    Initialize aipartnerupflow extensions intelligently

    This function automatically detects installed optional dependencies and
    only imports extensions that are available. It can be overridden via:
    1. Function parameters (explicit control)
    2. Environment variables (AIPARTNERUPFLOW_EXTENSIONS or AIPARTNERUPFLOW_ENABLE_*)
    3. Auto-detection (default, based on installed packages)

    Args:
        include_stdio: Import stdio extensions (default: auto-detect or True)
        include_crewai: Import CrewAI extension (default: auto-detect)
        include_http: Import HTTP extension (default: auto-detect)
        include_ssh: Import SSH extension (default: auto-detect)
        include_docker: Import Docker extension (default: auto-detect)
        include_grpc: Import gRPC extension (default: auto-detect)
        include_websocket: Import WebSocket extension (default: auto-detect)
        include_apflow: Import ApFlow extension (default: auto-detect or True)
        include_mcp: Import MCP extension (default: auto-detect or True)
        auto_init_examples: Auto-initialize examples data if database is empty
        load_custom_task_model: Load custom TaskModel from environment variable
    """
    logger.info("Initializing aipartnerupflow extensions...")

    # Get environment variable overrides
    env_overrides = _get_extension_enablement_from_env()

    # Determine which extensions to load
    # Priority: function param > env var > auto-detect
    extension_enablement: dict[str, bool] = {}
    function_params = {
        "stdio": include_stdio,
        "crewai": include_crewai,
        "http": include_http,
        "ssh": include_ssh,
        "docker": include_docker,
        "grpc": include_grpc,
        "websocket": include_websocket,
        "apflow": include_apflow,
        "mcp": include_mcp,
    }

    for ext_name, ext_config in EXTENSION_CONFIG.items():
        # Priority: function param > env var > auto-detect
        param_value = function_params.get(ext_name)

        if param_value is not None:
            # Explicit function parameter
            extension_enablement[ext_name] = param_value
        elif ext_name in env_overrides:
            # Environment variable override
            extension_enablement[ext_name] = env_overrides[ext_name]
        elif ext_config.get("always_available", False):
            # Always available extensions
            extension_enablement[ext_name] = True
        else:
            # Auto-detect: check if dependencies are installed
            dependencies = ext_config.get("dependencies", [])
            if not dependencies:
                # No dependencies, assume available
                extension_enablement[ext_name] = True
            else:
                # Check if all dependencies are installed
                all_installed = all(_is_package_installed(dep) for dep in dependencies)
                extension_enablement[ext_name] = all_installed

    # Import and register enabled extensions
    for ext_name, enabled in extension_enablement.items():
        if not enabled:
            logger.debug(f"Skipping {ext_name} extension (not enabled or dependencies not installed)")
            continue

        ext_config = EXTENSION_CONFIG[ext_name]
        module_path = ext_config["module"]
        classes = ext_config["classes"]

        try:
            # Import the module
            module = __import__(module_path, fromlist=[cls[0] for cls in classes])

            # Register each class
            for class_name, extension_id in classes:
                executor_class = getattr(module, class_name)
                _ensure_extension_registered(executor_class, extension_id)

            logger.debug(f"Initialized {ext_name} extension")
        except ImportError as e:
            logger.debug(f"{ext_name} extension not available: {e}")
        except Exception as e:
            logger.warning(f"Failed to initialize {ext_name} extension: {e}")

    # Load custom TaskModel if specified
    if load_custom_task_model:
        _load_custom_task_model()

    # Auto-initialize examples if needed
    if auto_init_examples:
        _auto_init_examples_if_needed()

    logger.info("Extension initialization completed")


"""
aipartnerupflow - Task Orchestration and Execution Framework

Core orchestration framework with optional features.

Core modules (always included):
- core.interfaces: Core interfaces (ExecutableTask, BaseTask)
- core.execution: Task orchestration (TaskManager, StreamingCallbacks)
- core.extensions: Unified extension system (ExtensionRegistry, ExtensionCategory)
- core.storage: Database session factory (DuckDB default, PostgreSQL optional)
- core.utils: Utility functions

Optional extensions (require extras):
- extensions.crewai: CrewAI support [crewai]
- api: A2A Protocol Server [a2a] (A2A Protocol is the standard)
- cli: CLI tools [cli]

Protocol Standard: A2A (Agent-to-Agent) Protocol
"""

__version__ = "0.7.2"

# Core framework - re-export from core module for convenience
from aipartnerupflow.core import (
    ExecutableTask,
    BaseTask,
    TaskManager,
    StreamingCallbacks,
    create_session,
    get_default_session,
    # Backward compatibility (deprecated)
    create_storage,
    get_default_storage,
)

# Unified decorators (Flask-style API) - single entry point for all decorators
from aipartnerupflow.core.decorators import (
    register_pre_hook,
    register_post_hook,
    register_task_tree_hook,
    get_task_tree_hooks,
    set_task_model_class,
    get_task_model_class,
    task_model_register,
    clear_config,
    set_use_task_creator,
    get_use_task_creator,
    set_require_existing_tasks,
    get_require_existing_tasks,
    executor_register,
    storage_register,
    hook_register,
    tool_register,
)

# Extension registry utilities
from aipartnerupflow.core.extensions import add_executor_hook

__all__ = [
    # Core framework (from core module)
    "ExecutableTask",
    "BaseTask",
    "TaskManager",
    "StreamingCallbacks",
    "create_session",
    "get_default_session",
    # Backward compatibility (deprecated)
    "create_storage",
    "get_default_storage",
    # Unified decorators (Flask-style API)
    "register_pre_hook",
    "register_post_hook",
    "register_task_tree_hook",
    "get_task_tree_hooks",
    "set_task_model_class",
    "get_task_model_class",
    "task_model_register",
    "clear_config",
    "set_use_task_creator",
    "get_use_task_creator",
    "set_require_existing_tasks",
    "get_require_existing_tasks",
    "executor_register",
    "storage_register",
    "hook_register",
    "tool_register",
    # Extension registry utilities
    "add_executor_hook",
    # Version
    "__version__",
]

# Optional features (require extras):
# from aipartnerupflow.extensions.crewai import CrewManager, BatchManager
# Requires: pip install aipartnerupflow[crewai]

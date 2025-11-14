"""
Core orchestration framework modules

This module contains all core framework components for task orchestration:
- interfaces/: Core interfaces (ExecutableTask) - abstract contracts
- base/: Base class implementations (BaseTask) - common functionality
- execution/: Task orchestration (TaskManager, StreamingCallbacks)
- storage/: Storage implementation (DuckDB default, PostgreSQL optional)
- types.py: Core type definitions (TaskTreeNode, TaskStatus, hooks)
- utils/: Utility functions

All core modules are always included (pip install aipartnerupflow).
No optional dependencies required.

Note: TaskCreator (core) creates tasks from tasks array.
Note: Protocol specifications are handled by A2A Protocol (Agent-to-Agent Protocol),
which is the standard protocol for agent communication. See api/ module for A2A implementation.
"""

# Re-export from core modules for convenience
from aipartnerupflow.core.interfaces import ExecutableTask
from aipartnerupflow.core.base import BaseTask
from aipartnerupflow.core.execution import (
    TaskManager,
    TaskCreator,
    StreamingCallbacks,
)
from aipartnerupflow.core.extensions import (
    Extension,
    ExtensionCategory,
    ExtensionRegistry,
    get_registry,
    register_extension,
    executor_register,
    storage_register,
    hook_register,
)
from aipartnerupflow.core.types import (
    TaskTreeNode,
    TaskPreHook,
    TaskPostHook,
    TaskStatus,
)
    # Unified decorators (convenience re-export from decorators module)
from aipartnerupflow.core.decorators import (
    register_pre_hook,
    register_post_hook,
    set_task_model_class,
    get_task_model_class,
    clear_config,
    set_use_task_creator,
    get_use_task_creator,
    set_require_existing_tasks,
    get_require_existing_tasks,
    executor_register,
    storage_register,
    hook_register,
)
from aipartnerupflow.core.config import (
    get_pre_hooks,
    get_post_hooks,
)
from aipartnerupflow.core.storage import (
    create_session,
    get_default_session,
    # Backward compatibility (deprecated)
    create_storage,
    get_default_storage,
)

__all__ = [
    # Base interfaces
    "ExecutableTask",
    "BaseTask",
    # Core types
    "TaskTreeNode",
    "TaskPreHook",
    "TaskPostHook",
    "TaskStatus",
    # Execution
    "TaskManager",
    "TaskCreator",
    "StreamingCallbacks",
    # Extensions
    "Extension",
    "ExtensionCategory",
    "ExtensionRegistry",
    "get_registry",
    "register_extension",
    # Unified Decorators (Flask-style API)
    "register_pre_hook",
    "register_post_hook",
    "set_task_model_class",
    "get_task_model_class",
    "clear_config",
    "set_use_task_creator",
    "get_use_task_creator",
    "set_require_existing_tasks",
    "get_require_existing_tasks",
    "executor_register",
    "storage_register",
    "hook_register",
    # Configuration Registry (internal)
    "get_pre_hooks",
    "get_post_hooks",
    # Storage
    "create_session",
    "get_default_session",
    # Backward compatibility (deprecated)
    "create_storage",
    "get_default_storage",
]


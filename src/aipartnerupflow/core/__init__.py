"""
Core orchestration framework modules

This module contains all core framework components for task orchestration:
- interfaces/: Core interfaces (ExecutableTask, BaseTask, TaskStorage)
- execution/: Task orchestration (TaskManager, StreamingCallbacks)
- storage/: Storage implementation (DuckDB default, PostgreSQL optional)
- utils/: Utility functions

All core modules are always included (pip install aipartnerupflow).
No optional dependencies required.

Note: TaskPlanner (template-based task creation) is now in features/templates/ [templates]
Note: Protocol specifications are handled by A2A Protocol (Agent-to-Agent Protocol),
which is the standard protocol for agent communication. See api/ module for A2A implementation.
"""

# Re-export from core modules for convenience
from aipartnerupflow.core.interfaces import ExecutableTask, BaseTask
from aipartnerupflow.core.execution import TaskManager, StreamingCallbacks
from aipartnerupflow.core.types import (
    TaskTreeNode,
    TaskPreHook,
    TaskPostHook,
    TaskStatus,
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
    "StreamingCallbacks",
    # Storage
    "create_session",
    "get_default_session",
    # Backward compatibility (deprecated)
    "create_storage",
    "get_default_storage",
]


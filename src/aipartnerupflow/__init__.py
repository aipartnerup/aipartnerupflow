"""
aipartnerupflow - Task Orchestration and Execution Framework

Core orchestration framework with optional features.

Core modules (always included):
- core.interfaces: Core interfaces (ExecutableTask, BaseTask)
- core.execution: Task orchestration (TaskManager, StreamingCallbacks)
- features.templates: Template-based task creation (TaskPlanner, TaskCreator) [templates]
- core.storage: Database session factory (DuckDB default, PostgreSQL optional)
- core.utils: Utility functions

Optional features (require extras):
- features.crewai: CrewAI support [crewai]
- examples: Example implementations [examples]
- api: A2A Protocol Server [api] (A2A Protocol is the standard)
- cli: CLI tools [cli]

Protocol Standard: A2A (Agent-to-Agent) Protocol
"""

__version__ = "0.1.0"

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
    # Version
    "__version__",
]

# Optional features (require extras):
# from aipartnerupflow.features.crewai import CrewManager, BatchManager
# Requires: pip install aipartnerupflow[crewai]


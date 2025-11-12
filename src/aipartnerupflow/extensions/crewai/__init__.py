"""
CrewAI feature for aipartnerupflow

Provides LLM-based task execution via CrewAI and batch execution capabilities.

Requires: pip install aipartnerupflow[crewai]
"""

from aipartnerupflow.extensions.crewai.crew_manager import CrewManager
from aipartnerupflow.extensions.crewai.batch_manager import BatchManager
from aipartnerupflow.extensions.crewai.types import (
    CrewManagerState,
    BatchState,
    # Backward compatibility aliases
    FlowState,
    CrewState,
)
# Import tools module - this will auto-import all tools via tools.py
from aipartnerupflow.extensions.crewai.tools import (
    ToolRegistry,
    get_tool_registry,
    register_tool,
    resolve_tool,
)
from aipartnerupflow.extensions.crewai.decorators import crew_tool

__all__ = [
    "CrewManager",
    "BatchManager",
    "CrewManagerState",
    "BatchState",
    # Backward compatibility aliases
    "FlowState",
    "CrewState",
    # Tools
    "ToolRegistry",
    "get_tool_registry",
    "register_tool",
    "crew_tool",
    "resolve_tool",
]


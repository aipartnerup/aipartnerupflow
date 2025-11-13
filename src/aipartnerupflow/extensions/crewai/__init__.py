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
# Import tools from core.tools (tools framework is now in core)
from aipartnerupflow.core.tools import (
    ToolRegistry,
    get_tool_registry,
    register_tool,
    resolve_tool,
    tool_register,
)

# Backward compatibility: alias tool_register as crew_tool
crew_tool = tool_register

__all__ = [
    "CrewManager",
    "BatchManager",
    "CrewManagerState",
    "BatchState",
    # Backward compatibility aliases
    "FlowState",
    "CrewState",
    # Tools (from core.tools)
    "ToolRegistry",
    "get_tool_registry",
    "register_tool",
    "tool_register",
    "crew_tool",  # Backward compatibility alias
    "resolve_tool",
]


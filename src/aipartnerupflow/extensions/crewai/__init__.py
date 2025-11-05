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

__all__ = [
    "CrewManager",
    "BatchManager",
    "CrewManagerState",
    "BatchState",
    # Backward compatibility aliases
    "FlowState",
    "CrewState",
]


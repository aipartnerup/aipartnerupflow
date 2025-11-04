"""
CrewAI feature for aipartnerupflow

Provides LLM-based task execution via CrewAI and batch execution capabilities.

Requires: pip install aipartnerupflow[crewai]
"""

from aipartnerupflow.features.crewai.crew_manager import CrewManager
from aipartnerupflow.features.crewai.batch_manager import BatchManager
from aipartnerupflow.features.crewai.types import (
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


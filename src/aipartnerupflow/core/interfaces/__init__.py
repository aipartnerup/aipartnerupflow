"""
Core interfaces for aipartnerupflow

This module defines the core interfaces that all implementations must follow.
Interfaces are abstract contracts that define what methods must be implemented.
"""

from aipartnerupflow.core.interfaces.executable_task import ExecutableTask

__all__ = [
    "ExecutableTask",
]


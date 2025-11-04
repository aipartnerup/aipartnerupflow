"""
Core interfaces for aipartnerupflow

This module defines the core interfaces that all implementations must follow:
- ExecutableTask: Interface for all executable task types
- BaseTask: Base class with common implementations for ExecutableTask
"""

from aipartnerupflow.core.interfaces.plugin import ExecutableTask, BaseTask

__all__ = [
    "ExecutableTask",
    "BaseTask",
]


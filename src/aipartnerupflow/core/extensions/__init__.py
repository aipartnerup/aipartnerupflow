"""
Unified extension system for aipartnerupflow

This module provides a unified extension registration and discovery system
for all types of extensions (executors, storage, hooks, transformers, etc.).

All extensions implement the Extension interface and are registered through
the ExtensionRegistry using globally unique IDs.
"""

from aipartnerupflow.core.extensions.base import Extension
from aipartnerupflow.core.extensions.types import ExtensionCategory
from aipartnerupflow.core.extensions.protocol import ExecutorFactory, ExecutorLike
from aipartnerupflow.core.extensions.registry import (
    ExtensionRegistry,
    get_registry,
    register_extension,
)
from aipartnerupflow.core.extensions.decorators import (
    executor_register,
    storage_register,
    hook_register,
)

__all__ = [
    "Extension",
    "ExtensionCategory",
    "ExecutorFactory",
    "ExecutorLike",
    "ExtensionRegistry",
    "get_registry",
    "register_extension",
    "executor_register",
    "storage_register",
    "hook_register",
]


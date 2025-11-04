"""
Database dialects for different storage backends
"""

from aipartnerupflow.core.storage.dialects.registry import (
    register_dialect,
    get_dialect_config,
)

__all__ = [
    "register_dialect",
    "get_dialect_config",
]


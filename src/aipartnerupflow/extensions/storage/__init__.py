"""
Storage extensions

Provides storage backend implementations as ExtensionCategory.STORAGE extensions.
"""

# Auto-register storage backends when imported
from aipartnerupflow.extensions.storage import duckdb_storage  # noqa: F401

try:
    from aipartnerupflow.extensions.storage import postgres_storage  # noqa: F401
except ImportError:
    # PostgreSQL not available, skip
    pass

__all__ = ["duckdb_storage"]


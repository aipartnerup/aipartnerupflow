"""
Storage module for aipartnerupflow

Provides database session factory with default DuckDB (embedded, zero-config) and optional PostgreSQL support.
"""

from aipartnerupflow.core.storage.factory import (
    create_session,
    get_default_session,
    set_default_session,
    reset_default_session,
    # Backward compatibility (deprecated)
    create_storage,
    get_default_storage,
)

__all__ = [
    "create_session",
    "get_default_session",
    "set_default_session",
    "reset_default_session",
    # Backward compatibility (deprecated)
    "create_storage",
    "get_default_storage",
]


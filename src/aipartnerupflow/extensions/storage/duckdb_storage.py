"""
DuckDB storage backend extension

Provides DuckDB database backend as an ExtensionCategory.STORAGE extension.
"""

from typing import Dict, Any
from pathlib import Path
import json
from aipartnerupflow.core.extensions.storage import StorageBackend
from aipartnerupflow.core.extensions.decorators import storage_register


@storage_register()
class DuckDBStorage(StorageBackend):
    """
    DuckDB storage backend extension
    
    Provides embedded DuckDB database support.
    Registered as ExtensionCategory.STORAGE extension.
    """
    
    id = "duckdb"
    name = "DuckDB Storage"
    description = "Embedded DuckDB database backend (default)"
    version = "1.0.0"
    
    @property
    def type(self) -> str:
        """Extension type identifier"""
        return "duckdb"
    
    def normalize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize data before writing to database
        
        DuckDB supports JSON type, but needs special handling for nested structures.
        """
        normalized = {}
        for key, value in data.items():
            # DuckDB's JSON type requires string format
            if isinstance(value, (dict, list)):
                normalized[key] = json.dumps(value)
            else:
                normalized[key] = value
        return normalized
    
    def denormalize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Denormalize data after reading from database
        """
        denormalized = {}
        for key, value in data.items():
            if isinstance(value, str):
                # Try to parse JSON string
                try:
                    denormalized[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    denormalized[key] = value
            else:
                denormalized[key] = value
        return denormalized
    
    def get_connection_string(self, **kwargs) -> str:
        """
        Generate DuckDB connection string
        
        Args:
            **kwargs: Connection parameters
                - path: Database file path (default: ":memory:")
                - connection_string: Direct connection string (if provided, used as-is)
        
        Returns:
            Connection string for SQLAlchemy
        """
        if "connection_string" in kwargs:
            return kwargs["connection_string"]
        
        path = kwargs.get("path", ":memory:")
        if path == ":memory:":
            return "duckdb:///:memory:"
        else:
            # Ensure path is absolute
            abs_path = str(Path(path).absolute())
            return f"duckdb:///{abs_path}"
    
    def get_engine_kwargs(self) -> Dict[str, Any]:
        """DuckDB specific engine parameters"""
        return {
            "pool_pre_ping": True,
            # DuckDB is embedded, doesn't need connection pooling
        }


__all__ = ["DuckDBStorage"]


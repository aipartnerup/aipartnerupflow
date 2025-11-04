"""
DuckDB dialect configuration (default)
"""

from typing import Dict, Any
from pathlib import Path
import json


class DuckDBDialect:
    """DuckDB dialect configuration (default)"""
    
    @staticmethod
    def normalize_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize data (before writing to database)
        DuckDB supports JSON type, but needs special handling for nested structures
        """
        normalized = {}
        for key, value in data.items():
            # DuckDB's JSON type requires string format
            if isinstance(value, (dict, list)):
                normalized[key] = json.dumps(value)
            else:
                normalized[key] = value
        return normalized
    
    @staticmethod
    def denormalize_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Denormalize data (after reading from database)
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
    
    @staticmethod
    def get_connection_string(path: str = ":memory:") -> str:
        """
        Generate DuckDB connection string
        
        Args:
            path: Database file path, ":memory:" for in-memory database
        """
        if path == ":memory:":
            return "duckdb:///:memory:"
        else:
            # Ensure path is absolute
            abs_path = str(Path(path).absolute())
            return f"duckdb:///{abs_path}"
    
    @staticmethod
    def get_engine_kwargs() -> Dict[str, Any]:
        """DuckDB specific engine parameters"""
        return {
            "pool_pre_ping": True,
            # DuckDB is embedded, doesn't need connection pooling
        }


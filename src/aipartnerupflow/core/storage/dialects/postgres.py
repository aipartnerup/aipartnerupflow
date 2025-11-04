"""
PostgreSQL dialect configuration (optional, requires [postgres] extra)
"""

from typing import Dict, Any


class PostgreSQLDialect:
    """PostgreSQL dialect configuration (optional, requires [postgres] extra)"""
    
    @staticmethod
    def normalize_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize data (before writing to database)
        PostgreSQL natively supports JSONB, can store directly
        """
        # PostgreSQL's JSONB type can directly handle dict/list
        return data
    
    @staticmethod
    def denormalize_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Denormalize data (after reading from database)
        """
        # PostgreSQL's JSONB automatically converts to Python dict/list
        return data
    
    @staticmethod
    def get_connection_string(
        connection_string: str
    ) -> str:
        """
        Generate PostgreSQL connection string
        
        Args:
            connection_string: PostgreSQL connection string
        """
        return connection_string
    
    @staticmethod
    def get_engine_kwargs() -> Dict[str, Any]:
        """PostgreSQL specific engine parameters"""
        return {
            "pool_size": 10,
            "max_overflow": 20,
            "pool_pre_ping": True,
            "pool_recycle": 3600,
        }


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
    def get_connection_string(**kwargs) -> str:
        """
        Generate PostgreSQL connection string
        
        This method primarily supports connection_string parameter (string mode).
        Connection string should include all necessary parameters including SSL settings.
        
        Args:
            **kwargs: Connection parameters
                - connection_string: Direct connection string (required, used as-is)
                  Supports SSL parameters in query string:
                  - ?sslmode=require
                  - ?sslrootcert=/path/to/ca.crt
                  - ?sslcert=/path/to/client.crt
                  - ?sslkey=/path/to/client.key
        
        Returns:
            Connection string for SQLAlchemy
        
        Examples:
            # Basic connection
            get_connection_string(connection_string="postgresql+asyncpg://user:pass@host/db")
            
            # With SSL
            get_connection_string(connection_string="postgresql+asyncpg://user:pass@host/db?sslmode=require")
            
            # With SSL certificate
            get_connection_string(connection_string="postgresql+asyncpg://user:pass@host/db?sslrootcert=/path/to/ca.crt")
        """
        # Connection string is required (string mode only)
        if "connection_string" not in kwargs:
            raise ValueError(
                "connection_string parameter is required for PostgreSQL. "
                "Use full connection string format: "
                "postgresql+asyncpg://user:password@host:port/dbname?sslmode=require"
            )
        
        return kwargs["connection_string"]
    
    @staticmethod
    def get_engine_kwargs() -> Dict[str, Any]:
        """PostgreSQL specific engine parameters"""
        return {
            "pool_size": 10,
            "max_overflow": 20,
            "pool_pre_ping": True,
            "pool_recycle": 3600,
        }


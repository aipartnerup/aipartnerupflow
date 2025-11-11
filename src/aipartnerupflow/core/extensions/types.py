"""
Extension category types

Defines the categories of extensions supported by the framework.
"""

from enum import Enum


class ExtensionCategory(str, Enum):
    """
    Extension categories for classification
    
    Each extension must belong to one category, which determines
    how it's used and discovered in the system.
    """
    EXECUTOR = "executor"
    """Task execution implementations (stdio, crewai, http, etc.)"""
    
    STORAGE = "storage"
    """Storage backend implementations (duckdb, postgres, mongodb, etc.)"""
    
    HOOK = "hook"
    """Hook implementations (pre, post, error, lifecycle hooks)"""
    
    TRANSFORMER = "transformer"
    """Data transformation implementations (input, output, result formatters)"""
    
    AGGREGATOR = "aggregator"
    """Result aggregation implementations"""
    
    VALIDATOR = "validator"
    """Validation implementations (input, output, schema validators)"""
    
    NOTIFICATION = "notification"
    """Notification implementations (email, slack, webhook, sms)"""
    
    MONITOR = "monitor"
    """Monitoring implementations (metrics, performance, health checks)"""
    
    AUTHENTICATOR = "authenticator"
    """Authentication implementations (jwt, oauth, api_key)"""
    
    ROUTER = "router"
    """Routing implementations (executor selection, load balancing)"""
    
    TEMPLATE = "template"
    """Template implementations (reserved for future use)"""


__all__ = ["ExtensionCategory"]


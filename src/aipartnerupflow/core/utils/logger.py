"""
Logging utilities for aipartnerupflow
"""

import logging
import sys
import os


# Determine default log level based on context
def _get_default_log_level() -> str:
    """
    Determine the default log level based on environment and context.
    
    Priority:
    1. LOG_LEVEL environment variable (explicit override)
    2. DEBUG environment variable (for backward compatibility)
    3. Default: ERROR (for clean CLI output, only show actual errors)
    
    Returns:
        Log level as string
    """
    # Explicit LOG_LEVEL takes precedence
    if "LOG_LEVEL" in os.environ:
        return os.environ["LOG_LEVEL"]
    
    # Check for DEBUG flag (backward compatibility)
    if os.getenv("DEBUG", "").lower() in ("true", "1", "yes"):
        return "DEBUG"
    
    # Default: ERROR level for clean CLI output
    return "ERROR"


def get_logger(name: str = "aipartnerupflow") -> logging.Logger:
    """
    Get logger instance
    
    The log level is determined by environment variables:
    - LOG_LEVEL: Set to DEBUG, INFO, WARNING, ERROR, or CRITICAL
    - DEBUG: Legacy flag, set to 1 or true for DEBUG logging
    
    Examples:
        LOG_LEVEL=DEBUG apflow tasks all     # Enable debug logging
        apflow tasks all                      # Default: ERROR (clean output)
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        # Create console handler
        handler = logging.StreamHandler(sys.stdout)
        
        # Determine log level
        log_level = _get_default_log_level()
        handler.setLevel(log_level)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(handler)
        logger.setLevel(log_level)
    
    return logger




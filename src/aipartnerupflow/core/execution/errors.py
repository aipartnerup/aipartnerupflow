"""
Custom exceptions for task execution.

This module defines exceptions that represent different failure modes
during task execution, following best practices from FastAPI and other
production frameworks.

Exception Hierarchy:
    ApflowError (base)
        ├── BusinessError (user/expected errors, no stack trace)
        │   ├── ValidationError (input validation failures)
        │   └── ConfigurationError (config/environment issues)
        └── SystemError (unexpected errors, with stack trace)
            ├── ExecutorError (executor runtime failures)
            └── StorageError (database/storage failures)

Usage Guidelines:
    - Raise BusinessError subclasses for expected failures (bad input, missing config)
    - Let system exceptions (TimeoutError, ConnectionError) propagate naturally
    - TaskManager logs BusinessError without exc_info, others with exc_info
"""


class ApflowError(RuntimeError):
    """
    Base exception for all AiPartnerUpFlow-specific errors.
    
    This serves as the root of the exception hierarchy and allows
    catching all framework-specific exceptions if needed.
    """
    pass


class BusinessError(ApflowError):
    """
    Base exception for expected/user-facing failures.
    
    Use this exception for:
    - Validation errors (invalid input, missing required fields)
    - Configuration errors (missing API keys, invalid settings)
    - Permission errors (unauthorized access, quota exceeded)
    - Resource errors (file not found, resource unavailable)
    
    These errors represent expected failure modes that don't require
    stack traces for debugging. The TaskManager will log them without
    exc_info=True to keep logs clean.
    
    For unexpected system errors (network failures, timeouts, service errors),
    let the original exception propagate so it includes a full stack trace.
    
    Example:
        >>> if not inputs.get("api_key"):
        >>>     raise ConfigurationError("API key is required")
    """
    pass


class ValidationError(BusinessError):
    """
    Validation-specific business error.
    
    Use this for input validation failures, schema mismatches,
    or constraint violations that are caused by user input.
    
    Example:
        >>> if not inputs.get("model"):
        >>>     raise ValidationError("model is required in inputs")
    """
    pass


class ConfigurationError(BusinessError):
    """
    Configuration-specific business error.
    
    Use this for missing configuration, invalid settings,
    or environment setup issues.
    
    Example:
        >>> if not LITELLM_AVAILABLE:
        >>>     raise ConfigurationError("litellm is not installed")
    """
    pass


class SystemError(ApflowError):
    """
    Base exception for unexpected system-level errors.
    
    These are logged with full stack traces since they represent
    unexpected failures that need investigation.
    
    Note: Use this sparingly - most system errors (TimeoutError,
    ConnectionError, etc.) should be allowed to propagate naturally.
    """
    pass


class ExecutorError(SystemError):
    """
    Executor runtime error.
    
    Use this when an executor encounters an unexpected internal error
    that is not a connection/timeout/service error.
    """
    pass


class StorageError(SystemError):
    """
    Database or storage operation error.
    
    Use this for unexpected database/storage failures that are not
    simple connection errors.
    """
    pass


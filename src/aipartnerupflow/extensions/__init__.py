"""
Extensions for aipartnerupflow

Extensions contain production-ready implementations of task executors and other
optional functionality. Each extension is available via an extra dependency.

Extensions implement the Extension interface and are registered in the unified
ExtensionRegistry using globally unique IDs.

Extensions are automatically registered when imported via type-specific decorators:
- @executor_register() for executors
- @storage_register() for storage backends
- @hook_register() for hooks
"""

# Auto-import tools extension to register all tools when extensions module is imported
# This ensures tools are available for use across all extensions (e.g., CrewManager)
try:
    import aipartnerupflow.extensions.tools  # noqa: F401
except ImportError:
    # Tools extension may not be installed, that's okay
    pass
except Exception:
    # Other errors (syntax errors, etc.) should not break import
    pass

# Auto-import storage extensions to trigger registration
try:
    from aipartnerupflow.extensions.storage import duckdb_storage  # noqa: F401
    try:
        from aipartnerupflow.extensions.storage import postgres_storage  # noqa: F401
    except ImportError:
        # PostgreSQL not available, skip
        pass
except ImportError:
    # Storage extensions may not be available, that's okay
    pass

# Auto-import hook extensions to trigger registration
try:
    from aipartnerupflow.extensions.hooks import pre_execution_hook  # noqa: F401
    from aipartnerupflow.extensions.hooks import post_execution_hook  # noqa: F401
except ImportError:
    # Hook extensions may not be available, that's okay
    pass

# Auto-import core built-in executors to trigger registration
try:
    from aipartnerupflow.extensions.core import aggregate_results_executor  # noqa: F401
except ImportError:
    # Core extensions may not be available, that's okay
    pass


# Auto-import llm extension to trigger registration
try:
    from aipartnerupflow.extensions.llm import llm_executor  # noqa: F401
except ImportError:
    # LLM extension may not be available (missing litellm), that's okay
    pass

__all__ = []


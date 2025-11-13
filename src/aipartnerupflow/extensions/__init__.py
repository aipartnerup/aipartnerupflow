"""
Extensions for aipartnerupflow

Extensions contain production-ready implementations of task executors and other
optional functionality. Each extension is available via an extra dependency.

Extensions implement the Extension interface and are registered in the unified
ExtensionRegistry using globally unique IDs.
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

__all__ = []


"""
Tools Extension Package

This package contains individual tool implementations.
Tools are automatically imported and registered when this package is imported.
"""

# Import core tool functionality from core.tools
from aipartnerupflow.core.tools import (
    BaseTool,
    ToolRegistry,
    get_tool_registry,
    register_tool,
    resolve_tool,
    tool_register,
)

__all__ = [
    "BaseTool",
    "ToolRegistry",
    "get_tool_registry",
    "register_tool",
    "resolve_tool",
    "tool_register",
]

# Auto-import all tools from this directory to trigger @tool_register() decorator registration
# This ensures all tools are automatically registered when the tools package is imported
try:
    import importlib
    import pkgutil
    from pathlib import Path
    
    # Get the current package directory
    tools_package_dir = Path(__file__).parent
    
    # Dynamically import all Python modules in the tools directory
    if tools_package_dir.exists() and tools_package_dir.is_dir():
        for module_info in pkgutil.iter_modules([str(tools_package_dir)]):
            module_name = module_info.name
            # Skip __init__ and __pycache__, and only import modules (not packages)
            if not module_name.startswith("__") and not module_info.ispkg:
                try:
                    importlib.import_module(f"aipartnerupflow.extensions.tools.{module_name}")
                except ImportError:
                    # Tool may have missing dependencies, skip it silently
                    pass
                except Exception:
                    # Other errors (syntax errors, etc.) should not break import
                    pass
except Exception:
    # If auto-import fails, tools can still be imported manually
    pass


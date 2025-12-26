"""
Tool registration decorator

Provides @tool_register() decorator for automatic tool registration.
"""

from typing import Any, Optional
from aipartnerupflow.core.tools.registry import register_tool
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


def tool_register(name: Optional[str] = None, override: bool = False):
    """
    Decorator to automatically register tools in the tool registry
    
    This decorator can be used on:
    - BaseTool subclasses (tools)
    - Functions that should be used as tools
    - Classes that should be instantiated as tools
    
    The tool will be automatically registered with its class name (or custom name)
    and can be referenced in agent configurations using string format.
    
    Args:
        name: Optional custom name for the tool. If not provided, uses class name.
        override: If True, allow overriding existing registration
    
    Returns:
        Decorated class or function
    
    Example:
        from aipartnerupflow.core.tools import BaseTool, tool_register
        
        @tool_register()
        class MyCustomTool(BaseTool):
            name: str = "My Custom Tool"
            description: str = "A custom tool for doing something"
            
            def _run(self, arg: str) -> str:
                return f"Result: {arg}"
        
        # Tool is automatically registered as "MyCustomTool"
        # Can be used in agent config: tools=["MyCustomTool()"]
        
        @tool_register(name="custom_name")
        class AnotherTool(BaseTool):
            ...
        
        # Tool is registered as "custom_name"
        # Can be used in agent config: tools=["custom_name()"]
    """
    def decorator(cls_or_func: Any) -> Any:
        # Determine tool name
        tool_name = name
        if tool_name is None:
            # Use class/function name as default
            tool_name = cls_or_func.__name__
        
        # Register the tool
        try:
            register_tool(tool_name, cls_or_func, override=override)
            logger.info(f"Auto-registered tool '{tool_name}' using @tool_register decorator")
        except ValueError:
            if not override:
                logger.warning(f"Tool '{tool_name}' already registered. Use override=True to replace it.")
                raise
            else:
                register_tool(tool_name, cls_or_func, override=True)
                logger.info(f"Overridden tool '{tool_name}' using @tool_register decorator")
        
        # Return the original class/function unchanged
        return cls_or_func
    
    return decorator


__all__ = ["tool_register"]


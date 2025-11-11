"""
Tools module for CrewAI extensions

Provides str_to_callable function and tool registry for converting string tool names
to callable tool objects.
"""

import ast
from inspect import isfunction, isclass
from typing import Dict, Any, Callable, Optional
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """
    Registry for tools that can be referenced by string name
    
    This registry allows tools to be registered and then referenced by string
    in agent configurations, enabling dynamic tool loading.
    """
    
    _instance: Optional["ToolRegistry"] = None
    _tools: Dict[str, Any] = {}
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance
    
    def register(self, name: str, tool: Any, override: bool = False) -> None:
        """
        Register a tool in the registry
        
        Args:
            name: Tool name (string identifier)
            tool: Tool object (class, function, or instance)
            override: If True, allow overriding existing registration
        
        Raises:
            ValueError: If name is already registered and override=False
        """
        if name in self._tools and not override:
            raise ValueError(
                f"Tool '{name}' is already registered. "
                f"Use override=True to replace it, or use a different name."
            )
        
        self._tools[name] = tool
        logger.debug(f"Registered tool '{name}' in ToolRegistry")
    
    def get(self, name: str) -> Optional[Any]:
        """
        Get a tool from the registry
        
        Args:
            name: Tool name
            
        Returns:
            Tool object or None if not found
        """
        return self._tools.get(name)
    
    def list_tools(self) -> list[str]:
        """
        List all registered tool names
        
        Returns:
            List of registered tool names
        """
        return list(self._tools.keys())


# Global registry instance
_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    """
    Get the global tool registry instance
    
    Returns:
        ToolRegistry singleton instance
    """
    return _registry


def register_tool(name: str, tool: Any, override: bool = False) -> None:
    """
    Register a tool in the global registry (convenience function)
    
    Args:
        name: Tool name (string identifier)
        tool: Tool object (class, function, or instance)
        override: If True, allow overriding existing registration
    
    Example:
        from aipartnerupflow.extensions.crewai.tools import register_tool
        from crewai_tools import SerperDevTool
        
        register_tool("serper", SerperDevTool)
        # Now can use "serper()" in agent tools config
    """
    _registry.register(name, tool, override=override)


def str_to_callable(callable_obj: Any) -> Any:
    """
    Convert string tool reference to callable tool object
    
    Handles conversion of:
    - String tool names (e.g., "SerperDevTool()") to tool instances
    - Already callable objects (functions, classes, instances) - returns as-is
    - Tool objects (has run/execute/call methods) - returns as-is
    
    The function first checks the tool registry, then tries crewai_tools,
    then searches in the calling frame's globals.
    
    Args:
        callable_obj: String tool reference, function, class, or tool instance
        
    Returns:
        Callable tool object
        
    Raises:
        ValueError: If string format is invalid
        NameError: If tool name is not found
        TypeError: If input type is unsupported
    
    Example:
        # From registry
        register_tool("my_tool", MyTool)
        tool = str_to_callable("my_tool()")
        
        # From crewai_tools
        tool = str_to_callable("SerperDevTool()")
        
        # Already a tool object
        tool = str_to_callable(SerperDevTool())
    """
    # If input is function, class, or instance, return directly
    if isfunction(callable_obj) or isclass(callable_obj) or callable(callable_obj):
        return callable_obj
    
    # Check if it's a tool object (has run method or similar)
    if hasattr(callable_obj, 'run') or hasattr(callable_obj, 'execute') or hasattr(callable_obj, 'call'):
        return callable_obj
    
    # Check if it's any other object - return it as is
    if hasattr(callable_obj, '__dict__') or hasattr(callable_obj, '__slots__'):
        return callable_obj
    
    # If input is string, parse to callable object
    if isinstance(callable_obj, str):
        # Auto-add () if it's a simple class name (not a function call format)
        if '(' not in callable_obj.strip():
            callable_obj = f"{callable_obj.strip()}()"
        
        # Parse string to AST
        try:
            tree = ast.parse(callable_obj, mode='eval')
            expr = tree.body
        except SyntaxError as e:
            raise ValueError(f"Invalid tool string syntax: {callable_obj}. Error: {e}")
        
        # Check if it is function call expression
        if not isinstance(expr, ast.Call):
            raise ValueError(f"Invalid function call: {callable_obj}")
        
        # Extract function name
        if hasattr(expr.func, 'id') and getattr(expr.func, 'id', None):
            func_name = getattr(expr.func, 'id')  # type: ignore
        elif hasattr(expr.func, 'attr') and getattr(expr.func, 'attr', None):
            func_name = getattr(expr.func, 'attr')  # type: ignore
        else:
            raise ValueError(f"Could not extract function name from {expr.func}")
        
        # Get function/class object
        try:
            # Method 1: Try to get from tool registry first
            registry = get_tool_registry()
            func = registry.get(func_name)
            if func is not None:
                # Parse positional arguments
                args = []
                for arg in expr.args:
                    args.append(ast.literal_eval(arg))
                
                # Parse keyword arguments
                kwargs = {}
                for kw in expr.keywords:
                    key = kw.arg
                    value = ast.literal_eval(kw.value)
                    kwargs[key] = value
                
                # Return tool instance directly
                if not args and not kwargs:
                    # For tool classes, instantiate them
                    if hasattr(func, '__bases__') and any('BaseTool' in str(base) for base in func.__bases__):
                        return func()
                    return func
                return func(*args, **kwargs)
            
            # Method 2: Try to get from crewai_tools (most common case)
            try:
                import crewai_tools
                func = getattr(crewai_tools, func_name, None)
                if func is not None:
                    # Parse positional arguments
                    args = []
                    for arg in expr.args:
                        args.append(ast.literal_eval(arg))
                    
                    # Parse keyword arguments
                    kwargs = {}
                    for kw in expr.keywords:
                        key = kw.arg
                        value = ast.literal_eval(kw.value)
                        kwargs[key] = value
                    
                    # Return tool instance directly
                    return func(*args, **kwargs)
            except ImportError:
                pass
            
            # Method 3: Try to get from current module globals
            # This requires the caller to have the function in their scope
            import inspect
            frame = inspect.currentframe()
            while frame:
                if func_name in frame.f_globals:
                    func = frame.f_globals[func_name]
                    
                    # If no arguments, return the function object itself
                    if not expr.args and not expr.keywords:
                        # For tool classes, instantiate them
                        if hasattr(func, '__bases__') and any('BaseTool' in str(base) for base in func.__bases__):
                            return func()
                        return func
                    
                    # If there are arguments, return the function call result
                    # Parse positional arguments
                    args = []
                    for arg in expr.args:
                        args.append(ast.literal_eval(arg))
                    
                    # Parse keyword arguments
                    kwargs = {}
                    for kw in expr.keywords:
                        key = kw.arg
                        value = ast.literal_eval(kw.value)
                        kwargs[key] = value
                    
                    # Return tool instance directly
                    return func(*args, **kwargs)
                frame = frame.f_back
            
            raise NameError(
                f"Tool '{func_name}' not found in registry, crewai_tools, or current scope. "
                f"Registered tools: {registry.list_tools()}"
            )
            
        except Exception as e:
            raise NameError(f"Tool '{func_name}' not found: {str(e)}")
    
    # Other types raise exception
    raise TypeError(
        f"Unsupported type: {type(callable_obj)}, "
        f"only support string, function, class, and object instances"
    )


__all__ = [
    "ToolRegistry",
    "get_tool_registry",
    "register_tool",
    "str_to_callable"
]


"""
Base Tool class for all tools

Compatible with CrewAI's BaseTool interface, but doesn't require crewai library.
Tools can be used independently or with CrewAI agents.
"""

from typing import Type, Optional, Any
from abc import ABC

# Try to use CrewAI's BaseTool if available, otherwise use our own implementation
try:
    from crewai.tools.base_tool import BaseTool as CrewAIBaseTool
    
    class BaseTool(CrewAIBaseTool, ABC):
        """
        Base class for all tools
        
        Compatible with CrewAI's BaseTool interface.
        If CrewAI is installed, inherits from CrewAI's BaseTool for full compatibility.
        If CrewAI is not installed, uses standalone implementation.
        
        Subclasses should implement _run() method for synchronous execution
        and optionally _arun() for asynchronous execution.
        """
        pass
    
except ImportError:
    # CrewAI not available, use standalone implementation
    from pydantic import BaseModel
    
    class BaseTool(ABC):
        """
        Base class for all tools (standalone implementation)
        
        This is used when CrewAI is not installed.
        Provides the same interface as CrewAI's BaseTool for compatibility.
        
        Subclasses should implement _run() method for synchronous execution
        and optionally _arun() for asynchronous execution.
        """
        name: str = ""
        description: str = ""
        args_schema: Optional[Type[BaseModel]] = None
        
        def _run(self, *args, **kwargs) -> Any:
            """
            Execute the tool (synchronous)
            
            Subclasses must implement this method.
            
            Args:
                *args: Positional arguments
                **kwargs: Keyword arguments
                
            Returns:
                Tool execution result
            """
            raise NotImplementedError("Subclasses must implement _run method")
        
        def run(self, *args, **kwargs) -> Any:
            """
            Public interface for running the tool
            Delegates to _run() for compatibility with CrewAI
            
            Args:
                *args: Positional arguments
                **kwargs: Keyword arguments
                
            Returns:
                Tool execution result
            """
            return self._run(*args, **kwargs)
        
        async def _arun(self, *args, **kwargs) -> Any:
            """
            Execute the tool (asynchronous) - optional
            
            Subclasses can implement this method for async execution.
            If not implemented, _run() will be used.
            
            Args:
                *args: Positional arguments
                **kwargs: Keyword arguments
                
            Returns:
                Tool execution result
            """
            raise NotImplementedError("Async execution not implemented. Use _run() instead.")
        
        async def arun(self, *args, **kwargs) -> Any:
            """
            Public interface for async tool execution
            Delegates to _arun() for compatibility with CrewAI
            
            Args:
                *args: Positional arguments
                **kwargs: Keyword arguments
                
            Returns:
                Tool execution result
            """
            return await self._arun(*args, **kwargs)


__all__ = ["BaseTool"]


"""
Extension protocols for type safety without circular dependencies

This module defines protocols (structural typing) that allow us to avoid
circular imports while maintaining type safety. Protocols define the
"shape" of objects without requiring concrete imports.
"""

from typing import Protocol, Dict, Any, runtime_checkable


@runtime_checkable
class ExecutorFactory(Protocol):
    """
    Protocol for creating executor instances
    
    This protocol allows ExtensionRegistry to work with executors
    without directly importing ExecutableTask, breaking the circular dependency.
    
    Any class that implements this protocol can be used as an executor factory.
    """
    
    def __call__(self, inputs: Dict[str, Any]) -> Any:
        """
        Create an executor instance
        
        Args:
            inputs: Input parameters for executor initialization
            
        Returns:
            Executor instance (typically ExecutableTask)
        """
        ...


@runtime_checkable
class ExecutorLike(Protocol):
    """
    Protocol for executor-like objects
    
    Defines the interface that executors must implement without
    requiring direct inheritance from ExecutableTask.
    
    This allows type checking and isinstance checks without
    importing ExecutableTask.
    """
    
    @property
    def id(self) -> str:
        """Unique identifier"""
        ...
    
    @property
    def name(self) -> str:
        """Display name"""
        ...
    
    @property
    def description(self) -> str:
        """Description"""
        ...
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the task"""
        ...
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Get input schema"""
        ...


__all__ = ["ExecutorFactory", "ExecutorLike"]


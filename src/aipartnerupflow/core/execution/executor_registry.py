"""
Executor registry for task execution

This module provides a registry system for registering and discovering task executors.
Task executors are registered by task_type (e.g., "stdio", "crewai", "rpc") and can be
looked up by TaskManager during task execution.

Supports:
- Built-in executors (stdio, crewai, etc.)
- Third-party executor registration
- ID conflict detection and error reporting
"""

from typing import Dict, Type, Optional, Callable, Any
from aipartnerupflow.core.interfaces.executable_task import ExecutableTask
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class ExecutorRegistry:
    """
    Registry for task executors
    
    This registry maps task_type strings to ExecutableTask classes or factory functions.
    TaskManager uses this registry to instantiate executors based on task schemas.
    
    Example:
        # Register built-in executor
        registry.register("system_info", SystemInfoExecutor)
        
        # Register third-party executor
        registry.register("custom", CustomExecutor)
        
        # Get executor instance
        executor = registry.get_executor("system_info", inputs={...})
    """
    
    _instance: Optional["ExecutorRegistry"] = None
    _executors: Dict[str, Type[ExecutableTask]] = {}
    _factory_functions: Dict[str, Callable[[Dict[str, Any]], ExecutableTask]] = {}
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._executors = {}
            cls._instance._factory_functions = {}
        return cls._instance
    
    def register(
        self,
        task_type: str,
        executor_class: Type[ExecutableTask],
        factory: Optional[Callable[[Dict[str, Any]], ExecutableTask]] = None,
        override: bool = False
    ) -> None:
        """
        Register an executor for a task type
        
        Args:
            task_type: Task type identifier (e.g., "stdio", "crewai", "rpc")
            executor_class: ExecutableTask class to register
            factory: Optional factory function to create executor instances.
                     If provided, this will be used instead of directly instantiating executor_class.
                     Signature: factory(inputs: Dict[str, Any]) -> ExecutableTask
            override: If True, allow overriding existing registration. Default False (raises error on conflict).
        
        Raises:
            ValueError: If task_type is already registered and override=False
            ValueError: If executor_class doesn't implement ExecutableTask
            ValueError: If executor_class.id conflicts with existing executor's id
        
        Example:
            # Register with class
            registry.register("system_info", SystemInfoExecutor)
            
            # Register with factory function
            def create_crew_executor(inputs):
                return CrewManager(agents=..., tasks=...)
            registry.register("crewai", CrewManager, factory=create_crew_executor)
        """
        # Validate executor class
        if not issubclass(executor_class, ExecutableTask):
            raise ValueError(
                f"Executor class {executor_class.__name__} must implement ExecutableTask interface"
            )
        
        # Check if task_type is already registered
        if task_type in self._executors and not override:
            existing_class = self._executors[task_type]
            raise ValueError(
                f"Task type '{task_type}' is already registered with executor '{existing_class.__name__}'. "
                f"Use override=True to replace it, or use a different task_type."
            )
        
        # Check for ID conflicts (if executor has id attribute)
        executor_id = getattr(executor_class, 'id', None)
        if executor_id:
            for registered_type, registered_class in self._executors.items():
                if registered_type != task_type:
                    registered_id = getattr(registered_class, 'id', None)
                    if registered_id == executor_id:
                        raise ValueError(
                            f"Executor ID conflict: '{executor_id}' is already used by "
                            f"task_type '{registered_type}' ({registered_class.__name__}). "
                            f"Each executor must have a globally unique ID."
                        )
        
        # Register executor
        self._executors[task_type] = executor_class
        if factory:
            self._factory_functions[task_type] = factory
        
        logger.info(
            f"Registered executor '{executor_class.__name__}' (id: {executor_id}) "
            f"for task_type '{task_type}'"
        )
    
    def get_executor(
        self,
        task_type: str,
        inputs: Optional[Dict[str, Any]] = None
    ) -> Optional[ExecutableTask]:
        """
        Get executor instance for a task type
        
        Args:
            task_type: Task type identifier
            inputs: Optional input parameters for executor initialization
        
        Returns:
            ExecutableTask instance, or None if task_type is not registered
        
        Raises:
            ValueError: If task_type is not registered
        """
        if task_type not in self._executors:
            return None
        
        executor_class = self._executors[task_type]
        
        # Use factory function if available
        if task_type in self._factory_functions:
            factory = self._factory_functions[task_type]
            return factory(inputs or {})
        
        # Otherwise, instantiate directly
        try:
            executor = executor_class(inputs=inputs or {})
            return executor
        except Exception as e:
            logger.error(f"Failed to instantiate executor '{executor_class.__name__}': {e}")
            raise
    
    def is_registered(self, task_type: str) -> bool:
        """
        Check if a task type is registered
        
        Args:
            task_type: Task type identifier
        
        Returns:
            True if registered, False otherwise
        """
        return task_type in self._executors
    
    def unregister(self, task_type: str) -> bool:
        """
        Unregister a task type
        
        Args:
            task_type: Task type identifier
        
        Returns:
            True if unregistered, False if not found
        """
        if task_type in self._executors:
            executor_class = self._executors[task_type]
            executor_id = getattr(executor_class, 'id', None)
            del self._executors[task_type]
            if task_type in self._factory_functions:
                del self._factory_functions[task_type]
            logger.info(f"Unregistered executor for task_type '{task_type}' (id: {executor_id})")
            return True
        return False
    
    def list_registered(self) -> Dict[str, str]:
        """
        List all registered task types and their executor classes
        
        Returns:
            Dictionary mapping task_type to executor class name
        """
        return {
            task_type: executor_class.__name__
            for task_type, executor_class in self._executors.items()
        }


# Global registry instance
_registry = ExecutorRegistry()


def get_registry() -> ExecutorRegistry:
    """
    Get the global executor registry instance
    
    Returns:
        ExecutorRegistry singleton instance
    """
    return _registry


def register_executor(
    task_type: str,
    executor_class: Type[ExecutableTask],
    factory: Optional[Callable[[Dict[str, Any]], ExecutableTask]] = None,
    override: bool = False
) -> None:
    """
    Register an executor (convenience function)
    
    Args:
        task_type: Task type identifier
        executor_class: ExecutableTask class to register
        factory: Optional factory function
        override: Allow overriding existing registration
    
    Example:
        from aipartnerupflow.core.execution.executor_registry import register_executor
        
        class MyExecutor(BaseTask):
            id = "my_executor"
            ...
        
        register_executor("my_type", MyExecutor)
    """
    _registry.register(task_type, executor_class, factory=factory, override=override)


__all__ = [
    "ExecutorRegistry",
    "get_registry",
    "register_executor",
]


"""
Global configuration registry for aipartnerupflow

This module provides a centralized registry for managing global configuration
like task model class and hooks. Components can access configuration without
passing parameters through multiple layers.

Industry-standard approach similar to:
- Flask's app context and extensions registry
- Django's middleware system
- FastAPI's dependency injection
- Dependency injection containers (Spring, Guice)
"""

from typing import Optional, Type, List, Callable, Union
from threading import local
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow.core.types import TaskPreHook, TaskPostHook
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

# Thread-local storage for configuration (supports multi-threaded scenarios)
_thread_local = local()


class ConfigRegistry:
    """
    Global configuration registry
    
    This class manages global configuration like:
    - Task model class
    - Pre-execution hooks
    - Post-execution hooks
    
    Uses thread-local storage to support multi-threaded scenarios.
    """
    
    def __init__(self):
        """Initialize empty registry"""
        self._task_model_class: Optional[Type[TaskModel]] = None
        self._pre_hooks: List[TaskPreHook] = []
        self._post_hooks: List[TaskPostHook] = []
        self._use_task_creator: bool = True  # Default to True for rigorous task creation
        self._require_existing_tasks: bool = False  # Default to False for convenience (auto-create)
    
    def set_task_model_class(self, task_model_class: Optional[Type[TaskModel]]) -> None:
        """
        Set the global task model class
        
        Args:
            task_model_class: Custom TaskModel class, or None for default
        """
        if task_model_class and not issubclass(task_model_class, TaskModel):
            raise TypeError(
                f"task_model_class must be a subclass of TaskModel, "
                f"got {task_model_class}"
            )
        self._task_model_class = task_model_class
        logger.debug(
            f"Set global task model class: "
            f"{task_model_class.__name__ if task_model_class else 'TaskModel'}"
        )
    
    def get_task_model_class(self) -> Type[TaskModel]:
        """
        Get the global task model class
        
        Returns:
            TaskModel class (default or custom)
        """
        return self._task_model_class or TaskModel
    
    def register_pre_hook(self, hook: TaskPreHook) -> None:
        """
        Register a pre-execution hook
        
        Args:
            hook: Pre-execution hook function (sync or async)
        """
        if hook not in self._pre_hooks:
            self._pre_hooks.append(hook)
            logger.debug(f"Registered pre-hook: {hook.__name__ if hasattr(hook, '__name__') else str(hook)}")
    
    def register_post_hook(self, hook: TaskPostHook) -> None:
        """
        Register a post-execution hook
        
        Args:
            hook: Post-execution hook function (sync or async)
        """
        if hook not in self._post_hooks:
            self._post_hooks.append(hook)
            logger.debug(f"Registered post-hook: {hook.__name__ if hasattr(hook, '__name__') else str(hook)}")
    
    def get_pre_hooks(self) -> List[TaskPreHook]:
        """
        Get all registered pre-execution hooks
        
        Returns:
            List of pre-hook functions
        """
        return self._pre_hooks.copy()
    
    def get_post_hooks(self) -> List[TaskPostHook]:
        """
        Get all registered post-execution hooks
        
        Returns:
            List of post-hook functions
        """
        return self._post_hooks.copy()
    
    def set_use_task_creator(self, use_task_creator: bool) -> None:
        """
        Set whether to use TaskCreator for rigorous task creation
        
        Args:
            use_task_creator: If True, use TaskCreator.create_task_tree_from_array for rigorous validation.
                             If False, use quick create mode (not recommended, may have issues).
                             Default is True.
        """
        self._use_task_creator = use_task_creator
        logger.debug(f"Set use_task_creator: {use_task_creator}")
    
    def get_use_task_creator(self) -> bool:
        """
        Get whether to use TaskCreator for task creation
        
        Returns:
            True if TaskCreator should be used (default), False otherwise
        """
        return self._use_task_creator
    
    def set_require_existing_tasks(self, require_existing_tasks: bool) -> None:
        """
        Set whether to require tasks to exist before execution
        
        Args:
            require_existing_tasks: If True, only execute tasks that already exist in database.
                                  If False (default), create tasks if they don't exist (more convenient).
                                  Default is False for convenience (auto-create).
        """
        self._require_existing_tasks = require_existing_tasks
        logger.debug(f"Set require_existing_tasks: {require_existing_tasks}")
    
    def get_require_existing_tasks(self) -> bool:
        """
        Get whether to require tasks to exist before execution
        
        Returns:
            True if only existing tasks should be executed, False if tasks can be auto-created (default)
        """
        return self._require_existing_tasks
    
    def clear(self) -> None:
        """Clear all configuration (useful for testing)"""
        self._task_model_class = None
        self._pre_hooks.clear()
        self._post_hooks.clear()
        self._use_task_creator = True  # Reset to default
        self._require_existing_tasks = False  # Reset to default
        logger.debug("Cleared configuration registry")


# Global registry instance (singleton pattern)
_global_registry = ConfigRegistry()


def _get_registry() -> ConfigRegistry:
    """
    Get the current configuration registry
    
    Uses a singleton pattern with global registry.
    Can be extended to support thread-local storage for multi-threaded scenarios.
    
    Returns:
        ConfigRegistry instance (global singleton)
    """
    return _global_registry


def get_config() -> ConfigRegistry:
    """
    Get the current configuration registry
    
    Returns:
        ConfigRegistry instance
    """
    return _get_registry()


def set_task_model_class(task_model_class: Optional[Type[TaskModel]]) -> None:
    """
    Set the global task model class
    
    Args:
        task_model_class: Custom TaskModel class, or None for default
    """
    _get_registry().set_task_model_class(task_model_class)


def get_task_model_class() -> Type[TaskModel]:
    """
    Get the global task model class
    
    Returns:
        TaskModel class (default or custom)
    """
    return _get_registry().get_task_model_class()


def register_pre_hook(hook: Optional[TaskPreHook] = None) -> Callable:
    """
    Register a pre-execution hook using decorator syntax
    
    Can be used as a decorator:
        @register_pre_hook
        async def my_pre_hook(task):
            ...
    
    Or called directly:
        register_pre_hook(my_pre_hook)
    
    Args:
        hook: Pre-execution hook function (sync or async), or None when used as decorator
    
    Returns:
        Hook function (for decorator usage) or None (for direct call)
    """
    def decorator(func: TaskPreHook) -> TaskPreHook:
        _get_registry().register_pre_hook(func)
        return func
    
    if hook is None:
        # Used as decorator: @register_pre_hook
        return decorator
    else:
        # Used as function call: register_pre_hook(my_hook)
        _get_registry().register_pre_hook(hook)
        return hook


def register_post_hook(hook: Optional[TaskPostHook] = None) -> Callable:
    """
    Register a post-execution hook using decorator syntax
    
    Can be used as a decorator:
        @register_post_hook
        async def my_post_hook(task, input_data, result):
            ...
    
    Or called directly:
        register_post_hook(my_post_hook)
    
    Args:
        hook: Post-execution hook function (sync or async), or None when used as decorator
    
    Returns:
        Hook function (for decorator usage) or None (for direct call)
    """
    def decorator(func: TaskPostHook) -> TaskPostHook:
        _get_registry().register_post_hook(func)
        return func
    
    if hook is None:
        # Used as decorator: @register_post_hook
        return decorator
    else:
        # Used as function call: register_post_hook(my_hook)
        _get_registry().register_post_hook(hook)
        return hook


def get_pre_hooks() -> List[TaskPreHook]:
    """
    Get all registered pre-execution hooks
    
    Returns:
        List of pre-hook functions
    """
    return _get_registry().get_pre_hooks()


def get_post_hooks() -> List[TaskPostHook]:
    """
    Get all registered post-execution hooks
    
    Returns:
        List of post-hook functions
    """
    return _get_registry().get_post_hooks()


def clear_config() -> None:
    """Clear all configuration (useful for testing)"""
    _get_registry().clear()


def set_use_task_creator(use_task_creator: bool) -> None:
    """
    Set whether to use TaskCreator for rigorous task creation
    
    Args:
        use_task_creator: If True, use TaskCreator.create_task_tree_from_array for rigorous validation.
                         If False, use quick create mode (not recommended, may have issues).
                         Default is True.
    """
    _get_registry().set_use_task_creator(use_task_creator)


def get_use_task_creator() -> bool:
    """
    Get whether to use TaskCreator for task creation
    
    Returns:
        True if TaskCreator should be used (default), False otherwise
    """
    return _get_registry().get_use_task_creator()


def set_require_existing_tasks(require_existing_tasks: bool) -> None:
    """
    Set whether to require tasks to exist before execution
    
    Args:
        require_existing_tasks: If True, only execute tasks that already exist in database.
                              If False (default), create tasks if they don't exist (more convenient).
                              Default is False for convenience (auto-create).
    """
    _get_registry().set_require_existing_tasks(require_existing_tasks)


def get_require_existing_tasks() -> bool:
    """
    Get whether to require tasks to exist before execution
    
    Returns:
        True if only existing tasks should be executed, False if tasks can be auto-created (default)
    """
    return _get_registry().get_require_existing_tasks()


__all__ = [
    "ConfigRegistry",
    "get_config",
    "register_pre_hook",
    "register_post_hook",
    "set_task_model_class",
    "get_task_model_class",
    "get_pre_hooks",
    "get_post_hooks",
    "clear_config",
    "set_use_task_creator",
    "get_use_task_creator",
    "set_require_existing_tasks",
    "get_require_existing_tasks",
]


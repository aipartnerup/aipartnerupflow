"""
Hook extension base interface

Hook extensions provide lifecycle hooks for task execution.
They extend the Extension interface and are registered with ExtensionCategory.HOOK.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from aipartnerupflow.core.extensions.base import Extension
from aipartnerupflow.core.extensions.types import ExtensionCategory
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel


class HookExtension(Extension, ABC):
    """
    Base interface for hook extensions
    
    Hook extensions provide lifecycle hooks for task execution.
    They are registered with ExtensionCategory.HOOK.
    
    Example:
        @hook_register()
        class PreExecutionHook(HookExtension):
            id = "pre_exec_hook"
            name = "Pre-Execution Hook"
            type = "pre_execution"
            
            async def execute(self, task: TaskModel) -> None:
                ...
    """
    
    @property
    def category(self) -> ExtensionCategory:
        """Extension category - always HOOK for HookExtension"""
        return ExtensionCategory.HOOK
    
    @abstractmethod
    async def execute(
        self,
        task: TaskModel,
        input_data: Optional[Dict[str, Any]] = None,
        result: Optional[Any] = None
    ) -> None:
        """
        Execute the hook
        
        Args:
            task: Task model instance
            input_data: Input data (for post hooks)
            result: Execution result (for post hooks)
        
        Note:
            - Pre hooks: input_data and result are None
            - Post hooks: input_data and result are provided
        """
        pass
    
    def is_async(self) -> bool:
        """
        Check if hook is async
        
        Returns:
            True if hook is async, False if sync
        """
        import inspect
        return inspect.iscoroutinefunction(self.execute)


__all__ = ["HookExtension"]


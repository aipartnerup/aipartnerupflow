"""
Pre-execution hook extension wrapper

Wraps existing ConfigRegistry hooks as ExtensionCategory.HOOK extensions.
"""

from typing import Dict, Any, Optional
from aipartnerupflow.core.extensions.hook import HookExtension
from aipartnerupflow.core.extensions.decorators import hook_register
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow.core.config.registry import get_pre_hooks
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


@hook_register()
class PreExecutionHookExtension(HookExtension):
    """
    Pre-execution hook extension
    
    Wraps all registered pre-execution hooks from ConfigRegistry.
    This allows hooks to be discovered and managed via ExtensionRegistry.
    """
    
    id = "pre_execution_hooks"
    name = "Pre-Execution Hooks"
    description = "Pre-execution hooks from ConfigRegistry"
    version = "1.0.0"
    
    @property
    def type(self) -> str:
        """Extension type identifier"""
        return "pre_execution"
    
    async def execute(
        self,
        task: TaskModel,
        inputs: Optional[Dict[str, Any]] = None,
        result: Optional[Any] = None
    ) -> None:
        """
        Execute all registered pre-execution hooks
        
        Args:
            task: Task model instance
            inputs: Not used for pre hooks (always None)
            result: Not used for pre hooks (always None)
        """
        hooks = get_pre_hooks()
        if not hooks:
            return
        
        import asyncio
        from inspect import iscoroutinefunction
        
        logger.debug(f"Executing {len(hooks)} pre-execution hooks for task {task.id}")
        
        for hook in hooks:
            try:
                if iscoroutinefunction(hook):
                    await hook(task)
                else:
                    # Synchronous function - run in executor to avoid blocking
                    await asyncio.to_thread(hook, task)
            except Exception as e:
                # Log error but don't fail the task execution
                logger.warning(
                    f"Pre-hook {hook.__name__ if hasattr(hook, '__name__') else str(hook)} "
                    f"failed for task {task.id}: {str(e)}. Continuing with task execution."
                )


__all__ = ["PreExecutionHookExtension"]


"""
Post-execution hook extension wrapper

Wraps existing ConfigRegistry hooks as ExtensionCategory.HOOK extensions.
"""

from typing import Dict, Any, Optional
from aipartnerupflow.core.extensions.hook import HookExtension
from aipartnerupflow.core.extensions.decorators import hook_register
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow.core.config.registry import get_post_hooks
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


@hook_register()
class PostExecutionHookExtension(HookExtension):
    """
    Post-execution hook extension
    
    Wraps all registered post-execution hooks from ConfigRegistry.
    This allows hooks to be discovered and managed via ExtensionRegistry.
    """
    
    id = "post_execution_hooks"
    name = "Post-Execution Hooks"
    description = "Post-execution hooks from ConfigRegistry"
    version = "1.0.0"
    
    @property
    def type(self) -> str:
        """Extension type identifier"""
        return "post_execution"
    
    async def execute(
        self,
        task: TaskModel,
        input_data: Optional[Dict[str, Any]] = None,
        result: Optional[Any] = None
    ) -> None:
        """
        Execute all registered post-execution hooks
        
        Args:
            task: Task model instance
            input_data: Final input data used for execution
            result: Execution result (or error information)
        """
        hooks = get_post_hooks()
        if not hooks:
            return
        
        import asyncio
        from inspect import iscoroutinefunction
        
        logger.debug(f"Executing {len(hooks)} post-execution hooks for task {task.id}")
        
        for hook in hooks:
            try:
                if iscoroutinefunction(hook):
                    await hook(task, input_data or {}, result)
                else:
                    # Synchronous function - run in executor to avoid blocking
                    await asyncio.to_thread(hook, task, input_data or {}, result)
            except Exception as e:
                # Log error but don't fail the task execution
                logger.warning(
                    f"Post-hook {hook.__name__ if hasattr(hook, '__name__') else str(hook)} "
                    f"failed for task {task.id}: {str(e)}. Continuing."
                )


__all__ = ["PostExecutionHookExtension"]


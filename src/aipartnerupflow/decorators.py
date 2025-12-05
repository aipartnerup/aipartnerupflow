"""
Unified decorators for aipartnerupflow

This module provides a single entry point for all decorators used in aipartnerupflow.
Similar to Flask's app decorators (@app.before_request, @app.route, etc.), this module
provides a clean, unified API for registering hooks and extensions.

Usage:
    from aipartnerupflow import register_pre_hook, register_post_hook, executor_register
    
    @register_pre_hook
    async def my_pre_hook(task):
        ...
    
    @register_post_hook
    async def my_post_hook(task, inputs, result):
        ...
    
    @executor_register()
    class MyExecutor(BaseTask):
        ...
"""

# Re-export configuration decorators
from aipartnerupflow.core.config import (
    register_pre_hook,
    register_post_hook,
    set_task_model_class,
    get_task_model_class,
    clear_config,
    set_use_task_creator,
    get_use_task_creator,
    set_require_existing_tasks,
    get_require_existing_tasks,
)

# Re-export extension decorators
from aipartnerupflow.core.extensions.decorators import (
    executor_register,
    storage_register,
    hook_register,
)

# Re-export tool decorator
from aipartnerupflow.core.tools.decorators import tool_register
__all__ = [
    # Hook decorators
    "register_pre_hook",
    "register_post_hook",
    # TaskModel configuration
    "set_task_model_class",
    "get_task_model_class",
    "clear_config",
    # TaskCreator configuration
    "set_use_task_creator",
    "get_use_task_creator",
    # Task execution mode configuration
    "set_require_existing_tasks",
    "get_require_existing_tasks",
    # Extension registration
    "executor_register",
    "storage_register",
    "hook_register",
    # Tool registration
    "tool_register",
]


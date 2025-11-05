"""
Configuration and registry for global settings

This module provides a centralized way to manage global configuration
like task model class, hooks, and other cross-cutting concerns.

Instead of passing parameters through multiple layers, components can
access configuration through this module.
"""

from aipartnerupflow.core.config.registry import (
    get_config,
    register_pre_hook,
    register_post_hook,
    set_task_model_class,
    get_task_model_class,
    get_pre_hooks,
    get_post_hooks,
    clear_config,
)

__all__ = [
    "get_config",
    "register_pre_hook",
    "register_post_hook",
    "set_task_model_class",
    "get_task_model_class",
    "get_pre_hooks",
    "get_post_hooks",
    "clear_config",
]


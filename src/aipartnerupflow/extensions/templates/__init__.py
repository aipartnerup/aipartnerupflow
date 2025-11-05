"""
Template-based task creation feature

This module provides template-based task creation functionality, allowing users
to create task trees from predefined templates. This is an optional feature.

Installation: pip install aipartnerupflow[templates]
"""

from aipartnerupflow.extensions.templates.task_creator import TaskCreator
from aipartnerupflow.extensions.templates.task_planner import TaskPlanner

__all__ = [
    "TaskCreator",
    "TaskPlanner",
]


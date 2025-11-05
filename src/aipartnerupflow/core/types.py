"""
Core type definitions for aipartnerupflow

This module contains core data structures and types that are shared across
different layers (execution, storage, api) to avoid circular dependencies.

These types represent the domain model of task orchestration and are not
tied to any specific implementation layer.
"""

from typing import List, Dict, Any, Union, Callable, Awaitable
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel


# ============================================================================
# Type Aliases
# ============================================================================

TaskPreHook = Callable[[TaskModel], Union[None, Awaitable[None]]]
"""
Type alias for pre-execution hook functions.

Pre-hooks are called before task execution, allowing modification of task input_data.
They receive only the TaskModel instance and can modify it in-place.

Example:
    async def my_pre_hook(task: TaskModel) -> None:
        if task.input_data is None:
            task.input_data = {}
        task.input_data["timestamp"] = datetime.now().isoformat()
"""

TaskPostHook = Callable[[TaskModel, Dict[str, Any], Any], Union[None, Awaitable[None]]]
"""
Type alias for post-execution hook functions.

Post-hooks are called after task execution completes, receiving the task,
final input data, and execution result. Useful for logging, notifications, etc.

Args:
    task: The TaskModel instance
    input_data: The final input data used for execution
    result: The execution result (or error information)

Example:
    async def my_post_hook(task: TaskModel, input_data: Dict[str, Any], result: Any) -> None:
        logger.info(f"Task {task.id} completed with result: {result}")
"""


# ============================================================================
# Task Status Constants
# ============================================================================

class TaskStatus:
    """
    Task status constants
    
    These constants represent the possible states of a task during its lifecycle.
    Use these constants instead of magic strings to ensure type safety and consistency.
    """
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    
    @classmethod
    def is_terminal(cls, status: str) -> bool:
        """
        Check if a status is terminal (task cannot transition from this state)
        
        Args:
            status: Task status string
            
        Returns:
            True if status is terminal (completed, failed, or cancelled)
        """
        return status in (cls.COMPLETED, cls.FAILED, cls.CANCELLED)
    
    @classmethod
    def is_active(cls, status: str) -> bool:
        """
        Check if a status represents an active task
        
        Args:
            status: Task status string
            
        Returns:
            True if status is pending or in_progress
        """
        return status in (cls.PENDING, cls.IN_PROGRESS)


# ============================================================================
# Task Priority
# ============================================================================

# Task Priority Notes:
# - Priority is an integer value used for task scheduling
# - TaskManager uses ASC (ascending) order following industry standard:
#   Lower numbers = Higher priority (executes earlier)
# - Recommended values (following industry standard):
#   0 = urgent (highest priority, executes first)
#   1 = high
#   2 = normal
#   3 = low (lowest priority, executes last)
# - This follows Linux kernel (nice values), POSIX, and real-time system conventions
# - If priority is None or missing, default to 999 (lowest priority, executes last)


class TaskTreeNode:
    """
    Task tree node for hierarchical task management
    
    This class represents a node in a task tree structure. It's a core data structure
    used by both the execution layer (TaskManager) and storage layer (TaskRepository)
    for building and managing task hierarchies.
    
    Attributes:
        task: The TaskModel instance associated with this node
        children: List of child TaskTreeNode instances
    
    Methods:
        add_child: Add a child node to this node
        calculate_progress: Calculate the overall progress of the task tree
        calculate_status: Calculate the overall status of the task tree
    """
    
    def __init__(self, task: TaskModel):
        """
        Initialize a task tree node
        
        Args:
            task: The TaskModel instance to associate with this node
        """
        self.task = task
        self.children: List["TaskTreeNode"] = []
    
    def add_child(self, child: "TaskTreeNode"):
        """
        Add a child node to this node
        
        Args:
            child: The TaskTreeNode to add as a child
        """
        self.children.append(child)
    
    def calculate_progress(self) -> float:
        """
        Calculate progress of the task tree
        
        Returns:
            Average progress of all child tasks (0.0 to 1.0)
            If no children, returns the task's own progress
        """
        if not self.children:
            return float(self.task.progress) if self.task.progress else 0.0
        
        total_progress = 0.0
        for child in self.children:
            total_progress += child.calculate_progress()
        
        return total_progress / len(self.children)
    
    def calculate_status(self) -> str:
        """
        Calculate overall status of the task tree
        
        Returns:
            Status string: "completed", "failed", "in_progress", or "pending"
            - "completed": All children are completed
            - "failed": At least one child has failed
            - "in_progress": At least one child is in progress
            - "pending": Otherwise
        """
        if not self.children:
            return self.task.status
        
        statuses = [child.calculate_status() for child in self.children]
        
        if all(s == "completed" for s in statuses):
            return "completed"
        elif any(s == "failed" for s in statuses):
            return "failed"
        elif any(s == "in_progress" for s in statuses):
            return "in_progress"
        else:
            return "pending"


__all__ = [
    "TaskTreeNode",
    "TaskPreHook",
    "TaskPostHook",
    "TaskStatus",
]


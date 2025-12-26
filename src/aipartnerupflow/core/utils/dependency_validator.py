"""
Dependency validation utilities for task updates

This module provides reusable functions for validating task dependencies,
including circular dependency detection and dependency reference validation.
"""

from typing import Dict, Any, List, Set, Optional
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


def detect_circular_dependencies(
    task_id: str,
    new_dependencies: List[Any],
    all_tasks_in_tree: List[TaskModel]
) -> None:
    """
    Detect circular dependencies using DFS algorithm.
    
    This function builds a dependency graph including the task being updated
    and all other tasks in the tree, then uses DFS to detect cycles.
    
    Args:
        task_id: ID of the task being updated
        new_dependencies: New dependencies list for the task
        all_tasks_in_tree: All tasks in the same task tree
        
    Raises:
        ValueError: If circular dependencies are detected
    """
    # Build dependency graph: task_id -> set of task_ids it depends on
    dependency_graph: Dict[str, Set[str]] = {}
    task_id_to_name: Dict[str, str] = {}  # For better error messages
    
    # Initialize graph with all tasks in tree
    for task in all_tasks_in_tree:
        dependency_graph[task.id] = set()
        task_id_to_name[task.id] = task.name
    
    # Add dependencies for the task being updated (using new_dependencies)
    for dep in new_dependencies:
        dep_id = None
        if isinstance(dep, dict):
            dep_id = dep.get("id")
        elif isinstance(dep, str):
            dep_id = dep
        
        if dep_id and dep_id in dependency_graph:
            dependency_graph[task_id].add(dep_id)
    
    # Add dependencies for all other tasks (using their current dependencies)
    for task in all_tasks_in_tree:
        if task.id == task_id:
            continue  # Already handled above
        
        task_deps = task.dependencies or []
        for dep in task_deps:
            dep_id = None
            if isinstance(dep, dict):
                dep_id = dep.get("id")
            elif isinstance(dep, str):
                dep_id = dep
            
            if dep_id and dep_id in dependency_graph:
                dependency_graph[task.id].add(dep_id)
    
    # DFS to detect cycles
    visited: Set[str] = set()
    
    def dfs(node: str, path: List[str]) -> Optional[List[str]]:
        """
        DFS to detect cycles.
        
        Args:
            node: Current node being visited
            path: Current path from root to this node
            
        Returns:
            Cycle path if cycle detected, None otherwise
        """
        if node in path:
            # Found a cycle - extract the cycle path
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]  # Complete the cycle
            return cycle
        
        if node in visited:
            # Already processed this node completely, no cycle from here
            return None
        
        # Mark as visited and add to current path
        visited.add(node)
        path.append(node)
        
        # Visit all dependencies
        node_deps = dependency_graph.get(node, set())
        for dep in node_deps:
            # Skip if dependency is not in the graph
            if dep not in dependency_graph:
                continue
            cycle = dfs(dep, path)
            if cycle:
                return cycle
        
        # Remove from current path (backtrack)
        path.pop()
        return None
    
    # Check all nodes for cycles
    for identifier in dependency_graph.keys():
        if identifier not in visited:
            cycle_path = dfs(identifier, [])
            if cycle_path:
                # Format cycle path with task names for better error message
                cycle_names = [task_id_to_name.get(id, id) for id in cycle_path]
                raise ValueError(
                    f"Circular dependency detected: {' -> '.join(cycle_names)}. "
                    f"Tasks cannot have circular dependencies as this would cause infinite loops."
                )


async def validate_dependency_references(
    task_id: str,
    new_dependencies: List[Any],
    task_repository: TaskRepository
) -> None:
    """
    Validate that all dependency references exist in the same task tree.
    
    Args:
        task_id: ID of the task being updated
        new_dependencies: New dependencies list for the task
        task_repository: TaskRepository instance
        
    Raises:
        ValueError: If any dependency reference is not found in the task tree
    """
    # Get the task being updated
    task = await task_repository.get_task_by_id(task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
    
    # Get root task
    root_task = await task_repository.get_root_task(task)
    
    # Get all tasks in the tree
    all_tasks_in_tree = await task_repository.get_all_tasks_in_tree(root_task)
    task_ids_in_tree = {t.id for t in all_tasks_in_tree}
    
    # Validate each dependency reference
    for dep in new_dependencies:
        dep_id = None
        if isinstance(dep, dict):
            dep_id = dep.get("id")
        elif isinstance(dep, str):
            dep_id = dep
        
        if not dep_id:
            raise ValueError(
                "Dependency must have 'id' field or be a string task ID"
            )
        
        if dep_id not in task_ids_in_tree:
            raise ValueError(
                f"Dependency reference '{dep_id}' not found in task tree"
            )


async def check_dependent_tasks_executing(
    task_id: str,
    task_repository: TaskRepository
) -> List[str]:
    """
    Check if any tasks that depend on this task are currently executing.
    
    Args:
        task_id: ID of the task being updated
        task_repository: TaskRepository instance
        
    Returns:
        List of task IDs that depend on this task and are in_progress
    """
    # Find all tasks that depend on this task
    dependent_tasks = await task_repository.find_dependent_tasks(task_id)
    
    # Filter for tasks that are in_progress
    executing_dependents = [
        t.id for t in dependent_tasks 
        if t.status == "in_progress"
    ]
    
    return executing_dependents


"""
Dependency resolution utilities for task orchestration

This module provides helper functions for resolving task dependencies,
checking dependency satisfaction, and managing dependency-related operations.
These functions can be used by TaskManager and other orchestration components.
"""

from typing import Dict, Any
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


async def are_dependencies_satisfied(
    task: TaskModel,
    task_repository: TaskRepository,
    tasks_to_reexecute: set[str]
) -> bool:
    """
    Check if all dependencies for a task are satisfied
    
    Re-execution Logic:
    - A dependency is satisfied if the dependency task is `completed`
    - Even if a dependency is marked for re-execution, if it's already `completed`,
      its result is available and can satisfy dependent tasks
    - This allows dependent tasks to proceed while still allowing re-execution
      of dependencies if needed
    
    Args:
        task: Task to check dependencies for
        task_repository: TaskRepository instance for querying tasks
        tasks_to_reexecute: Set of task IDs marked for re-execution
        
    Returns:
        True if all dependencies are satisfied, False otherwise
    """
    task_dependencies = task.dependencies or []
    if not task_dependencies:
        logger.info(f"🔍 [DEBUG] No dependencies for task {task.id}, ready to execute")
        return True
    
    # Get all completed tasks by id in the same task tree using repository
    completed_tasks_by_id = await get_completed_tasks_by_id(task, task_repository)
    logger.info(f"🔍 [DEBUG] Available tasks for {task.id}: {list(completed_tasks_by_id.keys())}")
    
    # Check each dependency
    for dep in task_dependencies:
        if isinstance(dep, dict):
            dep_id = dep.get("id")  # This is the task id of the dependency
            dep_required = dep.get("required", True)
            
            logger.info(f"🔍 [DEBUG] Checking dependency {dep_id} (required: {dep_required}) for task {task.id}")
            
            if dep_required and dep_id not in completed_tasks_by_id:
                logger.info(f"❌ Task {task.id} dependency {dep_id} not satisfied (not found in tasks: {list(completed_tasks_by_id.keys())})")
                return False
            elif dep_required and dep_id in completed_tasks_by_id:
                # Check if the dependency task is actually completed
                dep_task = completed_tasks_by_id[dep_id]
                dep_task_id = str(dep_task.id)
                # If dependency is marked for re-execution and is still in progress or pending, it's not satisfied yet
                # But if it's already completed, we can consider it satisfied (it will be re-executed but result is available)
                if dep_task_id in tasks_to_reexecute:
                    # Check current status from database to see if it's actually completed
                    # If it's completed, we can use the result even if marked for re-execution
                    if dep_task.status == "completed":
                        logger.info(f"✅ Task {task.id} dependency {dep_id} satisfied (task {dep_task.id} completed, marked for re-execution but result available)")
                    else:
                        logger.info(f"❌ Task {task.id} dependency {dep_id} is marked for re-execution and not completed yet (status: {dep_task.status})")
                        return False
                elif dep_task.status != "completed":
                    logger.info(f"❌ Task {task.id} dependency {dep_id} found but not completed (status: {dep_task.status})")
                    return False
                else:
                    logger.info(f"✅ Task {task.id} dependency {dep_id} satisfied (task {dep_task.id} completed)")
        elif isinstance(dep, str):
            # Simple string dependency (just the id) - backward compatibility
            dep_id = dep
            if dep_id not in completed_tasks_by_id:
                logger.info(f"❌ Task {task.id} dependency {dep_id} not satisfied")
                return False
            dep_task = completed_tasks_by_id[dep_id]
            dep_task_id = str(dep_task.id)
            # If dependency is marked for re-execution, check if it's actually completed
            if dep_task_id in tasks_to_reexecute:
                # If it's completed, we can use the result even if marked for re-execution
                if dep_task.status == "completed":
                    logger.info(f"✅ Task {task.id} dependency {dep_id} satisfied (task {dep_task.id} completed, marked for re-execution but result available)")
                else:
                    logger.info(f"❌ Task {task.id} dependency {dep_id} is marked for re-execution and not completed yet (status: {dep_task.status})")
                    return False
            elif dep_task.status != "completed":
                logger.info(f"❌ Task {task.id} dependency {dep_id} found but not completed (status: {dep_task.status})")
                return False
            else:
                logger.info(f"✅ Task {task.id} dependency {dep_id} satisfied (task {dep_task.id} completed)")
    
    logger.info(f"✅ All dependencies satisfied for task {task.id}")
    return True


async def resolve_task_dependencies(
    task: TaskModel,
    task_repository: TaskRepository
) -> Dict[str, Any]:
    """
    Resolve task dependencies by merging results from dependency tasks
    
    Args:
        task: Task to resolve dependencies for
        task_repository: TaskRepository instance for querying tasks
        
    Returns:
        Resolved input data dictionary
    """
    inputs = task.inputs.copy() if task.inputs else {}
    
    # Get task dependencies from the dependencies field
    task_dependencies = task.dependencies or []
    if not task_dependencies:
        logger.debug(f"No dependencies found for task {task.id}")
        return inputs
    
    # Get all completed tasks by id in the same task tree
    completed_tasks_by_id = await get_completed_tasks_by_id(task, task_repository)
    
    logger.info(f"🔍 [Dependency Resolution] Task {task.id} (name: {task.name}) has dependencies: {task_dependencies}")
    logger.info(f"🔍 [Dependency Resolution] Available completed tasks: {list(completed_tasks_by_id.keys())}")
    logger.info(f"🔍 [Dependency Resolution] Initial inputs: {inputs}")
    
    # Resolve dependencies based on id
    for dep in task_dependencies:
        if isinstance(dep, dict):
            dep_id = dep.get("id")  # This is the task id of the dependency
            dep_type = dep.get("type", "result")
            dep_required = dep.get("required", True)
            
            logger.info(f"🔍 [Dependency Resolution] Processing dependency: {dep_id} (type: {dep_type}, required: {dep_required})")
            
            if dep_id in completed_tasks_by_id:
                # Found the dependency task, get its result
                source_task = completed_tasks_by_id[dep_id]
                source_result = source_task.result
                
                logger.info(f"🔍 [Dependency Resolution] Found dependency {dep_id} in task {source_task.id}")
                
                if source_result is not None:
                    # Check if we need to map dependency result fields to input parameters
                    if isinstance(source_result, dict):
                        # Check if the result is nested in a 'result' field
                        actual_result = source_result
                        if "result" in source_result and isinstance(source_result["result"], dict):
                            actual_result = source_result["result"]
                            logger.info(f"🔍 [Dependency Resolution] Using nested result from {dep_id}: {actual_result}")
                        else:
                            # Direct result structure
                            logger.info(f"🔍 [Dependency Resolution] Using direct result from {dep_id}: {actual_result}")
                        
                        # Get the input schema for this task to determine which fields to map
                        input_schema = {}
                        if task.schemas and isinstance(task.schemas, dict):
                            input_schema = task.schemas.get("input_schema", {})
                        
                        logger.info(f"🔍 [Dependency Resolution] Input schema for task {task.id}: {input_schema}")
                        
                        if input_schema and "properties" in input_schema:
                            # Map dependency result fields to input parameters based on input_schema
                            schema_properties = input_schema["properties"]
                            mapped_count = 0
                            
                            logger.info(f"🔍 [Dependency Resolution] Schema properties: {list(schema_properties.keys())}")
                            logger.info(f"🔍 [Dependency Resolution] Available result fields: {list(actual_result.keys())}")
                            
                            for field_name, field_schema in schema_properties.items():
                                if field_name in actual_result:
                                    inputs[field_name] = actual_result[field_name]
                                    mapped_count += 1
                                    logger.info(f"✅ Mapped {field_name} from {dep_id} result: {actual_result[field_name]}")
                            
                            logger.info(f"✅ Resolved {dep_id} dependency for task {task.id} with {mapped_count} fields")
                            logger.info(f"🔍 [Dependency Resolution] Final inputs after mapping: {inputs}")
                        else:
                            # No input schema or properties found, use the result as-is
                            inputs[dep_id] = source_result
                            logger.debug(f"✅ Resolved dependency {dep_id} with result from task {source_task.id} (no schema mapping)")
                    else:
                        # For non-dict results, use the result as-is
                        inputs[dep_id] = source_result
                        logger.debug(f"✅ Resolved dependency {dep_id} with result from task {source_task.id}")
                else:
                    logger.warning(f"⚠️ Task {source_task.id} completed but has no result for dependency {dep_id}")
                    if dep_required:
                        logger.error(f"❌ Required dependency {dep_id} not resolved for task {task.id}")
            else:
                logger.warning(f"⚠️ Could not resolve dependency {dep_id} for task {task.id} - no completed task found with id {dep_id}")
                if dep_required:
                    logger.error(f"❌ Required dependency {dep_id} not resolved for task {task.id}")
        elif isinstance(dep, str):
            # Simple string dependency (just the id) - backward compatibility
            dep_id = dep
            if dep_id in completed_tasks_by_id:
                source_task = completed_tasks_by_id[dep_id]
                if source_task.result:
                    if isinstance(source_task.result, dict):
                        inputs.update(source_task.result)
                    else:
                        inputs[dep_id] = source_task.result
    
    logger.info(f"🔍 [Dependency Resolution] Final resolved inputs for task {task.id}: {inputs}")
    return inputs


async def get_completed_tasks_by_id(
    task: TaskModel,
    task_repository: TaskRepository
) -> Dict[str, TaskModel]:
    """
    Get all completed tasks in the same task tree by id
    
    Args:
        task: Task to get sibling tasks for
        task_repository: TaskRepository instance for querying tasks
        
    Returns:
        Dictionary mapping task ids to completed TaskModel instances
    """
    # Get root task to find all tasks in the tree
    root_task = await task_repository.get_root_task(task)
    
    # Get all tasks in the tree
    all_tasks = await task_repository.get_all_tasks_in_tree(root_task)
    
    # Filter completed tasks with results
    completed_tasks = [
        t for t in all_tasks 
        if t.status == "completed" and t.result is not None
    ]
    
    # Create a map of completed tasks by id
    completed_tasks_by_id = {t.id: t for t in completed_tasks}
    
    return completed_tasks_by_id


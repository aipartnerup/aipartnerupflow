"""
Task management service for orchestrating and executing tasks
"""

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union, Callable, Awaitable
import asyncio
from decimal import Decimal
from inspect import iscoroutinefunction
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
from aipartnerupflow.core.execution.streaming_callbacks import StreamingCallbacks
from aipartnerupflow.core.extensions import get_registry, ExtensionCategory
from aipartnerupflow.core.types import (
    TaskTreeNode,
    TaskPreHook,
    TaskPostHook,
    TaskStatus,
)
from aipartnerupflow.core.config import get_pre_hooks, get_post_hooks, get_task_model_class
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class TaskManager:
    """Unified task management service - handles orchestration, distribution, and execution"""
    
    def __init__(
        self,
        db: Union[Session, AsyncSession],
        root_task_id: Optional[str] = None,
        pre_hooks: Optional[List[TaskPreHook]] = None,
        post_hooks: Optional[List[TaskPostHook]] = None
    ):
        """
        Initialize TaskManager
        
        Args:
            db: Database session (sync or async)
            root_task_id: Optional root task ID for streaming
            pre_hooks: Optional list of pre-execution hook functions
                Each hook receives (task: TaskModel)
                Hooks can access and modify task.input_data directly
                Hooks can be sync or async functions
                Example:
                    async def my_pre_hook(task):
                        # Custom validation or transformation
                        if task.input_data and task.input_data.get("url"):
                            task.input_data["url"] = task.input_data["url"].strip()
                    task_manager = TaskManager(db, pre_hooks=[my_pre_hook])
            post_hooks: Optional list of post-execution hook functions
                Each hook receives (task: TaskModel, input_data: Dict[str, Any], result: Any)
                Hooks can be sync or async functions
                Example:
                    async def my_post_hook(task, input_data, result):
                        # Custom result processing or logging
                        logger.info(f"Task {task.id} completed with result: {result}")
                    task_manager = TaskManager(db, post_hooks=[my_post_hook])
        """
        self.db = db
        self.is_async = isinstance(db, AsyncSession)
        self.root_task_id = root_task_id
        # Get task_model_class from config registry (supports custom TaskModel via decorators)
        task_model_class = get_task_model_class() or TaskModel
        self.task_repository = TaskRepository(db, task_model_class=task_model_class)
        self.streaming_callbacks = StreamingCallbacks(root_task_id=self.root_task_id)
        self.stream = False
        self.streaming_final = False
        # Use provided hooks or fall back to config registry
        # This allows hooks to be registered globally via decorators
        self.pre_hooks = pre_hooks if pre_hooks is not None else get_pre_hooks()
        self.post_hooks = post_hooks if post_hooks is not None else get_post_hooks()

    
    async def distribute_task_tree(
        self,
        task_tree: TaskTreeNode,
        use_callback: bool = True
    ) -> TaskTreeNode:
        """
        Distribute task tree directly with proper multi-level priority execution
        
        Args:
            task_tree: Root task tree node
            use_callback: Whether to use callbacks
            
        Returns:
            Task tree node with execution results
        """
        logger.info(f"Distributing task tree with root task: {task_tree.task.id}")
        
        await self._execute_task_tree_recursive(task_tree, use_callback)
        
        return task_tree
    
    async def distribute_task_tree_with_streaming(
        self,
        task_tree: TaskTreeNode,
        use_callback: bool = True
    ) -> None:
        """
        Distribute task tree with real-time streaming for progress updates
        
        Args:
            task_tree: Root task tree node
            use_callback: Whether to use callbacks
        """
        logger.info(f"Distributing task tree with streaming, root task: {task_tree.task.id}")
        
        # Enable streaming mode and set root task ID
        self.stream = True
        self.streaming_final = False
        self.root_task_id = task_tree.task.id
        
        try:
            # Send initial status
            self.streaming_callbacks.progress(task_tree.task.id, 0.0, "Task tree execution started")
            
            # Execute task tree with progress streaming
            await self._execute_task_tree_recursive(task_tree, use_callback)
            
            # Check final status
            final_progress = task_tree.calculate_progress()
            final_status = task_tree.calculate_status()
            
            # Ensure progress is a float
            if isinstance(final_progress, Decimal):
                final_progress = float(final_progress)
            
            # Send final status if all tasks are completed
            if final_status == "completed":
                self.streaming_callbacks.final(
                    task_tree.task.id,
                    final_status,
                    result={"progress": final_progress}
                )
            else:
                # Send progress update
                self.streaming_callbacks.progress(
                    task_tree.task.id,
                    final_progress,
                    f"Task tree execution {final_status}"
                )
                
        except Exception as e:
            logger.error(f"Error in distribute_task_tree_with_streaming: {str(e)}")
            self.streaming_callbacks.task_failed(task_tree.task.id, str(e))
    
    async def _execute_task_tree_recursive(
        self,
        node: TaskTreeNode,
        use_callback: bool = True
    ) -> None:
        """
        Execute task tree recursively with proper dependency checking
        
        Args:
            node: Task tree node to execute
            use_callback: Whether to use callbacks
        """
        try:
            # Check if streaming has been marked as final
            if self.streaming_final:
                logger.info(f"Streaming marked as final, stopping task tree execution for {node.task.id}")
                return
                
            if node.task.status in ["completed", "failed", "in_progress"]:
                logger.info(f"Task {node.task.id} already {node.task.status}, skipping distribution")
                return
            
            # Execute tasks in proper hierarchical order
            has_completed_children = True
            if node.children:
                for child in node.children:
                    if child.task.status not in ["completed", "failed"]:
                        has_completed_children = False
                        break
            
            if has_completed_children and node.task.status != "completed":
                logger.debug(f"All children for task {node.task.id} are completed, executing the task itself")
                await self._execute_single_task(node.task, use_callback)
                return
            
            # Group children by priority
            priority_groups = {}
            for child_node in node.children:
                priority = child_node.task.priority or 999
                if priority not in priority_groups:
                    priority_groups[priority] = []
                if child_node.task.status not in ["completed", "failed"]:
                    priority_groups[priority].append(child_node)
                    self._add_children_to_priority_groups(child_node, priority_groups)
            
            if not priority_groups:
                logger.debug(f"No children for task {node.task.id} to execute")
                return
            
            # Sort priorities in ascending order (lower numbers = higher priority)
            # Industry standard: smaller numbers execute first (higher priority)
            sorted_priorities = sorted(priority_groups.keys())
            logger.debug(f"Executing {len(node.children)} children for task {node.task.id} in {len(sorted_priorities)} priority groups")
            
            for priority in sorted_priorities:
                children_with_same_priority = priority_groups[priority]
                logger.debug(f"Processing {len(children_with_same_priority)} tasks with priority {priority}")
                
                # Check dependencies
                ready_tasks = []
                waiting_tasks = []
                
                for child_node in children_with_same_priority:
                    child_task = child_node.task
                    deps_satisfied = await self._are_dependencies_satisfied(child_task)
                    if deps_satisfied:
                        ready_tasks.append(child_node)
                    else:
                        waiting_tasks.append(child_node)
                
                # Execute ready tasks
                if ready_tasks:
                    if len(ready_tasks) == 1:
                        # Single task - execute directly
                        child_node = ready_tasks[0]
                        await self._execute_single_task(child_node.task, use_callback)
                        await self._execute_task_tree_recursive(child_node, use_callback)
                    else:
                        # Multiple tasks - execute in parallel
                        logger.debug(f"Executing {len(ready_tasks)} ready tasks in parallel with priority {priority}")
                        
                        async def execute_child_and_children(child_node):
                            await self._execute_single_task(child_node.task, use_callback)
                            await self._execute_task_tree_recursive(child_node, use_callback)
                        
                        parallel_tasks = [
                            execute_child_and_children(child_node)
                            for child_node in ready_tasks
                        ]
                        
                        await asyncio.gather(*parallel_tasks)
                        logger.debug(f"Completed parallel execution of {len(ready_tasks)} ready tasks")
                
                # Waiting tasks will be triggered by callbacks when dependencies are satisfied
                if waiting_tasks:
                    logger.debug(f"Leaving {len(waiting_tasks)} tasks waiting for dependencies")
                    
        except Exception as e:
            logger.error(f"Error in _execute_task_tree_recursive for task {node.task.id}: {str(e)}")
            try:
                # Update task status using repository
                await self.task_repository.update_task_status(
                    task_id=node.task.id,
                    status="failed",
                    error=str(e),
                    completed_at=datetime.now(timezone.utc)
                )
            except Exception as db_error:
                logger.error(f"Error updating task status in database: {str(db_error)}")
            raise
    
    def _add_children_to_priority_groups(
        self,
        node: TaskTreeNode,
        priority_groups: Dict[int, List[TaskTreeNode]]
    ):
        """Recursively add all children to priority groups"""
        for child_node in node.children:
            priority = child_node.task.priority or 999
            if priority not in priority_groups:
                priority_groups[priority] = []
            if child_node.task.status not in ["completed", "failed"]:
                priority_groups[priority].append(child_node)
                self._add_children_to_priority_groups(child_node, priority_groups)
    
    async def _are_dependencies_satisfied(self, task: TaskModel) -> bool:
        """
        Check if all dependencies for a task are satisfied
        
        Args:
            task: Task to check dependencies for
            
        Returns:
            True if all dependencies are satisfied, False otherwise
        """
        task_dependencies = task.dependencies or []
        if not task_dependencies:
            logger.info(f"🔍 [DEBUG] No dependencies for task {task.id}, ready to execute")
            return True
        
        # Get all completed tasks by id in the same task tree using repository
        completed_tasks_by_id = await self._get_completed_tasks_by_id(task)
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
                    if dep_task.status != "completed":
                        logger.info(f"❌ Task {task.id} dependency {dep_id} found but not completed (status: {dep_task.status})")
                        return False
                    logger.info(f"✅ Task {task.id} dependency {dep_id} satisfied (task {dep_task.id} completed)")
            elif isinstance(dep, str):
                # Simple string dependency (just the id) - backward compatibility
                dep_id = dep
                if dep_id not in completed_tasks_by_id:
                    logger.info(f"❌ Task {task.id} dependency {dep_id} not satisfied")
                    return False
                dep_task = completed_tasks_by_id[dep_id]
                if dep_task.status != "completed":
                    logger.info(f"❌ Task {task.id} dependency {dep_id} found but not completed (status: {dep_task.status})")
                    return False
        
        logger.info(f"✅ All dependencies satisfied for task {task.id}")
        return True
    
    async def _execute_single_task(
        self,
        task: TaskModel,
        use_callback: bool = True
    ):
        """
        Execute a single task
        
        Args:
            task: Task to execute
            use_callback: Whether to use callbacks
        """
        try:
            # Check if streaming has been marked as final
            if self.streaming_final:
                logger.info(f"Streaming marked as final, stopping single task execution for {task.id}")
                return
                
            if task.status in ["completed", "failed", "in_progress"]:
                logger.info(f"Task {task.id} already {task.status}, skipping execution")
                return
            
            # Send task start status if streaming is enabled
            if self.stream:
                self.streaming_callbacks.task_start(task.id)
            
            # Update task status to in_progress using repository
            await self.task_repository.update_task_status(
                task_id=task.id,
                status="in_progress",
                error=None,
                started_at=datetime.now(timezone.utc)
            )
            # Refresh task object
            task = await self.task_repository.get_task_by_id(task.id)
            if not task:
                raise ValueError(f"Task {task.id} not found after status update")
            logger.info(f"Task {task.id} status updated to in_progress")
            
            # Resolve dependencies first (merge dependency results into input_data)
            resolved_input_data = await self._resolve_task_dependencies(task)
            
            if resolved_input_data != (task.input_data or {}):
                # Update input data using repository
                await self.task_repository.update_task_input_data(task.id, resolved_input_data)
                # Refresh task object
                task = await self.task_repository.get_task_by_id(task.id)
                if not task:
                    raise ValueError(f"Task {task.id} not found after input data update")
            
            # Execute pre-hooks (after dependency resolution, to allow user adjustment based on complete data)
            # Pre-hooks can access and modify task.input_data directly
            # Store input_data before pre-hooks to detect changes (deep copy for nested dicts)
            import copy
            input_data_before_pre_hooks = copy.deepcopy(task.input_data) if task.input_data else {}
            await self._execute_pre_hooks(task)
            
            # Update input data if pre-hooks modified task.input_data
            # Use deep comparison to detect any changes (including nested dict modifications)
            input_data_after_pre_hooks = task.input_data or {}
            # Deep comparison to detect changes in nested structures
            if input_data_after_pre_hooks != input_data_before_pre_hooks:
                # Pre-hooks modified input_data, update database
                # Make a deep copy to ensure we're saving the current state
                input_data_to_save = copy.deepcopy(input_data_after_pre_hooks) if input_data_after_pre_hooks else {}
                logger.info(
                    f"Pre-hooks modified input_data for task {task.id}: "
                    f"before_keys={list(input_data_before_pre_hooks.keys())}, "
                    f"after_keys={list(input_data_after_pre_hooks.keys())}"
                )
                await self.task_repository.update_task_input_data(task.id, input_data_to_save)
                # Refresh task object to get latest state from database
                task = await self.task_repository.get_task_by_id(task.id)
                if not task:
                    raise ValueError(f"Task {task.id} not found after pre-hook input data update")
                logger.info(f"Pre-hooks modified input_data for task {task.id}, updated in database")
            else:
                logger.debug(f"Pre-hooks did not modify input_data for task {task.id}")
            
            # Execute task using agent executor
            # Use task.input_data (which may have been modified by pre-hooks)
            final_input_data = task.input_data or {}
            logger.info(f"Task {task.id} execution - calling agent executor (name: {task.name})")
            
            # Execute task based on schemas
            task_result = await self._execute_task_with_schemas(task, final_input_data)
            
            # Update task status using repository
            await self.task_repository.update_task_status(
                task_id=task.id,
                status="completed",
                progress=1.0,
                result=task_result,
                completed_at=datetime.now(timezone.utc)
            )
            # Refresh task object
            task = await self.task_repository.get_task_by_id(task.id)
            if not task:
                raise ValueError(f"Task {task.id} not found after completion update")
            
            if self.stream:
                self.streaming_callbacks.task_completed(task.id, result=task.result)
            
            # System-internal dependency task triggering
            # execute_after_task is always executed to trigger dependent tasks
            # This is independent of use_callback (which controls external URL notifications)
            # Post-hooks will be executed in execute_after_task BEFORE triggering dependent tasks
            # This ensures immediate response for notifications/logging without waiting for dependencies
            try:
                await self.execute_after_task(task)
            except Exception as e:
                logger.error(f"Error triggering dependent tasks for {task.id}: {str(e)}")
                # Don't fail the current task if dependency triggering fails
            
            # Note: use_callback is for external URL callback notifications (if configured)
            # It doesn't affect execute_after_task which handles internal dependency triggering
                
        except Exception as e:
            logger.error(f"Error executing task {task.id}: {str(e)}", exc_info=True)
            
            # Update task status using repository
            await self.task_repository.update_task_status(
                task_id=task.id,
                status="failed",
                error=str(e),
                completed_at=datetime.now(timezone.utc)
            )
            
            if self.stream:
                self.streaming_callbacks.task_failed(task.id, str(e))
    
    async def _execute_pre_hooks(self, task: TaskModel) -> None:
        """
        Execute pre-execution hooks
        
        Args:
            task: Task to execute (hooks can access and modify task.input_data)
            
        Note:
            Pre-hooks are executed after dependency resolution, so task.input_data
            contains the complete resolved data including dependency results.
            Hooks can modify task.input_data directly.
        """
        if not self.pre_hooks:
            return
        
        logger.debug(f"Executing {len(self.pre_hooks)} pre-hooks for task {task.id}")
        
        for hook in self.pre_hooks:
            try:
                if iscoroutinefunction(hook):
                    await hook(task)
                else:
                    # Synchronous function - run in executor to avoid blocking
                    await asyncio.to_thread(hook, task)
            except Exception as e:
                # Log error but don't fail the task execution
                logger.warning(
                    f"Pre-hook {hook.__name__} failed for task {task.id}: {str(e)}. "
                    f"Continuing with task execution."
                )
    
    async def _execute_post_hooks(
        self,
        task: TaskModel,
        input_data: Dict[str, Any],
        result: Any
    ) -> None:
        """
        Execute post-execution hooks
        
        Args:
            task: Task that was executed
            input_data: Input data used for execution
            result: Task execution result
        """
        if not self.post_hooks:
            return
        
        logger.debug(f"Executing {len(self.post_hooks)} post-hooks for task {task.id}")
        
        for hook in self.post_hooks:
            try:
                if iscoroutinefunction(hook):
                    await hook(task, input_data, result)
                else:
                    # Synchronous function - run in executor to avoid blocking
                    await asyncio.to_thread(hook, task, input_data, result)
            except Exception as e:
                # Log error but don't fail the task execution
                logger.warning(
                    f"Post-hook {hook.__name__} failed for task {task.id}: {str(e)}. "
                    f"Task execution already completed."
                )
    
    async def _resolve_task_dependencies(self, task: TaskModel) -> Dict[str, Any]:
        """
        Resolve task dependencies by merging results from dependency tasks
        
        Args:
            task: Task to resolve dependencies for
            
        Returns:
            Resolved input data dictionary
        """
        input_data = task.input_data.copy() if task.input_data else {}
        
        # Get task dependencies from the dependencies field
        task_dependencies = task.dependencies or []
        if not task_dependencies:
            logger.debug(f"No dependencies found for task {task.id}")
            return input_data
        
        # Get all completed tasks by id in the same task tree
        completed_tasks_by_id = await self._get_completed_tasks_by_id(task)
        
        logger.info(f"🔍 [Dependency Resolution] Task {task.id} (name: {task.name}) has dependencies: {task_dependencies}")
        logger.info(f"🔍 [Dependency Resolution] Available completed tasks: {list(completed_tasks_by_id.keys())}")
        logger.info(f"🔍 [Dependency Resolution] Initial input_data: {input_data}")
        
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
                                        input_data[field_name] = actual_result[field_name]
                                        mapped_count += 1
                                        logger.info(f"✅ Mapped {field_name} from {dep_id} result: {actual_result[field_name]}")
                                
                                logger.info(f"✅ Resolved {dep_id} dependency for task {task.id} with {mapped_count} fields")
                                logger.info(f"🔍 [Dependency Resolution] Final input_data after mapping: {input_data}")
                            else:
                                # No input schema or properties found, use the result as-is
                                input_data[dep_id] = source_result
                                logger.debug(f"✅ Resolved dependency {dep_id} with result from task {source_task.id} (no schema mapping)")
                        else:
                            # For non-dict results, use the result as-is
                            input_data[dep_id] = source_result
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
                            input_data.update(source_task.result)
                        else:
                            input_data[dep_id] = source_task.result
        
        logger.info(f"🔍 [Dependency Resolution] Final resolved input_data for task {task.id}: {input_data}")
        return input_data
    
    async def _get_completed_tasks_by_id(self, task: TaskModel) -> Dict[str, TaskModel]:
        """
        Get all completed tasks in the same task tree by id
        
        Args:
            task: Task to get sibling tasks for
            
        Returns:
            Dictionary mapping task ids to completed TaskModel instances
        """
        # Get root task to find all tasks in the tree
        root_task = await self._get_root_task(task)
        
        # Get all tasks in the tree
        all_tasks = await self._get_all_tasks_in_tree(root_task)
        
        # Filter completed tasks with results
        completed_tasks = [
            t for t in all_tasks 
            if t.status == "completed" and t.result is not None
        ]
        
        # Create a map of completed tasks by id
        completed_tasks_by_id = {t.id: t for t in completed_tasks}
        
        return completed_tasks_by_id
    
    async def _get_root_task(self, task: TaskModel) -> TaskModel:
        """Get root task of the task tree"""
        # Use repository method
        return await self.task_repository.get_root_task(task)
    
    async def _get_all_tasks_in_tree(self, root_task: TaskModel) -> List[TaskModel]:
        """
        Get all tasks in the task tree (recursive)
        
        Args:
            root_task: Root task of the tree
            
        Returns:
            List of all tasks in the tree
        """
        # Use repository method
        return await self.task_repository.get_all_tasks_in_tree(root_task)
    
    async def execute_after_task(self, completed_task: TaskModel):
        """
        Execute after task completion - execute post-hooks and trigger dependent tasks
        
        Args:
            completed_task: Task that just completed
            
        Note:
            Post-hooks are executed FIRST (before triggering dependent tasks) to ensure
            immediate response for notifications, logging, etc. This allows:
            - Immediate notification of task completion
            - Fast logging and data export
            - Better user experience (no waiting for dependent tasks)
            
            If you need dependent task results in post-hooks, handle it in the
            dependent task's own post-hooks instead.
        """
        try:
            # Check if task is actually completed
            if completed_task.status != "completed":
                return
            
            # Execute post-hooks FIRST (before triggering dependent tasks)
            # This ensures immediate response and doesn't wait for dependent tasks
            refreshed_task = await self.task_repository.get_task_by_id(completed_task.id)
            if refreshed_task and refreshed_task.status == "completed":
                # Get the input_data that was used for execution
                # This should include pre-hook modifications since they were saved to DB
                # Use refreshed_task.input_data which contains the latest data from database
                logger.info(
                    f"Loading task {completed_task.id} from DB for post-hook: "
                    f"input_data_type={type(refreshed_task.input_data)}, "
                    f"input_data_keys={list(refreshed_task.input_data.keys()) if refreshed_task.input_data else []}, "
                    f"input_data_value={refreshed_task.input_data}"
                )
                input_data = refreshed_task.input_data or {}
                result = refreshed_task.result
                
                # Ensure we're passing the actual input_data dict (not a reference that might be stale)
                # Make a copy to ensure we're passing the current state
                # If input_data is already a dict, create a shallow copy; otherwise convert to dict
                if isinstance(input_data, dict):
                    input_data = dict(input_data)
                else:
                    # Handle case where input_data might be a JSON string or other type
                    input_data = dict(input_data) if input_data else {}
                
                logger.info(
                    f"Post-hook input_data for task {refreshed_task.id}: "
                    f"keys={list(input_data.keys())}, has_pre_hook_marker={input_data.get('_pre_hook_executed', False)}, "
                    f"input_data_type={type(input_data)}, input_data_value={input_data}"
                )
                
                await self._execute_post_hooks(refreshed_task, input_data, result)
            else:
                logger.warning(f"Task {completed_task.id} not found or not completed, skipping post-hooks")
            
            logger.info(f"🔍 Checking for dependent tasks after completion of {completed_task.id} (name: {completed_task.name})")
            
            # Get all tasks in the tree
            root_task = await self._get_root_task(completed_task)
            all_tasks = await self._get_all_tasks_in_tree(root_task)
            
            # Find tasks that are waiting and might have their dependencies satisfied
            waiting_tasks = [
                t for t in all_tasks 
                if t.status in ["pending", "in_progress"] and t.id != completed_task.id
            ]
            
            # Trigger dependent tasks if any
            if waiting_tasks:
                logger.info(f"Found {len(waiting_tasks)} waiting tasks to check for dependencies")
                
                # Check each waiting task to see if its dependencies are now satisfied
                triggered_tasks = []
                for task in waiting_tasks:
                    logger.debug(f"Checking dependencies for task {task.id} (name: {task.name})")
                    deps_satisfied = await self._are_dependencies_satisfied(task)
                    
                    if deps_satisfied:
                        logger.info(f"🚀 Task {task.id} (name: {task.name}) dependencies now satisfied, executing")
                        triggered_tasks.append(task)
                        try:
                            await self._execute_single_task(task, use_callback=True)
                        except Exception as e:
                            logger.error(f"❌ Failed to execute dependent task {task.id}: {str(e)}")
                            # Update task status using repository
                            await self.task_repository.update_task_status(
                                task_id=task.id,
                                status="failed",
                                error=str(e)
                            )
                    else:
                        logger.debug(f"Task {task.id} (name: {task.name}) dependencies not yet satisfied")
                
                if triggered_tasks:
                    logger.info(f"Successfully triggered {len(triggered_tasks)} dependent tasks")
                else:
                    logger.debug("No tasks were triggered by this completion")
            else:
                logger.debug("No waiting tasks found")
        except Exception as e:
            logger.error(f"Error in execute_after_task for {completed_task.id}: {str(e)}", exc_info=True)
    
    async def _execute_task_with_schemas(
        self,
        task: TaskModel,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute task based on schemas configuration
        
        Uses the executor registry to find and instantiate the appropriate executor
        based on task_type in schemas. Supports both built-in and third-party executors.
        
        Args:
            task: Task to execute
            input_data: Input data for task execution
            
        Returns:
            Task execution result
            
        Raises:
            ValueError: If task_type is not registered in executor registry
        """
        schemas = task.schemas or {}
        task_type = schemas.get("type")  # Optional: only used if method is not an executor id
        task_method = schemas.get("method", "command")
        
        logger.info(f"Executing task {task.id} with type={task_type}, method={task_method}")
        
        # Get executor from unified extension registry
        registry = get_registry()
        
        # Strategy: Try to use method as executor id first, then fall back to type-based lookup
        # This allows:
        # 1. Direct id-based lookup: method="crewai_executor" (no type needed)
        # 2. Type-based lookup: type="stdio", method="command" (method is execution method, not id)
        extension_id = None
        extension = None
        
        # First, try to use method as executor id
        if task_method:
            extension = registry.get_by_id(task_method)
            if extension and extension.category == ExtensionCategory.EXECUTOR:
                extension_id = task_method
                logger.debug(f"Using method '{task_method}' as executor id (type not needed)")
        
        # If method is not an executor id, fall back to type-based lookup
        if extension is None or (extension and extension.category != ExtensionCategory.EXECUTOR):
            if not task_type:
                # If no type specified and method is not an executor id, use default
                task_type = "stdio"
                logger.debug(f"No type specified, defaulting to 'stdio'")
            extension = registry.get_by_type(ExtensionCategory.EXECUTOR, task_type)
            if extension:
                extension_id = extension.id
                logger.debug(f"Using type '{task_type}' to find executor '{extension_id}'")
        
        if extension is None or extension.category != ExtensionCategory.EXECUTOR:
            # Task type not registered
            registered_extensions = registry.list_by_category(ExtensionCategory.EXECUTOR)
            error_msg = (
                f"Task executor not found. "
                f"type='{task_type}', method='{task_method}'. "
                f"Registered executor types: {[ext.type for ext in registry.get_all_by_category(ExtensionCategory.EXECUTOR) if ext.type]}. "
                f"Registered executor ids: {registry.list_by_category(ExtensionCategory.EXECUTOR)}. "
                f"Please register an executor for this task type using "
                f"register_extension(YourExecutorInstance, executor_class=YourExecutorClass)."
            )
            logger.error(error_msg)
            return {
                "error": error_msg,
                "task_id": task.id,
                "name": task.name,
                "task_type": task_type,
                "task_method": task_method,
                "registered_types": [ext.type for ext in registry.get_all_by_category(ExtensionCategory.EXECUTOR) if ext.type],
                "registered_ids": registry.list_by_category(ExtensionCategory.EXECUTOR),
                "input_data": input_data,
                "schemas": schemas
            }
        
        # Merge params into input_data for executor initialization
        # params are used for executor initialization (like works for CrewManager)
        # input_data is used for execution inputs
        executor_inputs = input_data.copy()
        if task.params:
            executor_inputs.update(task.params)
        
        # Create executor instance for this task execution
        executor = registry.create_executor_instance(extension_id, inputs=executor_inputs)
        
        if executor is None:
            error_msg = f"Failed to create executor instance for extension '{extension.id}'"
            logger.error(error_msg)
            return {
                "error": error_msg,
                "task_id": task.id,
                "name": task.name,
                "task_type": task_type,
                "extension_id": extension.id,
                "input_data": input_data,
                "schemas": schemas
            }
        
        # Prepare execution inputs
        execution_inputs = input_data.copy()
        # Note: method is no longer passed to executor.execute()
        # Executors determine execution logic based on input_data fields
        
        # Special handling for system_info_executor (helper logic)
        # Use extension.id to check if it's system_info_executor
        if extension and extension.id == "system_info_executor":
            # If resource is not specified, try to infer resource from task name
            if "resource" not in execution_inputs:
                task_name_lower = task.name.lower()
                if "cpu" in task_name_lower:
                    execution_inputs["resource"] = "cpu"
                elif "memory" in task_name_lower or "mem" in task_name_lower:
                    execution_inputs["resource"] = "memory"
                elif "disk" in task_name_lower:
                    execution_inputs["resource"] = "disk"
                else:
                    execution_inputs["resource"] = "all"
        
        # Handle aggregate_results - this is a special TaskManager feature, not an executor method
        # Check if this is an aggregate_results request (legacy support)
        # Note: aggregate_results is handled by TaskManager, not by any executor
        if task_method == "aggregate_results":
            return self._aggregate_dependency_results(task, input_data)
        
        # Execute task
        try:
            result = await executor.execute(execution_inputs)
            return result
        except Exception as e:
            logger.error(f"Error executing task {task.id} with executor {executor.__class__.__name__}: {e}", exc_info=True)
            return {
                "error": str(e),
                "task_id": task.id,
                "name": task.name,
                "task_type": task_type,
                "executor": executor.__class__.__name__,
                "input_data": input_data
            }
    
    def _aggregate_dependency_results(
        self,
        task: TaskModel,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Aggregate results from dependency tasks
        
        Args:
            task: Task that needs to aggregate dependency results
            input_data: Input data containing dependency results (from _resolve_task_dependencies)
            
        Returns:
            Aggregated result dictionary
        """
        # Extract dependency results from input_data
        # Dependency results are merged into input_data with keys like dependency IDs
        aggregated = {
            "summary": "System Resources Aggregation",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "resources": {}
        }
        
        # Get dependencies from task
        dependencies = task.dependencies or []
        
        for dep in dependencies:
            dep_id = dep.get("id") if isinstance(dep, dict) else dep
            if dep_id and dep_id in input_data:
                # Dependency result is in input_data
                dep_result = input_data[dep_id]
                aggregated["resources"][dep_id] = dep_result
        
        # Also check for any keys that look like task IDs (fallback)
        for key, value in input_data.items():
            if key not in aggregated["resources"] and isinstance(value, dict):
                # Check if this looks like a task result (has system info structure)
                if "system" in value or "cores" in value or "total" in value:
                    aggregated["resources"][key] = value
        
        aggregated["resource_count"] = len(aggregated["resources"])
        
        return aggregated


__all__ = [
    "TaskManager",
]


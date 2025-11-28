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
        post_hooks: Optional[List[TaskPostHook]] = None,
        executor_instances: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize TaskManager
        
        Args:
            db: Database session (sync or async)
            root_task_id: Optional root task ID for streaming
            pre_hooks: Optional list of pre-execution hook functions
                Each hook receives (task: TaskModel)
                Hooks can access and modify task.inputs directly
                Hooks can be sync or async functions
                Example:
                    async def my_pre_hook(task):
                        # Custom validation or transformation
                        if task.inputs and task.inputs.get("url"):
                            task.inputs["url"] = task.inputs["url"].strip()
                    task_manager = TaskManager(db, pre_hooks=[my_pre_hook])
            post_hooks: Optional list of post-execution hook functions
                Each hook receives (task: TaskModel, inputs: Dict[str, Any], result: Any)
                Hooks can be sync or async functions
                Example:
                    async def my_post_hook(task, inputs, result):
                        # Custom result processing or logging
                        logger.info(f"Task {task.id} completed with result: {result}")
                    task_manager = TaskManager(db, post_hooks=[my_post_hook])
            executor_instances: Optional shared dictionary for storing executor instances (task_id -> executor)
                Used for cancellation support. If provided, executors created during execution are stored here
                so that cancel_task() can access them. Typically passed from TaskExecutor.
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
        # Store executor instances for cancellation (task_id -> executor)
        # Use shared executor_instances dict from TaskExecutor if provided, otherwise create new one
        # This allows cancel_task() to access executors created during execution
        self._executor_instances: Dict[str, Any] = executor_instances if executor_instances is not None else {}
        # Track tasks that should be re-executed (even if they are completed or failed)
        # This allows re-executing failed tasks and ensures dependencies are also re-executed
        self._tasks_to_reexecute: set[str] = set()
    
    async def cancel_task(
        self,
        task_id: str,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cancel a task execution (called by external sources like CLI/API)
        
        This method:
        1. Checks if task is running
        2. If executor supports cancellation, calls executor.cancel() to get cancellation result
        3. Updates database with cancelled status and token_usage from cancellation result
        
        Args:
            task_id: Task ID to cancel
            error_message: Optional error message for cancellation
            
        Returns:
            Dictionary with cancellation result:
            {
                "status": "cancelled" | "failed",
                "message": str,
                "token_usage": Dict,  # Optional token usage from executor
            }
        """
        try:
            # Get task from database
            task = await self.task_repository.get_task_by_id(task_id)
            if not task:
                return {
                    "status": "failed",
                    "message": f"Task {task_id} not found",
                    "error": "Task not found"
                }
            
            # Check if task can be cancelled
            if task.status in ["completed", "failed", "cancelled"]:
                return {
                    "status": "failed",
                    "message": f"Task {task_id} is already {task.status}, cannot cancel",
                    "current_status": task.status
                }
            
            logger.info(f"Cancelling task {task_id} (current status: {task.status})")
            
            # If task is in_progress and executor supports cancellation, call executor.cancel()
            cancel_result = None
            token_usage = None
            result_data = None
            executor_cancelled = False  # Track if executor.cancel() was actually called
            
            if task.status == "in_progress":
                executor = self._executor_instances.get(task_id)
                if executor and hasattr(executor, 'cancel'):
                    try:
                        logger.info(f"Calling executor.cancel() for task {task_id}")
                        cancel_result = await executor.cancel()
                        executor_cancelled = True
                        logger.info(f"Executor {executor.__class__.__name__} cancel() returned: {cancel_result}")
                        
                        if cancel_result and cancel_result.get("status") == "cancelled":
                            token_usage = cancel_result.get("token_usage")
                            # Use result if available, otherwise use partial_result
                            result_data = cancel_result.get("result") or cancel_result.get("partial_result")
                    except Exception as e:
                        logger.warning(f"Failed to call executor.cancel() for task {task_id}: {str(e)}")
                        cancel_result = {
                            "status": "failed",
                            "message": f"Failed to cancel executor: {str(e)}",
                            "error": str(e)
                        }
            
            # Update database with cancelled status
            error_msg = error_message or (cancel_result.get("message") if cancel_result else "Cancelled by user")
            
            # Prepare update data - merge all fields in one update
            update_data = {
                "status": "cancelled",
                "error": error_msg,
                "completed_at": datetime.now(timezone.utc)
            }
            
            # If we have result data (from executor.cancel()), save it
            if result_data:
                update_data["result"] = result_data
            
            # If token_usage is available, merge it into result
            # If result_data exists, merge token_usage into it; otherwise create new dict
            if token_usage:
                if result_data and isinstance(result_data, dict):
                    # Merge token_usage into existing result
                    result_with_token = result_data.copy()
                    result_with_token["token_usage"] = token_usage
                    update_data["result"] = result_with_token
                else:
                    # Create new result dict with token_usage
                    update_data["result"] = {"token_usage": token_usage}
            
            # Update task status in one call (combines status, error, result, token_usage)
            await self.task_repository.update_task_status(
                task_id=task_id,
                **update_data
            )
            
            # Clear executor reference
            self._executor_instances.pop(task_id, None)
            
            # Build return result
            result = {
                "status": "cancelled",
                "message": error_msg,
            }
            
            if token_usage:
                result["token_usage"] = token_usage
            
            if result_data:
                result["result"] = result_data
            
            logger.info(f"Task {task_id} cancelled successfully")
            return result
            
        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {str(e)}", exc_info=True)
            return {
                "status": "failed",
                "message": f"Failed to cancel task {task_id}",
                "error": str(e)
            }

    
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
            
            # Allow re-execution of failed tasks and pending tasks
            # Skip only completed and in_progress tasks (unless marked for re-execution)
            task_id = str(node.task.id)
            if node.task.status in ["completed", "in_progress"]:
                # Check if task is marked for re-execution
                if task_id not in self._tasks_to_reexecute:
                    logger.info(f"Task {node.task.id} already {node.task.status}, skipping distribution")
                    return
                else:
                    logger.info(f"Task {node.task.id} is {node.task.status} but marked for re-execution, will re-execute")
            elif node.task.status == "failed":
                # Failed tasks can always be re-executed
                logger.info(f"Task {node.task.id} is failed, will re-execute")
            
            # Note: Parent-child relationship is only for tree organization, not execution order
            # Only dependencies affect execution order - a task executes when its dependencies are satisfied
            # We process children first (for tree traversal), then check if task should execute based on dependencies
            
            # Group children by priority
            priority_groups = {}
            for child_node in node.children:
                priority = child_node.task.priority or 999
                if priority not in priority_groups:
                    priority_groups[priority] = []
                child_id = str(child_node.task.id)
                # Include pending tasks, failed tasks, and completed tasks marked for re-execution
                if child_node.task.status not in ["completed", "failed"]:
                    priority_groups[priority].append(child_node)
                    self._add_children_to_priority_groups(child_node, priority_groups)
                elif child_node.task.status == "failed":
                    # Failed tasks should be re-executed
                    priority_groups[priority].append(child_node)
                    self._add_children_to_priority_groups(child_node, priority_groups)
                elif child_node.task.status == "completed" and child_id in self._tasks_to_reexecute:
                    # Completed tasks marked for re-execution should be re-executed
                    priority_groups[priority].append(child_node)
                    self._add_children_to_priority_groups(child_node, priority_groups)
            
            if not priority_groups:
                # No children to execute - check if task should be executed based on dependencies
                # Note: Parent-child relationship is only for organization, not execution order
                # Task execution depends on dependencies, not children status
                deps_satisfied = await self._are_dependencies_satisfied(node.task)
                if deps_satisfied and node.task.status != "completed":
                    logger.debug(f"All dependencies for task {node.task.id} are satisfied, executing task")
                    await self._execute_single_task(node.task, use_callback)
                else:
                    logger.debug(f"No children to execute for task {node.task.id}, and dependencies not satisfied or task already completed")
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
            
            # After processing all children, check if task should be executed based on dependencies
            # Note: Parent-child relationship is only for tree organization, not execution order
            # Only dependencies affect execution order - if a task's dependencies are satisfied, it can execute
            # This handles both pending tasks and failed tasks that need re-execution
            # Tasks execute when their dependencies are satisfied, regardless of children status
            deps_satisfied = await self._are_dependencies_satisfied(node.task)
            if deps_satisfied and node.task.status != "completed":
                logger.debug(f"All dependencies for task {node.task.id} are satisfied, executing task")
                await self._execute_single_task(node.task, use_callback)
                    
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
            child_id = str(child_node.task.id)
            # Include pending tasks, failed tasks, and completed tasks marked for re-execution
            if child_node.task.status not in ["completed", "failed"]:
                priority_groups[priority].append(child_node)
                self._add_children_to_priority_groups(child_node, priority_groups)
            elif child_node.task.status == "failed":
                # Failed tasks should be re-executed
                priority_groups[priority].append(child_node)
                self._add_children_to_priority_groups(child_node, priority_groups)
            elif child_node.task.status == "completed" and child_id in self._tasks_to_reexecute:
                # Completed tasks marked for re-execution should be re-executed
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
                    dep_task_id = str(dep_task.id)
                    # If dependency is marked for re-execution and is still in progress or pending, it's not satisfied yet
                    # But if it's already completed, we can consider it satisfied (it will be re-executed but result is available)
                    if dep_task_id in self._tasks_to_reexecute:
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
                if dep_task_id in self._tasks_to_reexecute:
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
                
            # Check if task is already finished or cancelled
            # Allow re-execution of failed tasks if they are marked for re-execution
            task_id = str(task.id)
            if task.status in ["completed", "cancelled"]:
                # Check if task is marked for re-execution
                if task_id not in self._tasks_to_reexecute:
                    logger.info(f"Task {task.id} already {task.status}, skipping execution")
                    return
                else:
                    logger.info(f"Task {task.id} is {task.status} but marked for re-execution, will re-execute")
            elif task.status == "failed":
                # Failed tasks can be re-executed if marked for re-execution
                if task_id in self._tasks_to_reexecute:
                    logger.info(f"Task {task.id} is failed and marked for re-execution, will re-execute")
                else:
                    # If not marked for re-execution, skip (shouldn't happen in normal flow)
                    logger.info(f"Task {task.id} is failed but not marked for re-execution, skipping execution")
                    return
            
            # Check if task is already in progress (may have been started by another process)
            if task.status == "in_progress":
                logger.info(f"Task {task.id} already in_progress, skipping execution")
                return
            
            # Check if task was cancelled before starting (double-check after potential race condition)
            # Refresh task from database to get latest status
            task = await self.task_repository.get_task_by_id(task.id)
            if not task:
                raise ValueError(f"Task {task.id} not found")
            
            if task.status == "cancelled":
                logger.info(f"Task {task.id} was cancelled, skipping execution")
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
            
            # Final check: if task was cancelled between status update and refresh
            if task.status == "cancelled":
                logger.info(f"Task {task.id} was cancelled after status update, stopping execution")
                return
            
            logger.info(f"Task {task.id} status updated to in_progress")
            
            # Resolve dependencies first (merge dependency results into inputs)
            resolved_inputs = await self._resolve_task_dependencies(task)
            
            # Check cancellation before proceeding
            task = await self.task_repository.get_task_by_id(task.id)
            if not task:
                raise ValueError(f"Task {task.id} not found")
            if task.status == "cancelled":
                logger.info(f"Task {task.id} was cancelled during dependency resolution, stopping execution")
                return
            
            if resolved_inputs != (task.inputs or {}):
                # Update inputs using repository
                await self.task_repository.update_task_inputs(task.id, resolved_inputs)
                # Refresh task object
                task = await self.task_repository.get_task_by_id(task.id)
                if not task:
                    raise ValueError(f"Task {task.id} not found after input data update")
                
                # Check cancellation again
                if task.status == "cancelled":
                    logger.info(f"Task {task.id} was cancelled after input data update, stopping execution")
                    return
            
            # Execute pre-hooks (after dependency resolution, to allow user adjustment based on complete data)
            # Pre-hooks can access and modify task.inputs directly
            # Store inputs before pre-hooks to detect changes (deep copy for nested dicts)
            import copy
            inputs_before_pre_hooks = copy.deepcopy(task.inputs) if task.inputs else {}
            await self._execute_pre_hooks(task)
            
            # Update inputs if pre-hooks modified task.inputs
            # Use deep comparison to detect any changes (including nested dict modifications)
            inputs_after_pre_hooks = task.inputs or {}
            # Deep comparison to detect changes in nested structures
            if inputs_after_pre_hooks != inputs_before_pre_hooks:
                # Pre-hooks modified inputs, update database
                # Make a deep copy to ensure we're saving the current state
                inputs_to_save = copy.deepcopy(inputs_after_pre_hooks) if inputs_after_pre_hooks else {}
                logger.info(
                    f"Pre-hooks modified inputs for task {task.id}: "
                    f"before_keys={list(inputs_before_pre_hooks.keys())}, "
                    f"after_keys={list(inputs_after_pre_hooks.keys())}"
                )
                await self.task_repository.update_task_inputs(task.id, inputs_to_save)
                # Refresh task object to get latest state from database
                task = await self.task_repository.get_task_by_id(task.id)
                if not task:
                    raise ValueError(f"Task {task.id} not found after pre-hook inputs update")
                logger.info(f"Pre-hooks modified inputs for task {task.id}, updated in database")
            else:
                logger.debug(f"Pre-hooks did not modify inputs for task {task.id}")
            
            # Check cancellation before executing
            task = await self.task_repository.get_task_by_id(task.id)
            if not task:
                raise ValueError(f"Task {task.id} not found")
            if task.status == "cancelled":
                logger.info(f"Task {task.id} was cancelled before execution, stopping")
                return
            
            # Execute task using agent executor
            # Use task.inputs (which may have been modified by pre-hooks)
            final_inputs = task.inputs or {}
            logger.info(f"Task {task.id} execution - calling agent executor (name: {task.name})")
            
            # Execute task based on schemas
            # Note: For long-running executors, cancellation check should be done inside executor
            # TaskManager can only check before and after executor execution
            task_result = await self._execute_task_with_schemas(task, final_inputs)
            
            # Check cancellation after execution (in case it was cancelled during execution)
            # Note: If task was cancelled, cancel_task() was already called by external source,
            # so we just need to stop execution and preserve the cancelled status
            task = await self.task_repository.get_task_by_id(task.id)
            if task and task.status == "cancelled":
                logger.info(f"Task {task.id} was cancelled during execution, stopping")
                
                # Clear executor reference
                self._executor_instances.pop(task.id, None)
                
                # Don't update to completed, keep cancelled status
                if self.stream:
                    # StreamingCallbacks may not have task_cancelled method, use task_failed as fallback
                    if hasattr(self.streaming_callbacks, 'task_cancelled'):
                        self.streaming_callbacks.task_cancelled(task.id)
                    else:
                        self.streaming_callbacks.task_failed(task.id, "Task was cancelled")
                return
            
            # Clear executor reference after successful execution
            self._executor_instances.pop(task.id, None)
            
            # Update task status using repository
            # Clear error field when task completes successfully (for re-execution scenarios)
            await self.task_repository.update_task_status(
                task_id=task.id,
                status="completed",
                progress=1.0,
                result=task_result,
                error=None,  # Clear error when task completes successfully
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
            task: Task to execute (hooks can access and modify task.inputs)
            
        Note:
            Pre-hooks are executed after dependency resolution, so task.inputs
            contains the complete resolved data including dependency results.
            Hooks can modify task.inputs directly.
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
        inputs: Dict[str, Any],
        result: Any
    ) -> None:
        """
        Execute post-execution hooks
        
        Args:
            task: Task that was executed
            inputs: Input parameters used for execution
            result: Task execution result
        """
        if not self.post_hooks:
            return
        
        logger.debug(f"Executing {len(self.post_hooks)} post-hooks for task {task.id}")
        
        for hook in self.post_hooks:
            try:
                if iscoroutinefunction(hook):
                    await hook(task, inputs, result)
                else:
                    # Synchronous function - run in executor to avoid blocking
                    await asyncio.to_thread(hook, task, inputs, result)
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
        inputs = task.inputs.copy() if task.inputs else {}
        
        # Get task dependencies from the dependencies field
        task_dependencies = task.dependencies or []
        if not task_dependencies:
            logger.debug(f"No dependencies found for task {task.id}")
            return inputs
        
        # Get all completed tasks by id in the same task tree
        completed_tasks_by_id = await self._get_completed_tasks_by_id(task)
        
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
                # Get the inputs that were used for execution
                # This should include pre-hook modifications since they were saved to DB
                # Use refreshed_task.inputs which contains the latest data from database
                logger.info(
                    f"Loading task {completed_task.id} from DB for post-hook: "
                    f"inputs_type={type(refreshed_task.inputs)}, "
                    f"inputs_keys={list(refreshed_task.inputs.keys()) if refreshed_task.inputs else []}, "
                    f"inputs_value={refreshed_task.inputs}"
                )
                inputs = refreshed_task.inputs or {}
                result = refreshed_task.result
                
                # Ensure we're passing the actual inputs dict (not a reference that might be stale)
                # Make a copy to ensure we're passing the current state
                # If inputs is already a dict, create a shallow copy; otherwise convert to dict
                if isinstance(inputs, dict):
                    inputs = dict(inputs)
                else:
                    # Handle case where inputs might be a JSON string or other type
                    inputs = dict(inputs) if inputs else {}
                
                logger.info(
                    f"Post-hook inputs for task {refreshed_task.id}: "
                    f"keys={list(inputs.keys())}, has_pre_hook_marker={inputs.get('_pre_hook_executed', False)}, "
                    f"inputs_type={type(inputs)}, inputs_value={inputs}"
                )
                
                await self._execute_post_hooks(refreshed_task, inputs, result)
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
        inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute task based on schemas configuration
        
        Uses the executor registry to find and instantiate the appropriate executor
        based on task_type in schemas. Supports both built-in and third-party executors.
        
        Args:
            task: Task to execute
            inputs: Input parameters for task execution
            
        Returns:
            Task execution result
            
        Raises:
            ValueError: If task_type is not registered in executor registry
        """
        schemas = task.schemas or {}
        task_type = schemas.get("type")  # Optional: only used if method is not an executor id
        task_method = schemas.get("method", "command")
        
        logger.info(f"Executing task {task.id} with type={task_type}, method={task_method}")
        
        # ============================================================
        # 1. get executor id from params
        # ============================================================
        params = task.params or {}
        executor_id = params.get("executor_id")

        # Get executor from unified extension registry
        registry = get_registry()
        
        # Strategy: Try to use method as executor id first, then fall back to type-based lookup
        # This allows:
        # 1. Direct id-based lookup: method="crewai_executor" (no type needed)
        # 2. Type-based lookup: type="stdio", method="command" (method is execution method, not id)
        extension_id = None
        extension = None
        
        # If executor_id is already set from params or schemas.method, use it
        if executor_id:
            extension = registry.get_by_id(executor_id)
            if extension and extension.category == ExtensionCategory.EXECUTOR:
                extension_id = executor_id
                logger.debug(f"Using executor_id '{executor_id}' from params/schemas")
        
        # If not found, try to use method as executor id
        if extension is None or (extension and extension.category != ExtensionCategory.EXECUTOR):
            if task_method:
                extension = registry.get_by_id(task_method)
                if extension and extension.category == ExtensionCategory.EXECUTOR:
                    extension_id = task_method
                    executor_id = task_method
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
                executor_id = extension_id
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
                "inputs": inputs,
                "schemas": schemas
            }
        
        if not executor_id:
            executor_id = extension_id
        
        if not executor_id:
            error_msg = (
                f"Task {task.id}: executor_id is required in params. "
                f"Please specify params.executor_id (e.g., 'crewai_executor', 'command_executor')."
            )
            logger.error(error_msg)
            return {
                "error": error_msg,
                "task_id": task.id
            }
        
        # ============================================================
        # 2. extract executor initialization parameters from params
        # ============================================================
        # all fields in params except executor_id are initialization parameters
        init_params = params.copy()
        init_params.pop("executor_id", None)  # executor_id is already handled separately
        
        # Get input_schema from schemas to pass to executor
        input_schema = schemas.get("input_schema")
        if input_schema:
            init_params["inputs_schema"] = input_schema
        
        # Inject LLM API key if needed (for CrewAI executors)
        # Priority: request header > user config
        # Note: CrewAI/LiteLLM automatically reads provider-specific API keys from environment,
        # so we set the appropriate env var here if we have a dynamic key from header/config
        # LLM key is never stored in database (task.params)
        if executor_id == "crewai_executor":
            from aipartnerupflow.core.utils.llm_key_context import get_llm_key, get_llm_provider_from_header
            from aipartnerupflow.core.utils.llm_key_injector import inject_llm_key, detect_provider_from_model
            
            # Priority for provider detection:
            # 1. Provider from request header (parsed from X-LLM-API-KEY format: provider:key)
            # 2. Provider from works configuration (model name)
            # 3. Auto-detect from model name
            works = params.get("works", {})
            detected_provider = get_llm_provider_from_header()  # First check header (parsed from provider:key format)
            
            if not detected_provider:
                # Detect provider from works configuration
                if works:
                    # Try to extract model from agents
                    agents = works.get("agents", {})
                    for agent_config in agents.values():
                        agent_llm = agent_config.get("llm")
                        if isinstance(agent_llm, str):
                            detected_provider = detect_provider_from_model(agent_llm)
                            break
            
            # Get LLM key (may be provider-specific)
            # get_llm_key will use provider from header if available
            llm_key = get_llm_key(user_id=task.user_id, provider=detected_provider)
            if llm_key:
                # Inject LLM key with provider detection
                # This supports multiple LLM providers (OpenAI, Anthropic, Google, etc.)
                inject_llm_key(
                    api_key=llm_key,
                    provider=detected_provider,
                    works=works,
                    model_name=None  # Will be extracted from works if available
                )
                logger.debug(f"Injected LLM key for task {task.id} (user: {task.user_id}, provider: {detected_provider or 'auto'})")
        
        # ============================================================
        # 3. create executor instance
        # ============================================================
        # Create cancellation checker
        cached_cancelled = task.status == "cancelled"
        def cancellation_checker() -> bool:
            return cached_cancelled
        
        # Create executor: inputs as inputs parameter, other as **kwargs
        # Note: Input validation is now handled by executor itself (in BaseTask or executor.execute)
        executor = registry.create_executor_instance(
            extension_id=executor_id,
            inputs=inputs,  # inputs for execution (will be validated by executor)
            **init_params,  # initialization parameters (works, name, inputs_schema, etc.)
            cancellation_checker=cancellation_checker
        )
        
        if executor is None:
            error_msg = f"Failed to create executor instance '{executor_id}'"
            logger.error(error_msg)
            return {
                "error": error_msg,
                "task_id": task.id,
                "executor_id": executor_id
            }
        
        # Store executor for cancellation support
        if hasattr(executor, 'cancel'):
            self._executor_instances[task.id] = executor
            logger.debug(f"Stored executor instance for task {task.id} (supports cancellation)")
        
        # ============================================================
        # 4. execute executor
        # ============================================================
        # Note: Input validation and any executor-specific input processing
        # should be handled by the executor itself (in BaseTask or executor.execute)
        # TaskManager only handles task orchestration and distribution
        try:
            result = await executor.execute(inputs)
            return result
        except Exception as e:
            logger.error(f"Error executing task {task.id} with executor {executor.__class__.__name__}: {e}", exc_info=True)
            # Clear executor reference on error
            self._executor_instances.pop(task.id, None)
            return {
                "error": str(e),
                "task_id": task.id,
                "executor_id": executor_id
            }
    
__all__ = [
    "TaskManager",
]

